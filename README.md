## Smart Vision-Based Accident Prediction & Emergency Dispatch System

End-to-end Raspberry Pi solution for real-time traffic incident prediction, detection, and emergency dispatch automation. Combines YOLOv8 object detection, multi-object tracking (ByteTrack), motion analytics, IMU jerk sensing, GPS tagging, and multi-channel alerting with a FastAPI-powered dashboard.

### Hardware Overview
- Raspberry Pi 4 (4GB+ recommended), active cooling, 64GB microSD
- Pi Camera v2 (or USB camera)
- Optional sensors:
  - MPU-6050 IMU (I2C) for jerk detection
  - USB GPS receiver (serial) or smartphone hotspot GPS share
  - HC-SR04 ultrasonic for proximity (future use)
  - Buzzer/LED driver for on-device alarms

### Project Layout
- `src/` core services (detection, tracking, risk engine, alert manager, sensors)
- `config/` configuration helpers (`env.example` → copy to `.env`)
- `web/` FastAPI templates, static assets, mock data
- `scripts/` setup helpers for dependencies, ONNX conversion, dashboard launch
- `diagrams/` ASCII architecture & data-flow diagrams
- `tests/` unit tests for deterministic components

### Quick Start
1. **Clone & install dependencies**
   ```bash
   git clone <repo-url> smart-vision-accident-system
   cd smart-vision-accident-system
   chmod +x scripts/*.sh
   ./scripts/install_dependencies.sh
   ```
2. **Configure environment**
   ```bash
   cp config/env.example .env
   # edit .env (Twilio, Firebase, GPS, hardware toggles, paths)
   ```
3. **Prepare YOLOv8 ONNX**
   ```bash
   ./scripts/setup_onnx_model.sh
   ```
   > Requires internet + `ultralytics` package. Script exports an optimized `models/yolov8_accident.onnx`.

4. **Run perception pipeline**
   ```bash
   source .venv/bin/activate
   python -m src.main
   ```

5. **Launch dashboard**
   ```bash
   ./scripts/run_dashboard.sh
   ```
   Access via `http://<pi-ip>:8000` on LAN. `http://<pi-ip>:8000/events` for logs.

### Configuration Reference
Key `.env` parameters (full list in `config/env.example`):
- `VIDEO_SOURCE`: camera index or RTSP/HTTP stream URL
- `DISPLAY_STREAM`: set `true` for HDMI preview window
- `SMS_ENABLED`, `WHATSAPP_ENABLED`: toggle alert channels
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `SMS_FROM`, `SMS_TO`, etc.
- `FIREBASE_*`: credentials JSON path, realtime DB URL, storage bucket
- `USE_IMU`, `USE_GPS`: hardware toggles (fallbacks auto-enable mock data)
- `MEDIA_DIR`, `LOG_DIR`: storage roots (auto-created)

Pydantic settings also support direct overrides via environment variables using nested keys (see `config/config.py`).

### Core Runtime Flow
1. Frames captured via OpenCV → YOLOv8 ONNX detection → ByteTrack tracking.
2. Motion feature extractor derives velocity, acceleration, heading change, lateral drift.
3. TTC estimator computes converging trajectories per tracked pair.
4. Risk engine scores incidents (sudden decel, low TTC, jerk, freeze detection).
5. Alert manager captures snapshot/clip (ring buffer), records GPS, dispatches SMS/WhatsApp, syncs to Firebase, appends local log.
6. FastAPI dashboard streams annotated MJPEG feed, event timeline, Leaflet map.

Diagrams: see `diagrams/architecture.txt` & `diagrams/data_flow.txt`.

### Testing & Simulation
Use mock data when hardware unavailable:
- `web/assets/mock_events.json` populates dashboard timeline.
- Configure `VIDEO_SOURCE` to point at `data/samples/sample_video.mp4` (provide your clip).
- IMU/GPS handlers gracefully fall back to simulated values with warning logs.

Run tests:
```bash
source .venv/bin/activate
pytest
```

### Troubleshooting
- **Low FPS / Thermal throttling**: ensure active cooling, reduce resolution (e.g. 640x480), drop FPS to 15, switch to YOLOv8n or quantized variant.
- **ONNX runtime errors**: confirm `onnxruntime` ARM build; fallback to CPU provider by editing `.env`.
- **Twilio alerts failing**: verify sandbox configuration for WhatsApp, ensure outbound internet.
- **Firebase upload blocked**: service account JSON must have storage + database permissions; bucket region should match.
- **No GPS lock**: check serial permissions (`sudo usermod -a -G dialout $USER`), fallback IP geolocation triggered automatically.

### Deployment Tips
- Enable `systemd` services for `src.main` and `run_dashboard.sh`.
- Use `tmux` or `supervisor` for resilience.
- Rotate logs via `logrotate` if running long term.
- For remote dashboard access, use SSH tunneling or secure reverse proxies.

### Roadmap Hooks
- `src/sensors/ultrasonic_handler.py`: integrate obstacle-aware TTC adjustments.
- `alert/notifier.py`: extend with MQTT/ESP32 triggers, in-vehicle CAN bus integration.
- Edge TPU / NPU acceleration by providing alternative ONNX runtime providers.

---
**License & Safety Notice**: Intended as driver-assist telemetry. Not a substitute for human supervision or certified ADAS systems. Validate thoroughly before field deployment.

