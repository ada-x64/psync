from subprocess import Popen
from loguru import logger
import pytest
import os
from pathlib import Path
import logging

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HealthcheckWaitStrategy
from common.log import InterceptHandler

assets_path = Path(os.path.join(__file__, "..", "assets")).resolve()
root_path = Path(os.path.join(__file__, "..", "..")).resolve()

log_level = os.environ.get("PSYNC_LOG", "DEBUG").upper()
logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)
logger.remove()



@pytest.fixture(scope="session", autouse=True)
def build_server():
    exit = Popen(
        [
            "docker",
            "build",
            (root_path),
            "-f",
            "docker/server/Dockerfile",
            "-t",
            "psync-server:latest",
        ]
    ).wait()
    assert exit == 0
    return None


@pytest.fixture(scope="function", autouse=True)
def server(request: pytest.FixtureRequest, build_server):
    container = DockerContainer(
        image="psync-server:latest",
        ports=[5000, 5022],
        env={"PSYNC_ORIGINS": "172.26.0.1 127.0.0.1 localhost"},
        volumes=[
            (str(assets_path / "cert.pem"), "/app/cert.pem", "ro"),
            (str(assets_path / "key.pem"), "/app/key.pem", "ro"),
            (str(assets_path / "ssh-key.pub"), "/app/authorized_keys.src", "ro"),
        ],
    )

    def cleanup():
        container.stop(True)

    request.addfinalizer(cleanup)
    container = container.start()
    HealthcheckWaitStrategy().wait_until_ready(container)
    return container
