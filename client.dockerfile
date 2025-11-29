FROM astral/uv:python3.12-bookworm-slim

ADD . /app
WORKDIR /app
RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uv", "run", "psync-client"]
