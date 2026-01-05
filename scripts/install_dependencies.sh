#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN=${PYTHON_BIN:-python3}

echo "[+] Updating system packages..."
sudo apt-get update
sudo apt-get install -y python3-dev python3-venv python3-pip libatlas-base-dev \
    libhdf5-dev libatlas-base-dev libjpeg-dev zlib1g-dev libgtk-3-dev \
    libavcodec-dev libavformat-dev libswscale-dev liblapack-dev gfortran \
    libssl-dev libffi-dev git

echo "[+] Creating Python virtual environment..."
if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
  ${PYTHON_BIN} -m venv "${PROJECT_ROOT}/.venv"
fi
source "${PROJECT_ROOT}/.venv/bin/activate"

echo "[+] Upgrading pip..."
pip install --upgrade pip wheel setuptools

echo "[+] Installing Python requirements..."
pip install -r "${PROJECT_ROOT}/requirements.txt"

echo "[+] Installation complete."

