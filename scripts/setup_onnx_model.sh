#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${PROJECT_ROOT}/models"
MODEL_NAME="yolov8n.pt"
ONNX_NAME="yolov8_accident.onnx"

mkdir -p "${MODEL_DIR}"
cd "${MODEL_DIR}"

if [ ! -f "${MODEL_NAME}" ]; then
  echo "[+] Downloading YOLOv8n model..."
  curl -L -o "${MODEL_NAME}" "https://github.com/ultralytics/assets/releases/download/v0.0.0/${MODEL_NAME}"
fi

echo "[+] Converting model to ONNX (optimized for Raspberry Pi)..."
source "${PROJECT_ROOT}/.venv/bin/activate"
python - <<'PYTHON'
from ultralytics import YOLO
import onnx
import onnxoptimizer

model_path = "yolov8n.pt"
onnx_path = "yolov8_accident.onnx"

model = YOLO(model_path)
model.export(format="onnx", imgsz=640, opset=12, simplify=True, device="cpu", half=False, optimize=True, fuses=True)

model = onnx.load(onnx_path)
passes = onnxoptimizer.get_available_passes()
model = onnxoptimizer.optimize(model, passes)
onnx.save(model, onnx_path)
print("[+] ONNX model optimized and saved.")
PYTHON

echo "[+] Model setup complete."

