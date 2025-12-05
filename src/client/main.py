"""
psync client
"""

import asyncio
import os
from pathlib import Path
import signal
import ssl
import subprocess
import websockets
from common.data import (
    ErrorResp,
    ExitResp,
    KillReq,
    LogResp,
    OkayResp,
    OpenReq,
    deserialize,
    serialize,
)
import logging
from common.log import InterceptHandler
from client.args import (
    Args,
    parse_args,
)


class PsyncClient:
    """
    The primary interface for psync. The client CLI allows users to sync files with
    rsync, then execute them remotely while receiving the logs.
    """

    args: Args
    __quit: bool = False
    __force_exit: bool = False

    def __init__(self, args: Args):
        self.args = args

    def __mk_handler(self, ws: websockets.ClientConnection):
        async def inner():
            if not self.__force_exit:
                logging.info("Gracefully shutting down...")
                self.__force_exit = True
                await ws.send(serialize(KillReq()))
                await ws.close()
                asyncio.get_event_loop().stop()
            else:
                logging.warning("Got second SIGINT, shutting down")
                asyncio.get_event_loop().stop()
                raise Exception("Forced shutdown")

        return lambda: asyncio.create_task(inner())

    async def run(self):
        """Run the client instance."""
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_ctx.load_verify_locations(Path(self.args.ssl_cert_path).expanduser())
        ssl_ctx.check_hostname = False  # not ideal
        async with websockets.connect(
            f"wss://{self.args.server_ip}:{self.args.server_port}", ssl=ssl_ctx
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
                    exit(1)

                match resp:
                    case LogResp():
                        print(resp.msg, end="")
                    case ErrorResp():
                        logging.error(f"Received server error: {resp.msg}")
                        await ws.close()
                        exit(1)
                    case ExitResp():
                        logging.info(f"Exiting with code {resp.exit_code}")
                        await ws.close()
                        exit(resp.exit_code)
                    case OkayResp():
                        logging.info("Running exectuable...")
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

    client = PsyncClient(args)
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
