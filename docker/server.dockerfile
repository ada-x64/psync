FROM astral/uv:python3.12-bookworm-slim

ADD . /app
WORKDIR /app

RUN apt update && apt install -y rsync ssh
RUN service ssh start

COPY <<EOF /etc/ssh/sshd_config
AuthorizedKeysFile /app/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding yes
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
PermitRootLogin yes
EOF

RUN echo "root:root" | chpasswd

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "psync-server"]
