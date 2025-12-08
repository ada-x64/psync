#!/usr/bin/env -S uv run --script
import datetime

while True:
    time = datetime.datetime.now()
    diff = datetime.datetime.now() - time
    while diff.seconds < 1:
        diff = datetime.datetime.now() - time
    print("tick")
