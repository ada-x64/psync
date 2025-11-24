import argparse
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shlex
from common.data import deserialize_env


@dataclass
class Args:
    target_path: str
    dest_path: str
    extra: list[str]
    env: dict[str, str]
    args: list[str]


parser = argparse.ArgumentParser(
    prog="psync-client", description="Client for the psync server."
)
_action = parser.add_argument(
    "--path",
    "-p",
    required=True,
    help="Path to the target exectuable.",
)
_action = parser.add_argument(
    "--extra",
    "-E",
    nargs="+",
    help="Extra files or directories to be synced to the destination path.",
)
_action = parser.add_argument(
    "--env",
    "-e",
    help="Environment variables to set in the remote execution environment. Variables must be space-sepated or double-quoted.",
)
_action = parser.add_argument(
    "--args", "-a", help="Arguments with which to run the remote executable."
)

SERVER_IP: str = os.environ.get("PSYNC_SERVER_IP", "127.0.0.1")
SERVER_PORT: int = int(os.environ.get("PSYNC_SERVER_PORT", "5000"))
USER = os.environ.get("PSYNC_SSH_USER", "")


def parse_args() -> Args:
    args = vars(parser.parse_args())

    target_path = str(args.get("path"))
    target_path = Path(target_path)
    if not target_path.is_file():
        logging.error(f"Could not file at {target_path}")
        exit(1)

    val_hash = hash(os.getcwd())
    dest_path = f"~/.local/share/psync/{val_hash}/"

    extra: list[str] = []
    extra_raw = args.get("extra")
    if extra_raw is not None:
        extra = extra_raw

    client_args: list[str] = []
    raw_args = args.get("args")
    if raw_args is not None:
        client_args = shlex.split(str(raw_args))  # pyright: ignore[reportAny]

    env: dict[str, str] = dict()
    raw_env = args.get("args")
    if raw_env is not None:
        env = deserialize_env(str(raw_env))  # pyright: ignore[reportAny]

    return Args(
        target_path=str(target_path),
        dest_path=dest_path,
        extra=extra or [],
        env=env,
        args=client_args,
    )
