FROM astral/uv:debian-slim

RUN useradd -ms /bin/bash psync && passwd -d psync
USER psync
ADD . /app
WORKDIR /app

USER root

RUN apt update && apt install -y rsync ssh

COPY <<EOF /etc/ssh/sshd_config
PasswordAuthentication no
Subsystem sftp /usr/lib/openssh/sftp-server
Port 5022
EOF
RUN mkdir -p /run/sshd \
    && chmod 755 /run/sshd \
    && chown root:root /run/sshd

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

USER psync
CMD ["docker/run-server.sh"]
