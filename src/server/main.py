"""
psync server
"""

from pprint import PrettyPrinter
from dataclasses import dataclass
from os import environ
import asyncio
from asyncio.tasks import Task
from asyncio.subprocess import Process
from collections.abc import Awaitable
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
from server.args import (
    Args,
    parse_args,
)

pprint = PrettyPrinter().pformat


@dataclass
class PTask:
    """
    Simple wrapper class for task-based process execution.
    """

    task: Task[None]
    process: Process


class PsyncServer:
    """
    The main interface for the psync websocker server.
    """

    args: Args

    __tasks: dict[str, PTask] = {}
    """Active sessions. A dict of IP addresses and the running log task. IP
    addresses _must_ match those in origins."""

    __coroutine: Task[None] | None = None
    """The main coroutine for this server."""

    __force_shutdown: bool = False

    def __init__(self, args: Args):
        logging.debug(pprint(args))
        self.args = args

    def __get_host(self, ws: ServerConnection) -> str:
        addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
        (host, _port) = addrs
        return host

    async def serve(self) -> None:
        """
        The main interface for the server. Will serve forever, or until exited with SIGINT/Ctrl-C.
        """
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(
            pathlib.Path(self.args.cert_path).expanduser(),
            pathlib.Path(self.args.key_path).expanduser(),
        )
        logging.debug(pprint(ssl_ctx.get_ca_certs()))
        server = await serve(
            (self.__handle()),
            self.args.host,
            int(self.args.port),
            process_request=self.__process_request(),
            ssl=ssl_ctx,
        )
        self.__coroutine = asyncio.create_task(server.serve_forever())
        try:
            await self.__coroutine
        except RuntimeError as e:
            # 'event loop stopped before Future completed'
            logging.info(f"Got error {e}")
            pass

    def __process_request(
        self,
    ) -> Callable[[ServerConnection, Request], Response | None]:
        def inner(ws: ServerConnection, _req: Request) -> Response | None:
            addrs: tuple[str, str] = ws.remote_address  # pyright: ignore[reportAny]
            (host, port) = addrs
            if host not in self.args.origins:
                logging.info(f"Rejecting unknown request origin {host}:{port}")
                return ws.respond(400, "Client address not recognized.")

        return inner

    async def __end_session(self, ws: ServerConnection):
        host = self.__get_host(ws)
        try:
            _ = self.__tasks.pop(host)
        except Exception:
            pass
        await ws.close()

    def __mk_handle_signal(self, ws: ServerConnection):
        async def inner():
            if not self.__force_shutdown:
                logging.info("Gracefully shutting down...")
                self.__force_shutdown = True
                await ws.close()
                _ = self.__coroutine.cancel()  # pyright: ignore[reportOptionalMemberAccess]
                asyncio.get_event_loop().stop()
                raise SystemExit(130)
            else:
                logging.warning("Second Ctrl-C detected, forcing shutdown.")
                raise SystemExit(130)

        return lambda: asyncio.create_task(inner())

    def __handle(self) -> Callable[[ServerConnection], Awaitable[None]]:
        async def inner(ws: ServerConnection):
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGINT, self.__mk_handle_signal(ws)
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
                        logging.error(e)
                        await ws.send(serialize(ErrorResp(f"{e}")))
                        continue

                    match req:
                        case OpenReq():
                            await self.__open(req, ws)
                        case KillReq():
                            await self.__kill(req, ws)
                        case _:
                            logging.warning(f"Got unknown request {req}")
            except ConnectionClosedOK:
                logging.info("connection closed")
                pass
            except Exception as e:
                logging.error(e)
                await self.__end_session(ws)

        return inner

    async def __open(self, req: OpenReq, ws: ServerConnection):
        host = self.__get_host(ws)
        if self.__tasks.get(host) is not None:
            ptask = self.__tasks[host]
            logging.warning(
                f"Cancelling previous task for host {host} (PID {ptask.process.pid})"
            )
            ptask.process.kill()
            _ = ptask.task.cancel()
            _ = self.__tasks.pop(host)
        path = pathlib.Path.expanduser(req.path).resolve()
        args = [str(path), *req.args]
        env = req.env if not self.args.use_base_env else {**environ, **req.env}

        info_log = f"Running `[...]/{basename(args[0])} {' '.join(args[1:])}`..."
        if env != {}:
            info_log += f"\n... with env {pprint(env)}"
        if self.args.user is not None:
            info_log += f"... as user {self.args.user}"

        logging.info(info_log)

        try:
            p = await asyncio.create_subprocess_exec(
                *args,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                user=self.args.user,
            )
            self.__tasks[host] = PTask(asyncio.create_task(self.__log(ws, p)), p)
            resp = OkayResp()
            await ws.send(serialize(resp))
        except Exception as e:
            logging.error(f"Failed to run process with error {e}")
            resp = ErrorResp(msg=f"Server error: {e}")
            await ws.send(serialize(resp))

    async def __log(self, ws: ServerConnection, process: asyncio.subprocess.Process):
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
            await self.__end_session(ws)

        except (KeyError, ConnectionClosedError, ConnectionClosedOK):
            pass

    async def __kill(self, _req: KillReq, ws: ServerConnection):
        host = self.__get_host(ws)
        ptask = self.__tasks.get(host)
        if ptask is None:
            logging.error(
                f"Tried to kill process for host {host}, but no process was running."
            )
            await ws.send(
                serialize(
                    ErrorResp(msg="Tried to kill process, but no process was running.")
                )
            )
            return
        process = ptask.process
        logging.info(f"Killing PID {process.pid}")
        process.kill()
        code = await process.wait()
        resp = ExitResp(str(code))
        await ws.send(serialize(resp))
        await ws.close()


def main(args: Args | None = None):
    """Run the server as an executable."""
    args = parse_args() if args is None else args
    logging.basicConfig(handlers=[InterceptHandler()], level=args.log_level, force=True)
    try:
        asyncio.run(PsyncServer(args).serve())
    except SystemExit as e:
        exit(e.code)
    except Exception:
        exit(1)


if __name__ == "__main__":
    main()
