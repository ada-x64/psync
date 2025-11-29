FROM astral/uv:python3.12-debian-slim

ADD . /app
WORKDIR /app

RUN apt update && apt install -y rsync ssh
RUN service start ssh

COPY <<EOF /etc/ssh/sshd_config
AuthorizedKeysFile /app/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding yes
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
EOF

EXPOSE 22
VOLUME ["/app/rsync"]

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

CMD ["./docker/run-server.sh"]
