import asyncio
import os
import pathlib
import signal
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
from client.args import SERVER_IP, SERVER_PORT, USER, Args, parse_args


class PsyncClient:
    args: list[str]
    env: dict[str, str]
    path: pathlib.Path
    quit: bool = False
    force_exit: bool = False

    def __init__(self, args: list[str], env: dict[str, str], path: pathlib.Path):
        self.args = args
        self.env = env
        self.path = path

    def mk_handler(self, ws: websockets.ClientConnection):
        async def inner():
            if not self.force_exit:
                logging.info("Gracefully shutting down...")
                self.force_exit = True
                await ws.send(serialize(KillReq()))
                await ws.close()
                asyncio.get_event_loop().stop()
            else:
                logging.warning("Got second SIGINT, shutting down")
                asyncio.get_event_loop().stop()
                raise Exception("Forced shutdown")

        return lambda: asyncio.create_task(inner())

    async def run(self):
        async with websockets.connect(f"ws://{SERVER_IP}:{SERVER_PORT}") as ws:
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGINT, self.mk_handler(ws)
            )
            await ws.send(
                serialize(OpenReq(path=self.path, env=self.env, args=self.args))
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

            # TODO
            # wss impl
            # dockerfile for server daemon with ssl cert
            # probably not: stdin


def rsync(args: Args):
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
    log_level = os.environ.get("PSYNC_LOG", "INFO").upper()
    logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)

    args = parse_args()
    rsync(args)

    client_path = pathlib.Path(f"{args.dest_path}/{os.path.basename(args.target_path)}")
    client = PsyncClient(args=args.args, env=args.env, path=client_path)
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
