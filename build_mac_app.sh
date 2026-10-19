#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"

if [[ ! -f xxxx.py || ! -f mars_app.py || ! -f 题库.xlsx ]]; then
  print -u2 '缺少源码或题库文件。'
  exit 1
fi

if [[ ! -x .mac-build-venv/bin/python ]]; then
  uv venv --python 3.12 .mac-build-venv
fi
uv pip install --python .mac-build-venv/bin/python -r requirements.txt 'pyinstaller>=6.10,<7'
.mac-build-venv/bin/python build_desktop.py
