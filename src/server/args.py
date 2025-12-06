import argparse
from dataclasses import dataclass, field
from os import environ
from pathlib import Path


@dataclass
class Args:
    """
    Server arguments.
    """

    use_base_env: bool
    """
    flag: ``--use-base-env, -E``

    Use the current environment in addition to the values specified in the websocket request.
    """
    cert_path: Path = Path(
        environ.get("PSYNC_SSL_CERT_PATH", "~/.local/share/psync/cert.pem")
    ).expanduser()
    """
    environ: ``PSYNC_SSL_CERT_PATH``

    Path to the SSL certificate used to authenticate this server.
    """
    key_path: Path = Path(
        environ.get("PSYNC_SSL_KEY_PATH", "~/.local/share/psync/key.pem")
    ).expanduser()
    """
    environ: ``PSYNC_SSL_KEY_PATH``

    Path to the SSL private key.
    """
    host: str = environ.get("PSYNC_SERVER_IP", "0.0.0.0")
    """
    environ: ``PSYNC_SERVER_IP``

    Host IP on which to listen for incoming connections.
    """
    port: str = environ.get("PSYNC_SERVER_PORT", "5000")
    """
    environ: ``PSYNC_SERVER_PORT``

    Host port on which to listen for incoming connections.
    """
    origins: list[str] = field(
        default_factory=lambda: environ.get(
            "PSYNC_ORIGINS", "localhost 127.0.0.1"
        ).split()
    )
    """
    environ: ``PSYNC_ORIGINS``

    Accepted client origins. Should match the HTTP Origin header.
    """
    log_level: str = environ.get("PSYNC_LOG_LEVEL", "INFO").upper()
    """
    environ: ``PSYNC_LOG_LEVEL``

    Log level.
    """
    user: str | None = environ.get("PSYNC_USER", None)
    """
    environ: ``PSYNC_USER``

    User used to execute the requested binaries.
    """


parser = argparse.ArgumentParser(
    prog="psync-server",
    usage="""\
Server for project syncrhonization.

In addition to the options below, the client is configurable through environment
variables.

SSL_CERT_PATH - Path to SSL cert
    Default: ./cert.pem
SSL_KEY_PATH - Path to SSL key
    Default: ./key.pem
PSYNC_SERVER_IP - IP address on which to listen
    Default: 0.0.0.0
PSYNC_SERVER_PORT - Port on which to listen
    Default: 5000
PSYNC_ORIGINS - Space-separated list of accepted incoming IP addresses
    Default: "127.0.0.1 localhost"
PSYNC_LOG - Log level
    Default: "INFO"
PSYNC_USER - User to run the synced executables. Try not to use root.
    Default: None (current user)
""",
)
_action = parser.add_argument(
    "--use-base-env",
    "-E",
    help="Use the current environment in addition to the requested values.",
    action="store_true",
)


def parse_args() -> Args:
    args = vars(parser.parse_args())
    return Args(
        use_base_env=args["use_base_env"],  # pyright: ignore[reportAny]
    )
