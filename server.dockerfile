FROM astral/uv:python3.12-bookworm-slim

ADD . /app
WORKDIR /app

RUN apt update && apt install -y rsync

COPY <<EOF /etc/rsyncd.conf
    [psync]
    path=/app/rsync
EOF

RUN rsync --daemon
RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uv", "run", "psync-server"]
