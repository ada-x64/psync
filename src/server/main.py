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
import pathlib
import signal
import ssl
from typing import Callable
from websockets import (
    ConnectionClosedError,
    ConnectionClosedOK,
    ServerConnection,
)
from websockets.asyncio.server import serve
from websockets.typing import Origin
from common.data import (
    ErrorResp,
    ExitResp,
    KillReq,
    LogResp,
    OkayResp,
    OpenReq,
    SetPidResp,
    HealthCheckReq,
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

    __tasks: dict[str, dict[int, PTask]] = {}
    """{[host: str]: {[pid: str]: PTask} }"""
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
            ssl=ssl_ctx,
            origins=list(map(lambda x: Origin(f"wss://{x}"), self.args.origins)),
        )
        self.__coroutine = asyncio.create_task(server.serve_forever())
        try:
            await self.__coroutine
        except RuntimeError as e:
            # 'event loop stopped before Future completed'
            logging.info(f"Got error {e}")
            pass

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
                raise SystemExit(1)

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
                        case HealthCheckReq():
                            logging.info("Health check OK")
                            await ws.send(serialize(OkayResp()))
                            await ws.close()
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
        path = pathlib.Path.expanduser(req.path).resolve()
        base_env = environ.copy() if self.args.use_base_env else {}
        if not self.args.use_base_env:
            # still get path and etc
            for var in ['PATH','HOME','USER','SHELL']:
                if var in environ:
                    base_env[var] = environ[var]
            if 'VIRTUAL_ENV' in environ:
                base_env['VIRUTAL_ENV'] = environ['VIRTUAL_ENV']
                base_env["PATH"] = f"{environ['VIRTUAL_ENV']}/bin:{base_env["PATH"]}"
        env = base_env | req.env

        info_log = f"Running `{path} {' '.join(req.args)}`"
        if env != {}:
            info_log += f"\n... with env {pprint(env)}"
        if self.args.user is not None:
            info_log += f"... as user {self.args.user}"

        logging.info(info_log)

        try:
            p = await asyncio.create_subprocess_exec(
                path,
                *req.args,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                user=self.args.user,
            )
            task = PTask(asyncio.create_task(self.__log(ws, p)), p)

            if self.__tasks.get(host) is None:
                self.__tasks[host] = {p.pid: task}
            else:
                self.__tasks[host][p.pid] = task

            resp = SetPidResp(pid=p.pid)
            await ws.send(serialize(resp))

        except Exception as e:
            logging.error(f"Failed to start process `{path}` with error {e}")
            resp = ErrorResp(f"Server error: {e}")
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

    async def __kill(self, req: KillReq, ws: ServerConnection):
        host = self.__get_host(ws)
        tasks = self.__tasks.get(host)
        if tasks is None:
            msg = f"Tried to kill process for host {host}, but no process was running."
            logging.error(msg)
            await ws.send(serialize(ErrorResp(msg)))
            return

        task = tasks.get(req.pid)
        if task is None:
            msg = f"Tried to kill process {req.pid}, but it was not found."
            logging.error(msg)
            await ws.send(serialize(ErrorResp(msg)))
            return

        process = task.process
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
