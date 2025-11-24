import asyncio
import os
import pathlib
import subprocess
import websockets
from common.data import OpenReq, serialize
import logging
from common.log import InterceptHandler
from client.args import SERVER_IP, SERVER_PORT, USER, Args, parse_args


class PsyncClient:
    args: list[str]
    env: dict[str, str]
    path: pathlib.Path

    def __init__(self, args: list[str], env: dict[str, str], path: pathlib.Path):
        self.args = args
        self.env = env
        self.path = path

    async def run(self):
        async with websockets.connect(f"ws://{SERVER_IP}:{SERVER_PORT}") as ws:
            await ws.send(
                serialize(OpenReq(path=self.path, env=self.env, args=self.args))
            )


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
    logging.info(f"Running {' '.join(rsync_args)}")
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
