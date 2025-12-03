import pytest
from testcontainers.compose.compose import DockerCompose
import os
from pathlib import Path

assets_path = Path(os.path.join(__file__, "..", "assets")).resolve()
root_path = Path(os.path.join(__file__, "..", "..")).resolve()


@pytest.fixture(scope="session", autouse=True)
def server(request: pytest.FixtureRequest):
    """
    Creates the psync server from assets/server.docker-compose.yml
    """
    compose = DockerCompose(
        context=root_path.__str__(),
        compose_file_name=[(assets_path / "server.docker-compose.yml").__str__()],
        keep_volumes=True,
    )

    def cleanup():
        compose.stop(False)

    request.addfinalizer(cleanup)
    return compose.__enter__()
