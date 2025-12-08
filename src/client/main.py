"""
psync client
"""

from io import TextIOWrapper
import sys
import asyncio
import os
from pathlib import Path
import signal
import ssl
import subprocess
import websockets
from websockets.typing import Origin
from common.data import (
    ErrorResp,
    ExitResp,
    KillReq,
    LogResp,
    OkayResp,
    OpenReq,
    SetPidResp,
    deserialize,
    serialize,
)
import logging
from common.log import InterceptHandler
from client.args import (
    Args,
    parse_args,
)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _typeshed import SupportsWrite
    Logfile = SupportsWrite[str]
else:
    Logfile = Any


class PsyncClient:
    """
    The primary interface for psync. The client CLI allows users to sync files with
    rsync, then execute them remotely while receiving the logs.
    """

    args: Args
    pid: int | None = None
    """ID of the current connection."""
    __force_exit: bool = False
    __outfile: Logfile

    def __init__(self, args: Args):
        self.args = args
        if isinstance(self.args.logfile, Path):
            self.__outfile = open(self.args.logfile, "w")
        elif self.args.logfile is not None:
            self.__outfile = self.args.logfile
        else:
            self.__outfile = sys.stdout

    def __enter__(self):
        return self

    def __exit__(self):
        if isinstance(self.__outfile, TextIOWrapper):
            self.__outfile.close()

    def __mk_handler(self, ws: websockets.ClientConnection):
        async def inner():
            if not self.__force_exit:
                logging.info("Gracefully shutting down...")
                self.__force_exit = True
                if self.pid is not None:
                    await ws.send(serialize(KillReq(pid=self.pid)))
                await ws.close()
                asyncio.get_event_loop().stop()
                raise SystemExit(130)
            else:
                logging.warning("Got second SIGINT, shutting down")
                asyncio.get_event_loop().stop()
                raise SystemExit(1)

        return lambda: asyncio.create_task(inner())

    async def run(self):
        """Run the client instance."""
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_ctx.load_verify_locations(Path(self.args.ssl_cert_path).expanduser())
        ssl_ctx.check_hostname = False  # not ideal
        async with websockets.connect(
            f"wss://{self.args.server_ip}:{self.args.server_port}",
            ssl=ssl_ctx,
            origin=Origin(f"wss://{self.args.client_origin}"),
        ) as ws:
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGINT, self.__mk_handler(ws)
            )
            await ws.send(
                serialize(
                    OpenReq(
                        path=self.args.destination_path(),
                        env=self.args.env,
                        args=self.args.args,
                    )
                )
            )
            async for data in ws:
                if isinstance(data, bytes):
                    msg = data.decode()
                else:
                    msg = data

                try:
                    resp = deserialize(msg)
                except ValueError as e:
                    logging.error(
                        f"Failed to deserialize message '{msg}' with error '{e}'"
                    )
                    await ws.close()
                    raise Exception(e)

                match resp:
                    case LogResp():
                        print(resp.msg, end="", file=self.__outfile)
                    case ErrorResp():
                        logging.error(f"Received server error: {resp.msg}")
                        await ws.close()
                        raise Exception(resp.msg)
                    case ExitResp():
                        logging.info(f"Exiting with code {resp.exit_code}")
                        await ws.close()
                        raise SystemExit(resp.exit_code)
                    case SetPidResp():
                        logging.info(f"Remote PID = {resp.pid}")
                        self.pid = resp.pid
                    case OkayResp():
                        logging.info("OK.")
                    case _:
                        logging.warning(f"Got unknown request {resp}")


def __rsync(args: Args):
    """Runs rsync."""
    rsync_args = [
        "rsync",
        "-avzr",
        "-e",
        f"/usr/bin/ssh {args.ssh_args} -p {str(args.server_ssh_port)}",
        "--progress",
        "--mkpath",
        args.target_path,
        *args.assets,
        args.rsync_url(),
    ]
    logging.info(" ".join(rsync_args))
    p = subprocess.run(rsync_args)
    if p.returncode != 0:
        msg = f"Rsync failed with exit code {p.returncode}"
        logging.error(msg)
        raise Exception(msg)


def main(args: Args | None = None):
    """
    The main executable.
    Sync project files with rsync, then run the client.
    """
    log_level = os.environ.get("PSYNC_LOG", "INFO").upper()
    logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)

    args = parse_args() if args is None else args
    __rsync(args)

    try:
        asyncio.run(PsyncClient(args).run())
    except SystemExit as e:
        exit(e.code)
    except Exception:
        exit(1)


if __name__ == "__main__":
    main()
