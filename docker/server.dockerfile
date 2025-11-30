FROM astral/uv:python3.12-bookworm-slim

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

USER root
CMD ["docker/run-server.sh"]
