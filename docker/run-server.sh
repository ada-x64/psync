#!/bin/bash
ssh-keygen -A
mkdir -p /home/psync/.ssh
chmod 700 /home/psync/.ssh
chown psync:psync /home/psync/.ssh
cp /app/authorized_keys.src /home/psync/.ssh/authorized_keys

mkdir -p /home/psync/.local/share/psync
cp /app/key.pem /home/psync/.local/share/psync/key.pem
cp /app/cert.pem /home/psync/.local/share/psync/cert.pem
chown psync:psync /home/psync/.local/share/psync -R

chmod 600 /home/psync/.ssh/authorized_keys
chown psync:psync /home/psync/.ssh/authorized_keys

/usr/sbin/sshd -D -e &

UV_CACHE_DIR="/home/psync/.cache/uv"
HOME=/home/psync
source /app/.venv/bin/activate
su psync -pc "uv run psync-server $1"
