from testcontainers.compose.compose import DockerCompose
from testcontainers.core.wait_strategies import HttpWaitStrategy


def test_ws_connection(server: DockerCompose):
    print("spins_up")
    server.waiting_for(
        HttpWaitStrategy(5000)
        .using_tls()
        .with_header("Connection", "Upgrade")
        .with_header("Upgrade", "websocket")
        .for_status_code(101)
    )
    assert True


def test_pass(server: DockerCompose):
    print("pass")
