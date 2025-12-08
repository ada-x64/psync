import argparse
from dataclasses import dataclass, field
import hashlib
import logging
import os
from os.path import basename
from pathlib import Path
import shlex
from common.data import deserialize_env
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from _typeshed import SupportsWrite
    Logfile = SupportsWrite[str] | Path | None
else:
    Logfile = Any


@dataclass
class Args:
    """
    Client arguments.
    """

    target_path: str
    """
    ``--path -p <target_path>``

    **Required.** Path to the target executable.
    """

    assets: list[str] = field(default_factory=list)
    """
    ``--assets -A <env>``

    Extra files or directories to be synced to the destination path.
    """

    env: dict[str, str] = field(default_factory=dict)
    """
    ``--env -e <env>``

    Space separated list of environment variables which will be passed to the executable.
    """

    args: list[str] = field(default_factory=list)
    """
    ``--args -a <args>``

    Arguments passed to the executable.
    """

    server_ip: str = os.environ.get("PSYNC_SERVER_IP", "127.0.0.1")
    """
    environ: ``PSYNC_SERVER_IP``

    Server IP address.
    """

    server_port: int = int(os.environ.get("PSYNC_SERVER_PORT", "5000"))
    """
    environ: ``PSYNC_SERVER_PORT``

    Server port.
    """

    server_ssh_port: int = int(os.environ.get("PSYNC_SSH_PORT", "5022"))
    """
    environ: ``PSYNC_SSH_PORT``

    SSH port on the server host. Client must be authenticated with a shared public key.
    """

    ssh_args: str = os.environ.get("PSYNC_SSH_ARGS", "-l psync")
    """
    environ: ``PSYNC_SSH_ARGS``

    Arguments passed to SSH. Under the hood, psync runs
    ``rsync -e "/usr/bin/ssh {PSYNC_SSH_ARGS} -p {PSYNC_SSH_PORT}"``
    """

    server_dest: str = os.environ.get("PSYNC_SERVER_DEST", "/home/psync")
    """
    environ: ``PSYNC_SERVER_DEST``

    Base path on the server where the files should be synced.
    """

    ssl_cert_path: str = os.environ.get(
        "PSYNC_CERT_PATH", "~/.local/share/psync/cert.pem"
    )
    """
    environ: ``PSYNC_CERT_PATH``

    Public SSL certificate used to trust the psync server.
    """

    client_origin: str = os.environ.get("PSYNC_CLIENT_ORIGIN", "127.0.0.1")
    """
    environ: ``PSYNC_CLIENT_ORIGIN``

    Domain name. Should match the origins set in the server's ``PSYNC_ORIGINS``
    variable.
    """

    logfile: Logfile = None
    """
    environ: ``PSYNC_LOG_FILE``

    Optional file where the executable's logs will be output.
    """

    def project_hash(self) -> str:
        """
        Hash value generated from the target path. Used as the directory name for the project.
        """
        return hashlib.blake2s(self.target_path.encode(), digest_size=8).hexdigest()

    def rsync_url(self) -> str:
        """
        {server_ip}:{server_dest}/{project_hash}
        """
        return f"{self.server_ip}:{self.server_dest}/{self.project_hash()}/"

    def destination_path(self) -> Path:
        """
        {server_dest}/{project_hash}/{basename(target_path)}
        """
        return Path(self.server_dest) / self.project_hash() / basename(self.target_path)


parser = argparse.ArgumentParser(
    prog="psync-client",
    usage="""\
Client for the psync server.

In addition to the options below, the client is configurable through environment
variables.

Variable            | Default
--------------------+-------------------------------
PSYNC_SERVER_IP     | 127.0.0.1
PSYNC_SERVER_PORT   | 5000
PSYNC_SSH_PORT      | 5022
PSYNC_SERVER_DEST   | /home/psync/
PSYNC_SSH_ARGS      | -l psync
PSYNC_CERT_PATH     | ~/.local/share/psync/cert.pem
PSYNC_CLIENT_ORIGIN | 127.0.0.1
PSYNC_LOG_FILE      | None (stdout)

SSH arguments will be append with "-p {PSYNC_SSH_PORT}"

For more info, please read the docs:
    https://psync.readthedocs.io/
""",
)
_action = parser.add_argument(
    "--path",
    "-p",
    required=True,
    help="Path to the target exectuable.",
)
_action = parser.add_argument(
    "--assets",
    "-A",
    nargs="+",
    help="Extra files or directories to be synced to the destination path.",
)
_action = parser.add_argument(
    "--env",
    "-e",
    help="Environment variables to set in the remote execution environment. Variables must be space-sepated or double-quoted.",
)
_action = parser.add_argument(
    "--args", "-a", help="Arguments passed to the executable."
)


def parse_args() -> Args:
    args = vars(parser.parse_args())

    target_path = str(args.get("path"))
    target_path = Path(target_path)
    if not target_path.is_file():
        logging.error(f"Could not file at {target_path}")
        exit(1)

    extra: list[str] = []
    extra_raw = args.get("extra")
    if extra_raw is not None:
        extra = extra_raw  # pyright: ignore[reportAny]

    client_args: list[str] = []
    raw_args = args.get("args")
    if raw_args is not None:
        client_args = shlex.split(str(raw_args))  # pyright: ignore[reportAny]

    env: dict[str, str] = dict()
    raw_env = args.get("env")
    if raw_env is not None:
        env = deserialize_env(f"env='{raw_env}'")

    return Args(
        target_path=str(target_path),
        assets=extra or [],
        env=env,
        args=client_args,
    )
