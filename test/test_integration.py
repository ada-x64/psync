import asyncio
import multiprocessing
import os
from os.path import basename
import sys
from signal import Signals
from subprocess import Popen

from testcontainers.compose.compose import (
    DockerCompose,  # pyright: ignore[reportMissingTypeStubs]
)

from client.args import Args as ClientArgs
from client.main import PsyncClient  # pyright: ignore[reportPrivateUsage]
from client.main import __rsync as rsync
from test.conftest import assets_path

SSH_ARGS = (
    f"-i {(assets_path / 'ssh-key').resolve()} -l psync -o StrictHostKeyChecking=no"
)
SSL_CERT_PATH = (assets_path / "cert.pem").resolve().__str__()


def template_programmatic(args: ClientArgs, server: DockerCompose, kill: bool = False):
    try:
        rsync(args)
        stdout, _, _ = server.exec_in_container(["ls", str(args.destination_path())])
        print(f"ls {args.destination_path()}\n --- \n {stdout}")
        assert stdout.__contains__(basename(args.target_path))
        client = PsyncClient(args)

        def run(code: int):
            try:
                asyncio.run(client.run())
            except SystemExit as e:
                assert int(e.code) == code

        if not kill:
            run(0)
        else:
            p = multiprocessing.Process(target=run, args=[130])
            p.start()
            while p.pid is None:
                pass
            asyncio.run(asyncio.sleep(1))
            os.kill(p.pid, Signals.SIGINT)
            p.join(3)

    except Exception as e:
        print(f"Got exception:\n {e}", file=sys.stderr)
        stdout, stderr = server.get_logs()
        print(
            f"Server logs:\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}",
            file=sys.stderr,
        )
        assert False


def template(args: ClientArgs, server: DockerCompose, signal: Signals | None = None):
    try:
        process = Popen(
            [
                "env",
                "-S",
                "uv",
                "run",
                "psync-client",
                "-p",
                args.target_path,
                # "-e",
                # args.env,
                # "-a",
                # args.args,
                # "-A",
                # args.assets,
            ],
            env={
                "PSYNC_CERT_PATH": args.ssl_cert_path,
                "PSYNC_SSH_ARGS": args.ssh_args,
                "PSYNC_SERVER_IP": "127.0.0.1",
                "PSYNC_SERVER_PORT": "5000",
                "PSYNC_SSH_PORT": "5022",
            },
        )
        if signal is not None:
            process.send_signal(signal)
            code = process.wait()
            assert code == 130
        else:
            code = process.wait()
            assert code == 0

    except Exception as e:
        print(f"Got exception:\n {e}", file=sys.stderr)
        stdout, stderr = server.get_logs()
        print(
            f"Server logs:\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}",
            file=sys.stderr,
        )
        assert False


def get_test_args(file):
    return ClientArgs(
        target_path=assets_path.joinpath(file).__str__(),
        ssh_args=SSH_ARGS,
        ssl_cert_path=SSL_CERT_PATH,
        server_ip="127.0.0.1",
        server_port=int("5000"),
        server_ssh_port=int("5022"),
    )


def test_basic(server: DockerCompose):
    args = get_test_args("example_basic.py")
    template_programmatic(args, server)


def test_sigint(server: DockerCompose):
    args = get_test_args("example.py")
    template_programmatic(args, server, Signals.SIGINT)
