import asyncio
from asyncio.subprocess import Process
from asyncio.tasks import Task
from collections.abc import Awaitable
from os import environ
from os.path import basename
import pathlib
import signal
import ssl
from typing import Callable
from websockets import (
    ConnectionClosedError,
    ConnectionClosedOK,
    Request,
    Response,
    ServerConnection,
)
from websockets.asyncio.server import serve
from common.data import (
    ErrorResp,
    ExitResp,
    KillReq,
    LogResp,
    OkayResp,
    OpenReq,
    serialize,
    deserialize,
)
import logging
from common.log import InterceptHandler


def get_host(ws: ServerConnection) -> str:
    addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
    (host, _port) = addrs
    return host


SSL_CERT_PATH: str = environ.get("SSL_CERT_PATH", "./cert.pem")
SSL_KEY_PATH: str = environ.get("SSL_KEY_PATH", "./key.pem")
PSYNC_HOST: str = environ.get("PSYNC_SERVER_IP", "0.0.0.0")
PSYNC_PORT: str = environ.get("PSYNC_SERVER_PORT", "5000")
PSYNC_ORIGINS: str = environ.get("PSYNC_ORIGINS", "localhost 127.0.0.1")


class PsyncServer:
    """
    The main interface for the psync websocker server.

    Configuration environment variables:
        PSYNC_HOST: IP for the server.
            Default: "0.0.0.0"
        PSYNC_PORT: Port for the server.
            Default: 5000
        PSYNC_ORIGINS: Space-separated list of allowed foreign origins.
            Default: "localhost"
        SSL_CERT_PATH: Path to the SSL certification file.
            Default: "./cert.pem"
        SSL_KEY_PATH: Path to the SSL key file.
            Default: "./key.pem"
    """

    host: str = PSYNC_HOST
    """Local host for the server."""

    port: int = int(PSYNC_PORT)
    """Exposed port for websocket connection."""

    origins: list[str] = (PSYNC_ORIGINS).split()
    """Allowed origins for websocket connections."""

    sessions: dict[str, Process] = {}
    """Active sessions. A dict of IP addresses and the running PID. IP
    addresses _must_ match those in origins."""

    tasks: dict[str, Task[None]] = {}
    """Active sessions. A dict of IP addresses and the running log task. IP
    addresses _must_ match those in origins."""

    coroutine: Task[None] | None = None

    async def serve(self) -> None:
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(
            pathlib.Path(SSL_CERT_PATH).expanduser(),
            pathlib.Path(SSL_KEY_PATH).expanduser(),
        )
        print(ssl_ctx.get_ca_certs())
        server = await serve(
            (self.handle()),
            self.host,
            self.port,
            process_request=self.process_request(),
            ssl=ssl_ctx,
        )
        self.coroutine = asyncio.create_task(server.serve_forever())
        try:
            await self.coroutine
        except RuntimeError:
            # 'event loop stopped before Future completed'
            pass

    def process_request(self) -> Callable[[ServerConnection, Request], Response | None]:
        def inner(ws: ServerConnection, _req: Request) -> Response | None:
            addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
            (host, _port) = addrs
            if host not in self.origins:
                return ws.respond(400, "Client address not recognized.")

        return inner

    async def end_session(self, ws: ServerConnection):
        host = get_host(ws)
        try:
            _ = self.sessions.pop(host)
        except Exception:
            pass
        try:
            _ = self.tasks.pop(host)
        except Exception:
            pass
        await ws.close()

    def mk_handle_signal(self, ws: ServerConnection):
        async def inner():
            logging.info("Gracefully shutting down...")
            await ws.close()
            _ = self.coroutine.cancel()  # pyright: ignore[reportOptionalMemberAccess]
            asyncio.get_event_loop().stop()

        return lambda: asyncio.create_task(inner())

    def handle(self) -> Callable[[ServerConnection], Awaitable[None]]:
        async def inner(ws: ServerConnection):
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGINT, self.mk_handle_signal(ws)
            )
            try:
                async for data in ws:
                    if isinstance(data, bytes):
                        msg = data.decode()
                    else:
                        msg = data

                    try:
                        req = deserialize(msg)
                    except ValueError as e:
                        await ws.send(serialize(ErrorResp(f"{e}")))
                        continue

                    match req:
                        case OpenReq():
                            await self.open(req, ws)
                        case KillReq():
                            await self.kill(req, ws)
                        case _:
                            logging.warning(f"Got unknown request {req}")
            except ConnectionClosedOK:
                logging.info("connection closed")
                pass
            except Exception as e:
                logging.error(e)
                await self.end_session(ws)

        return inner

    async def open(self, req: OpenReq, ws: ServerConnection):
        host = get_host(ws)
        if self.sessions.get(host) is not None:
            self.sessions[host]
            resp = ErrorResp(msg="Process already open for this client.")
            await ws.send(serialize(resp))
        else:
            path = pathlib.Path.expanduser(req.path).resolve()
            args = [str(path), *req.args]
            env = {"PYTHONUNBUFFERED": "1", **req.env}
            logging.info(
                f"Running `{map(lambda x: (f'{x[0]}={x[1]}'), env.items())} [...]/{basename(args[0])} {' '.join(args[1:])}`"
            )
            try:
                p = await asyncio.create_subprocess_exec(
                    *args,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                self.sessions[host] = p
                self.tasks[host] = asyncio.create_task(self.log(ws, p))
                resp = OkayResp()
                await ws.send(serialize(resp))
            except Exception as e:
                logging.error(f"Failed to run process with error {e}")
                resp = ErrorResp(msg=f"Caught exception: {e}")
                await ws.send(serialize(resp))

    async def log(self, ws: ServerConnection, process: asyncio.subprocess.Process):
        try:
            logging.info(f"Running process with PID {process.pid}")
            if process.stdout is not None:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    msg = line.decode("utf-8")
                    print(msg, end="")
                    await ws.send(serialize(LogResp(msg)))

            returncode = await process.wait()
            logging.info(f"process exited with code {returncode}")
            await ws.send(serialize(ExitResp(exit_code=str(returncode))))
            await self.end_session(ws)

        except (KeyError, ConnectionClosedError, ConnectionClosedOK):
            pass

    async def kill(self, _req: KillReq, ws: ServerConnection):
        host = get_host(ws)
        p = self.sessions.get(host)
        task = self.tasks.get(host)
        if p is not None and task is not None:
            logging.info(f"Killing PID {p.pid}")
            p.kill()
            code = await p.wait()
            resp = ExitResp(str(code))
            await ws.send(serialize(resp))
        else:
            logging.error(
                f"Tried to kill process for host {host}, but no process was running."
            )
            await ws.send(
                serialize(
                    ErrorResp(msg="Tried to kill process, but no process was running.")
                )
            )
        await ws.close()


def main():
    log_level = environ.get("PSYNC_LOG", "INFO").upper()
    logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)
    asyncio.run(PsyncServer().serve())


if __name__ == "__main__":
    main()
