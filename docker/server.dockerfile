FROM astral/uv:python3.12-bookworm-slim

ADD . /app
WORKDIR /app

RUN apt update && apt install -y rsync ssh

COPY <<EOF /etc/ssh/sshd_config
AuthorizedKeysFile /app/authorized_keys
PasswordAuthentication no
Subsystem sftp /usr/lib/openssh/sftp-server
PermitRootLogin yes
EOF

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
RUN mkdir -p /run/sshd /app/rsync \
    && chmod 755 /run/sshd /app/rsync \
    && chown root:root /run/sshd

CMD ["bash", "-c", "cp /app/authorized_keys.src /app/authorized_keys; /usr/sbin/sshd -D -e & uv run psync-server;"]
