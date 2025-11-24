import asyncio
from asyncio.tasks import Task
from collections.abc import Awaitable
import datetime
from os import environ
import pathlib
from subprocess import PIPE, STDOUT, Popen
from typing import Callable
from websockets import Request, Response, ServerConnection
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
    """

    host: str = environ.get("PSYNC_SERVER_IP", "0.0.0.0")
    """Local host for the server."""

    port: int = int(environ.get("PSYNC_SERVER_PORT", "5000"))
    """Exposed port for websocket connection."""

    origins: list[str] = (environ.get("PSYNC_ORIGINS", "localhost 127.0.0.1")).split()
    """Allowed origins for websocket connections."""

    sessions: dict[str, Popen[bytes]] = {}
    """Active sessions. A dict of IP addresses and the running PID. IP
    addresses _must_ match those in origins."""

    tasks: dict[str, Task[None]] = {}
    """Active sessions. A dict of IP addresses and the running log task. IP
    addresses _must_ match those in origins."""

    async def serve(self) -> None:
        server = await serve(
            (self.handle()),
            self.host,
            self.port,
            process_request=self.process_request(),
        )
        await server.serve_forever()

    def process_request(self) -> Callable[[ServerConnection, Request], Response | None]:
        def inner(ws: ServerConnection, _req: Request) -> Response | None:
            addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
            (host, _port) = addrs
            if host not in self.origins:
                return ws.respond(400, "Client address not recognized.")

        return inner

    def handle(self) -> Callable[[ServerConnection], Awaitable[None]]:
        async def inner(ws: ServerConnection):
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

        return inner

    async def open(self, req: OpenReq, ws: ServerConnection):
        addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
        (host, _port) = addrs
        if self.sessions.get(host) is not None:
            self.sessions[host]
            resp = ErrorResp(msg="Process already open for this client.")
            await ws.send(serialize(resp))
        else:
            path = pathlib.Path.expanduser(req.path).resolve()
            args = [str(path), *req.args]
            logging.info(f"Running `{' '.join(args)}` with env {req.env}")
            try:
                p = Popen(
                    args=args,
                    env=req.env,
                    stdout=PIPE,
                    stderr=STDOUT,
                )
                self.sessions[host] = p
                self.tasks[host] = asyncio.create_task(self.log(ws, p))
                resp = OkayResp()
                await ws.send(serialize(resp))
            except Exception as e:
                logging.error(f"Failed to run process with error {e}")
                resp = ErrorResp(msg=f"Caught exception: {e}")
                await ws.send(serialize(resp))

    async def log(self, ws: ServerConnection, process: Popen[bytes]):
        logging.info("in log fn")
        try:
            while process.poll() is None:
                if process.stdout is not None:
                    for line in process.stdout:
                        await ws.send(serialize(LogResp(msg=line.decode("utf-8"))))
            logging.info(f"done polling! {process.returncode}")
            await ws.send(serialize(ExitResp(exit_code=str(process.returncode))))
            addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
            (host, _port) = addrs
            try:
                _ = self.tasks.pop(host)
            except Exception:
                pass
            try:
                _ = self.sessions.pop(host)
            except Exception:
                pass

        except KeyError:
            pass

    async def kill(self, _req: KillReq, ws: ServerConnection):
        addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
        (host, _port) = addrs

        p = self.sessions.get(host)
        task = self.tasks.get(host)
        if p is not None and task is not None:
            p.kill()
            start = datetime.datetime.now()
            while p.poll() is None and not task.done():
                now = datetime.datetime.now()
                if (now - start).seconds > 5:
                    await ws.send(
                        serialize(ErrorResp(f"Failed to kill process with pid {p.pid}"))
                    )
                    return
                pass
            resp = ExitResp(str(p.returncode))
            await ws.send(serialize(resp))
        else:
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
