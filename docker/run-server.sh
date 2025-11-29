#!/bin/bash
set -xe
rsync --daemon -vv --no-detach &
uv run psync-server
