#!/usr/bin/env -S uv run --script

import sys
import os

try:
    print(f"argv1={sys.argv[1]}")
except Exception:
    pass

print("--- ENVIRON ---")
print(os.environ)
