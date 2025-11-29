FROM astral/uv:python3.12-bookworm-slim

ADD . /app
WORKDIR /app

RUN apt update && apt install -y rsync

EXPOSE 22 873
VOLUME ["/app/rsync"]

COPY <<EOF /etc/rsyncd.conf
[psync]
path=/app/rsync
EOF

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

CMD ["./docker/run-server.sh"]
