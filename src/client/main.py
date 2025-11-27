"""
psync client
"""

import asyncio
import os
import pathlib
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
from client.args import SERVER_IP, SERVER_PORT, USER, SSL_CERT_PATH, Args, parse_args


class PsyncClient:
    """
    The primary interface for psync. The client CLI allows users to sync files with
    rsync, then execute them remotely while receiving the logs.

    CLI arguments: ::

        usage: psync-client [-h] --path PATH [--extra EXTRA [EXTRA ...]] [--env ENV] [--args ARGS]

        Client for the psync server.

        options:
          -h, --help            show this help message and exit
          --path, -p PATH       Path to the target exectuable.
          --extra, -E EXTRA [EXTRA ...]
                                Extra files or directories to be synced to the destination path.
          --env, -e ENV         Environment variables to set in the remote execution environment. Variables
                                must be space-sepated or double-quoted.
          --args, -a ARGS       Arguments with which to run the remote executable.

    Environment configuration:
        PSYNC_SERVER_IP: The IP address of the server instance.
            Default: 127.0.0.1
        PSYNC_SERVER_PORT: The port of the server instance.
            Default: 5000
        PSYNC_SSH_USER: The SSH user for rsync.
            Default: Unset. Will use the default ssh user.
        PSYNC_CERT_PATH: Path to the SSL certificate. Used to trust self-signed certs. Should
            match the server's certificate.
            Default: ~/.local/share/psync/cert.pem
    """

    __args: list[str]
    __env: dict[str, str]
    __path: pathlib.Path
    __quit: bool = False
    __force_exit: bool = False

    def __init__(self, args: list[str], env: dict[str, str], path: pathlib.Path):
        self.__args = args
        self.__env = env
        self.__path = path

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
        ssl_ctx.load_verify_locations(pathlib.Path(SSL_CERT_PATH).expanduser())
        ssl_ctx.check_hostname = False  # not ideal
        print(ssl_ctx.get_ca_certs())
        async with websockets.connect(
            f"wss://{SERVER_IP}:{SERVER_PORT}", ssl=ssl_ctx
        ) as ws:
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGINT, self.__mk_handler(ws)
            )
            await ws.send(
                serialize(OpenReq(path=self.__path, env=self.__env, args=self.__args))
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
                        logging.error(resp.msg)
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
    if USER != "":
        user = f"{USER}@"
    else:
        user = ""
    url = f"{user}{SERVER_IP}:{args.dest_path}"
    rsync_args = [
        "rsync",
        "-avzr",
        "--progress",
        "--mkpath",
        args.target_path,
        *args.extra,
        url,
    ]
    logging.info(" ".join(rsync_args))
    p = subprocess.run(rsync_args)
    if p.returncode != 0:
        logging.error(f"Rsync failed with exit code {p.returncode}")
        exit(1)


def main():
    """
    The main executable.
    Sync project files with rsync, then run the client.
    """
    log_level = os.environ.get("PSYNC_LOG", "INFO").upper()
    logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)

    args = parse_args()
    __rsync(args)

    client_path = pathlib.Path(f"{args.dest_path}/{os.path.basename(args.target_path)}")
    client = PsyncClient(args=args.args, env=args.env, path=client_path)
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
