import sys
from loguru import logger
import pytest
from testcontainers.compose.compose import DockerCompose
import os
from pathlib import Path
import logging
from common.log import InterceptHandler

assets_path = Path(os.path.join(__file__, "..", "assets")).resolve()
root_path = Path(os.path.join(__file__, "..", "..")).resolve()

log_level = os.environ.get("PSYNC_LOG", "DEBUG").upper()
logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)
logger.remove()

@pytest.fixture(scope="session", autouse=True)
def server(request: pytest.FixtureRequest):
    """
    Creates the psync server from assets/server.docker-compose.yml
    """
    compose = DockerCompose(
        context=root_path.__str__(),
        compose_file_name=[(assets_path / "server.docker-compose.yml").__str__()],
    )

    def cleanup():
        compose.stop(True)

    request.addfinalizer(cleanup)
    return compose.__enter__()
