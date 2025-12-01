FROM x11docker/xserver

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=ghcr.io/ada-x64/psync-server /etc/ssh/sshd_config /etc/ssh/sshd_config

RUN useradd -ms /bin/bash psync && passwd -d psync
ADD . /app
WORKDIR /app

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

RUN mkdir -p /run/sshd \
    && chmod 755 /run/sshd \
    && chown root:root /run/sshd

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

USER root
CMD ["docker/run-server.sh"]
