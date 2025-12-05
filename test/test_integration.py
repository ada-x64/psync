import sys
from testcontainers.compose.compose import DockerCompose  # pyright: ignore[reportMissingTypeStubs]
from client.main import PsyncClient, __rsync as rsync  # pyright: ignore[reportPrivateUsage]
from client.args import Args as ClientArgs
from test.conftest import assets_path
import asyncio

SSH_ARGS = (
    f"-i {(assets_path / 'ssh-key').resolve()} -l psync -o StrictHostKeyChecking=no"
)
SSL_CERT_PATH = (assets_path / "cert.pem").resolve().__str__()


def template(args: ClientArgs, server: DockerCompose):
    try:
        rsync(args)
        stdout, _, _ = server.exec_in_container(["ls", str(args.destination_path())])
        print(f"ls {args.destination_path()}\n --- \n {stdout}")
        assert stdout.__contains__("example.py")
        client = PsyncClient(args)
        asyncio.run(client.run())

    except Exception as e:
        print(f"Got exception:\n {e}", file=sys.stderr)
        stdout, stderr = server.get_logs()
        print(
            f"Server logs:\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}",
            file=sys.stderr,
        )
        assert False


def test_basic(server: DockerCompose):
    args = ClientArgs(
        target_path=assets_path.joinpath("example.py").__str__(),
        ssh_args=SSH_ARGS,
        ssl_cert_path=SSL_CERT_PATH,
    )
    template(args, server)
