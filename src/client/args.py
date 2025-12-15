import argparse
from dataclasses import dataclass, field
import hashlib
import logging
import os
from os.path import basename
from pathlib import Path
import shlex
from common.data import deserialize_env
from pprint import PrettyPrinter
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from _typeshed import SupportsWrite
    Logfile = SupportsWrite[str] | Path | None
else:
    Logfile = Any

pprint = PrettyPrinter().pformat

ENV_DEFAULTS = {
    "server_ip": os.environ.get("PSYNC_SERVER_IP", "127.0.0.1"),
    "server_port": os.environ.get("PSYNC_SERVER_PORT", "5000"),
    "server_ssh_port": os.environ.get("PSYNC_SSH_PORT", "5022"),
    "ssh_args": os.environ.get("PSYNC_SSH_ARGS", "-l psync"),
    "server_dest": os.environ.get("PSYNC_SERVER_DEST", "/home/psync"),
    "cert_path": os.environ.get(
           "PSYNC_CERT_PATH", "~/.local/share/psync/cert.pem"
       ),
    "client_origin": os.environ.get("PSYNC_CLIENT_ORIGIN", "127.0.0.1"),
    "log_file": os.environ.get("PSYNC_LOG_FILE", "")
}

@dataclass
class Args:
    """
    Client arguments.
    """

    target_path: str
    """
    ``<target_path>``

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

    server_ip: str = ENV_DEFAULTS["server_ip"]
    """
    environ: ``PSYNC_SERVER_IP``

    Server IP address.
    """

    server_port: int = int(ENV_DEFAULTS["server_port"])
    """
    environ: ``PSYNC_SERVER_PORT``

    Server port.
    """

    server_ssh_port: int = int(ENV_DEFAULTS["server_ssh_port"])
    """
    environ: ``PSYNC_SSH_PORT``

    SSH port on the server host. Client must be authenticated with a shared public key.
    """

    ssh_args: str = ENV_DEFAULTS["ssh_args"]
    """
    environ: ``PSYNC_SSH_ARGS``

    Arguments passed to SSH. Under the hood, psync runs
    ``rsync -e "/usr/bin/ssh {PSYNC_SSH_ARGS} -p {PSYNC_SSH_PORT}"``
    """

    server_dest: str = ENV_DEFAULTS["server_dest"]
    """
    environ: ``PSYNC_SERVER_DEST``

    Base path on the server where the files should be synced.
    """

    ssl_cert_path: str = ENV_DEFAULTS["cert_path"]
    """
    environ: ``PSYNC_CERT_PATH``

    Public SSL certificate used to trust the psync server.
    """

    client_origin: str = ENV_DEFAULTS["client_origin"]
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
    usage="psync [OPTIONS] <target_path>",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=f"""\
Client for the psync server.

In addition to the options above, the client is configurable through environment
variables.

Variable            | Current value
--------------------+-------------------------------
PSYNC_SERVER_IP     | {ENV_DEFAULTS["server_ip"]}
PSYNC_SERVER_PORT   | {ENV_DEFAULTS["server_port"]}
PSYNC_SSH_PORT      | {ENV_DEFAULTS["server_ssh_port"]}
PSYNC_SERVER_DEST   | {ENV_DEFAULTS["server_dest"]}
PSYNC_SSH_ARGS      | {ENV_DEFAULTS["ssh_args"]}
PSYNC_CERT_PATH     | {ENV_DEFAULTS["cert_path"]}
PSYNC_CLIENT_ORIGIN | {ENV_DEFAULTS["client_origin"]}
PSYNC_LOG_FILE      | {ENV_DEFAULTS["log_file"]}

SSH arguments will be append with "-p PSYNC_SSH_PORT"
For more info, please read the docs: <https://psync.readthedocs.io/>\
""",
)
_action = parser.add_argument(
    "path",
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
    nargs="+"
)
_action = parser.add_argument(
    "--args", "-a", help="Arguments passed to the executable.", nargs="+"
)


def parse_args(input: list[str] | None = None) -> Args:
    args = vars(parser.parse_args(input))

    target_path = str(args.get("path"))
    target_path = Path(target_path)
    if not target_path.is_file():
        logging.error(f"Could not file at {target_path}")
        exit(1)

    assets: list[str] = []
    assets_raw = args.get("assets")
    if assets_raw is not None:
        assets = shlex.split(" ".join(assets_raw))
    logging.debug(f"ASSETS: {assets_raw} -> {assets}")

    client_args: list[str] = []
    raw_args = args.get("args")
    if raw_args is not None:
        client_args = shlex.split(' '.join(raw_args))
    logging.debug(f"ARGS: {raw_args} -> {client_args}")

    env: dict[str, str] = dict()
    raw_env = args.get("env")
    if raw_env is not None:
        env = deserialize_env(f"env='{" ".join(raw_env)}'")
    logging.debug(f"ENV: {raw_env} -> {env}")

    ret = Args(
        target_path=str(target_path),
        assets=assets or [],
        env=env,
        args=client_args,
    )
    logging.debug(pprint(ret))
    return ret
