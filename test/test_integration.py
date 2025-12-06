import asyncio
import multiprocessing
import os
from os.path import basename
import re
import sys
from signal import Signals

from testcontainers.core.generic import DockerContainer  # pyright: ignore[reportMissingTypeStubs]

from client.args import Args as ClientArgs
from client.main import PsyncClient
from client.main import __rsync as rsync  # pyright: ignore[reportPrivateUsage]
from test.conftest import assets_path


def template(args: ClientArgs, server: DockerContainer, kill: bool = False):
    try:
        rsync(args)
        exec_result = server.exec(["ls", str(args.destination_path())])
        print(f"ls {args.destination_path()}\n --- \n {exec_result.output}")
        assert exec_result.output.decode().__contains__(basename(args.target_path))
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
        stdout, stderr = server.get_logs()
        pat = re.compile(r"Running process with PID (\d+)")
        res = pat.search(stderr.decode())
        if res is None:
            raise Exception("Could not get PID from stdout!")
        pid = res.group(1)

        exec_result = server.exec(
            ["sh", "-c", f"ps -p {pid} > /dev/null; echo $?"],
        )
        assert exec_result.output.decode().strip() == "1"

    except Exception as e:
        print(f"Got exception:\n {e}", file=sys.stderr)
        stdout, stderr = server.get_logs()
        print(
            f"Server logs:\n--- stdout ---\n{stdout.decode()}\n--- stderr ---\n{stderr.decode()}",
            file=sys.stderr,
        )
        assert False


def get_test_args(file: str, server: DockerContainer):
    return ClientArgs(
        target_path=assets_path.joinpath(file).__str__(),
        ssh_args=f"-i {(assets_path / 'ssh-key').resolve()} -l psync -o StrictHostKeyChecking=no",
        ssl_cert_path=(assets_path / "cert.pem").resolve().__str__(),
        server_ip="127.0.0.1",
        server_port=server.get_exposed_port(5000),
        server_ssh_port=server.get_exposed_port(5022),
    )


def test_basic(server: DockerContainer):
    args = get_test_args("example_basic.py", server)
    template(args, server)


def test_sigint(server: DockerContainer):
    args = get_test_args("example.py", server)
    template(args, server, True)
