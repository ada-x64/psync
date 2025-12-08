import asyncio
import multiprocessing
import os
from os.path import basename
import re
import sys
from signal import Signals
from io import StringIO
from dataclasses import dataclass

from testcontainers.core.generic import DockerContainer  # pyright: ignore[reportMissingTypeStubs]

from client.args import Args as ClientArgs
from client.main import PsyncClient
from client.main import __rsync as rsync  # pyright: ignore[reportPrivateUsage]
from test.conftest import assets_path

OUTFILE = StringIO()


@dataclass
class Logs:
    stdout: str
    stderr: str


def get_logs(server: DockerContainer) -> Logs:
    slogs = server.get_logs()
    return Logs(stdout=slogs[0].decode(), stderr=slogs[1].decode())


def template(args: ClientArgs, server: DockerContainer, kill: bool = False):
    try:
        rsync(args)

        def find(path: str):
            exec_result = server.exec(["ls", str(path)])
            ok = exec_result.output.decode().__contains__(basename(args.target_path))
            if not ok:
                print(f"Could not find path {path}")
                assert False

        find(str(args.destination_path()))
        for file in args.assets:
            find(args.target_path + "/" + file)

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
        logs = get_logs(server)

        pat = re.compile(r"Running process with PID (\d+)")
        res = pat.search(logs.stderr)
        if res is None:
            raise Exception("Could not get PID from stdout!")
        pid = res.group(1)

        client_logs = OUTFILE.getvalue()

        if args.args != []:
            pat = re.compile(r"argv1=\w+")
            res = pat.search(client_logs)
            if res is None:
                raise Exception("Did not find argv1 value!")

        if args.env.get("TEST") is not None:
            pat = re.compile(r"'TEST':\s*'TEST'")
            res = pat.search(client_logs)
            if res is None:
                raise Exception("Env value TEST was not set!")

        exec_result = server.exec(
            ["sh", "-c", f"ps -p {pid} > /dev/null; echo $?"],
        )
        assert exec_result.output.decode().strip() == "1"

    except Exception as e:
        print(f"Got exception:\n {e}", file=sys.stderr)
        logs = get_logs(server)
        print(
            f"Server logs:\n--- stdout ---\n{logs.stdout}\n--- stderr ---\n{logs.stderr}",
            file=sys.stderr,
        )
        print(
            f"OUTFILE:\n--- stdout ---\n{OUTFILE.getvalue()}",
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
        logfile=OUTFILE,
    )


def test_basic(server: DockerContainer):
    args = get_test_args("example_basic.py", server)
    template(args, server)


def test_sigint(server: DockerContainer):
    args = get_test_args("example.py", server)
    template(args, server, True)


def test_env(server: DockerContainer):
    args = get_test_args("example_basic.py", server)
    args.env = {"PYTHONUNBUFERED": "1", "TEST": "TEST"}
    template(args, server)


def test_assets(server: DockerContainer):
    args = get_test_args("example_basic.py", server)
    args.assets = ["./test/assets/wizard.png", "./test/assets/test-dir"]
    template(args, server)


def test_args(server: DockerContainer):
    args = get_test_args("example_basic.py", server)
    args.args = ["test"]
    template(args, server)


def test_full(server: DockerContainer):
    args = get_test_args("example_basic.py", server)
    args.args = ["test"]
    args.assets = ["./test/assets/wizard.png", "./test/assets/test-dir"]
    args.env = {"PYTHONUNBUFERED": "1", "TEST": "TEST"}
    template(args, server)
