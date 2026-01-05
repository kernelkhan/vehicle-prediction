"""Quick script to download and convert YOLOv8 to ONNX format."""
import os
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    print("Installing ultralytics...")
    os.system("pip install ultralytics")
    from ultralytics import YOLO

# Create models directory if it doesn't exist
model_dir = Path("models")
model_dir.mkdir(exist_ok=True)

model_path = model_dir / "yolov8_accident.onnx"

print("Downloading YOLOv8n (nano) model...")
# Download YOLOv8n (smallest, fastest for testing)
model = YOLO("yolov8n.pt")

print("Converting to ONNX format...")
# Export to ONNX
model.export(format="onnx", imgsz=640, simplify=True)

# Move the exported model to the expected location
exported_path = Path("yolov8n.onnx")
if exported_path.exists():
    exported_path.rename(model_path)
    print(f"✓ Model saved to: {model_path}")
else:
    print("✗ Export failed. Check ultralytics output above.")

print("\nModel setup complete!")

