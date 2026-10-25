#!/usr/bin/env python3
"""Fail CI if embedded Python heredocs in deployment scripts have bad syntax.

bash -n only parses the shell wrapper and cannot see syntax errors inside
\`<<'PY'\` blocks; this checker covers that deployment failure mode.
"""
import ast
import pathlib
import re
import sys

FILES = [
    "ops/install-xhttp-lab-foreign.sh",
    "ops/install-xhttp-lab-iran.sh",
    "ops/install-naive-lab-iran.sh",
    "ops/resume-naive-lab-iran.sh",
    "ops/repair-naive-connect-foreign.sh",
]
START = re.compile(r"<<-?\s*(?:'PY'|\"PY\"|PY)(?:\s|$)")
failures = 0
for file in FILES:
    path = pathlib.Path(file)
    if not path.exists():
        print(f"ERROR: {file} is missing")
        failures += 1
        continue
    source = path.read_text()
    lines = source.splitlines()
    count = 0
    i = 0
    while i < len(lines):
        if not START.search(lines[i]):
            i += 1
            continue
        opening = i
        i += 1
        start = i
        while i < len(lines) and lines[i].strip() != "PY":
            i += 1
        if i >= len(lines):
            print(f"ERROR: {file}:{opening+1}: unterminated Python heredoc")
            failures += 1
            break
        block = "\n".join(lines[start:i]) + "\n"
        try:
            ast.parse(block, filename=f"{file} (heredoc at {opening+1})")
        except SyntaxError as exc:
            print(f"ERROR: {file}:{opening+1}: embedded Python syntax: {exc}")
            failures += 1
        count += 1
        i += 1
    if not count:
        print(f"ERROR: {file}: no Python heredoc found; review syntax contract")
        failures += 1
    else:
        print(f"{file}: {count} Python heredoc(s) syntax checked")
if failures:
    raise SystemExit(f"CI failed: {failures} embedded Python error(s)")
print("All embedded Python deployment blocks: syntax PASS")
