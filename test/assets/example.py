#!/usr/local/bin/uv run
import datetime

print("hi")
while True:
    time = datetime.datetime.now()
    diff = datetime.datetime.now() - time
    while diff.seconds < 1:
        diff = datetime.datetime.now() - time
    print("tick")
