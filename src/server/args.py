import argparse
from dataclasses import dataclass
from os import environ
from pathlib import Path

SSL_CERT_PATH: str = environ.get("SSL_CERT_PATH", "~/.local/share/psync/cert.pem")
SSL_KEY_PATH: str = environ.get("SSL_KEY_PATH", "~/.local/share/psync/key.pem")
PSYNC_HOST: str = environ.get("PSYNC_SERVER_IP", "0.0.0.0")
PSYNC_PORT: str = environ.get("PSYNC_SERVER_PORT", "5000")
PSYNC_ORIGINS: str = environ.get("PSYNC_ORIGINS", "localhost 127.0.0.1")
PSYNC_LOG: str = environ.get("PSYNC_LOG", "INFO").upper()
PSYNC_USER: str | None = environ.get("PSYNC_USER", None)


@dataclass
class Args:
    use_base_env: bool
    host: str
    port: str
    origins: list[str]
    user: str | None
    cert_path: Path
    key_path: Path


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
        use_base_env=args["use_base_env"],
        host=PSYNC_HOST,
        port=PSYNC_PORT,
        origins=PSYNC_ORIGINS.split(),
        user=PSYNC_USER,
        cert_path=Path(SSL_CERT_PATH).expanduser(),
        key_path=Path(SSL_KEY_PATH).expanduser(),
    )
    print(args)
