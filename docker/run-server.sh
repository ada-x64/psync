#!/bin/bash
mkdir -p /home/psync/.ssh
chmod 700 /home/psync/.ssh
chown psync:psync /home/psync/.ssh
cp /app/authorized_keys.src /home/psync/.ssh/authorized_keys
chmod 600 /home/psync/.ssh/authorized_keys
chown psync:psync /home/psync/.ssh/authorized_keys

/usr/sbin/sshd -D -e & uv run psync-server $1
