#!/bin/bash

date
echo "PATH: ${PATH}"

cd "$(dirname "$0")" || exit
SCRIPT_DIR="$(pwd)"
echo "SCRIPT_DIR: ${SCRIPT_DIR}"

source venv/bin/activate

python3 "${SCRIPT_DIR}/main.py"
