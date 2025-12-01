FROM astral/uv:debian-slim

ADD . /app
WORKDIR /app

USER root

RUN apt update && apt install -y \
    rsync ssh \
    g++ \
    pkg-config \
    libx11-dev \
    libasound2-dev \
    libudev-dev \
    libxkbcommon-x11-0 \
    libwayland-dev \
    libxkbcommon-dev \
    libwayland-client0 \
    libasound2-dev \
    mesa-utils \
    mesa-utils-extra

COPY <<EOF /etc/ssh/sshd_config
PasswordAuthentication no
Subsystem sftp /usr/lib/openssh/sftp-server
Port 5022
EOF
RUN mkdir -p /run/sshd \
    && chmod 755 /run/sshd \
    && chown root:root /run/sshd

RUN useradd -ms /bin/bash psync && passwd -d psync
RUN chown psync:psync /app -R

USER psync
RUN uv sync --locked

USER root
CMD ["docker/run-server.sh", "-E"]
