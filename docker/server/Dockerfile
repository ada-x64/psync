FROM astral/uv:debian-slim

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

RUN useradd -ms /bin/bash psync && passwd -d psync
RUN chown psync:psync /app -R

USER psync
RUN uv sync --locked


COPY --from=ghcr.io/vi/websocat:latest /usr/local/bin/websocat /usr/local/bin/websocat

HEALTHCHECK --interval=5s\
    CMD ["sh", "-c", "exit $([ $(echo 'hc' | /usr/local/bin/websocat -k -1 wss://0.0.0.0:5000) = 'ok' ])"]

USER root
CMD ["docker/run-server.sh"]
