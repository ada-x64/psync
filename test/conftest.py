from loguru import logger
import pytest
from testcontainers.compose.compose import DockerCompose  # pyright: ignore[reportMissingTypeStubs]
import os
from pathlib import Path
import logging
from common.log import InterceptHandler

assets_path = Path(os.path.join(__file__, "..", "assets")).resolve()
root_path = Path(os.path.join(__file__, "..", "..")).resolve()

log_level = os.environ.get("PSYNC_LOG", "DEBUG").upper()
logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)
logger.remove()


@pytest.fixture(scope="function", autouse=True)
def server(request: pytest.FixtureRequest):
    """
    Creates the psync server from assets/server.docker-compose.yml
    """
    compose = DockerCompose(
        context=root_path.__str__(),
        compose_file_name=[(assets_path / "docker-compose.yml").__str__()],
        services=["psync-server"],
    )

    def cleanup():
        compose.stop(True)

    request.addfinalizer(cleanup)
    return compose.__enter__()
