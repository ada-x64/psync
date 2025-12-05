import asyncio
import multiprocessing
import os
from os import PathLike
from os.path import basename
import re
import sys
from signal import Signals
from subprocess import Popen

from testcontainers.compose.compose import (  # pyright: ignore[reportMissingTypeStubs]
    DockerCompose,
)

from client.args import Args as ClientArgs
from client.main import PsyncClient
from client.main import __rsync as rsync  # pyright: ignore[reportPrivateUsage]
from test.conftest import assets_path

SSH_ARGS = (
    f"-i {(assets_path / 'ssh-key').resolve()} -l psync -o StrictHostKeyChecking=no"
)
SSL_CERT_PATH = (assets_path / "cert.pem").resolve().__str__()


def template(args: ClientArgs, server: DockerCompose, kill: bool = False):
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
                assert str(e.code) == str(code)

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

        # check that the pid closed
        stdout, _ = server.get_logs()
        pat = re.compile(r"Running process with PID (\d+)")
        res = pat.search(stdout)
        if res is None:
            raise Exception("Could not get PID from stdout!")
        pid = res.group(1)

        exit, _, _ = server.exec_in_container(
            ["sh", "-c", f"ps -p {pid} > /dev/null; echo $?"],
        )
        assert exit.strip() == "1"

    except Exception as e:
        print(f"Got exception:\n {e}", file=sys.stderr)
        stdout, stderr = server.get_logs()
        print(
            f"Server logs:\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}",
            file=sys.stderr,
        )
        assert False


def get_test_args(file: str):
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
    template(args, server)


def test_sigint(server: DockerCompose):
    args = get_test_args("example.py")
    template(args, server, True)
