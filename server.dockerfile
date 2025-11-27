FROM astral/uv:python3.12-bookworm-slim

ADD . /app
WORKDIR /app
RUN uv sync --locked
CMD ["uv", "run", "server"]
