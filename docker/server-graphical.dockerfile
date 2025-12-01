FROM ghcr.io/ada-x64/psync-server

USER root

# Install psync deps and bevy deps as basic setup
RUN apt update && apt install -y \
    rsync ssh \
    g++ \
    pkg-config \
    libx11-dev \
    libasound2-dev \
    libudev-dev \
    libxkbcommon-x11-0 \
    libwayland-dev \
    libxkbcommon-dev

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

USER root
CMD ["docker/run-server.sh"]
