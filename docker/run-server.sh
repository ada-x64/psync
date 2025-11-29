#!/bin/bash
set -xe
rsync --daemon
uv run psync-server
