# 🚗 Smart Vision-Based Accident Prediction & Emergency Dispatch System

A comprehensive, real-time traffic incident prediction and monitoring system powered by Computer Vision and AI. This system runs on edge devices (like Raspberry Pi) or standard PCs to detect vehicles, analyze their behavior, and predict accidents before they happen.

---

## 📖 Table of Contents
1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features)
3. [System Architecture](#-system-architecture)
4. [Project Structure](#-project-structure)
5. [Installation & Setup](#-installation--setup)
6. [Configuration](#-configuration)
7. [Running the System](#-running-the-system)
8. [Dashboard & Visualization](#-dashboard--visualization)
9. [Testing & Scenarios](#-testing--scenarios)
10. [Troubleshooting](#-troubleshooting)

---

## 🔭 Project Overview

This project is an end-to-end solution designed to improve road safety by automatically detecting hazardous driving behaviors. It uses **YOLOv8** for object detection and **ByteTrack** for multi-object tracking. By analyzing the motion trajectories of vehicles, the system calculates risk metrics like **Time-to-Collision (TTC)** and **Jerks (Sudden Acceleration/Deceleration)** to flag potential accidents.

When a high-risk event is detected, the system:
1.  Logs the event detailed metadata.
2.  Captures a purely visual snapshot and video clip.
3.  Triggers alerts (SMS/WhatsApp) via Twilio.
4.  Updates a real-time web dashboard.

---

## ✨ Key Features

-   **Real-time Object Detection**: Identifies Cars, Trucks, Buses, Motorbikes, and Pedestrians using YOLOv8.
-   **Multi-Object Tracking**: Robustly tracks vehicles across frames using ByteTrack + Kalman Filtering, handling occlusions and crossing paths.
-   **Advanced Risk Analysis**:
    -   **Collision Prediction**: Calculates TTC (Time-to-Collision) for converging trajectories.
    -   **Anomaly Detection**: Identifies sudden braking, swerving, and erratic steering events.
    -   **Stationary Vehicle Detection**: Flags stalled vehicles in active lanes.
-   **Emergency Alerting**: Automated SMS and WhatsApp notifications with location data.
-   **Interactive Dashboard**:
    -   Live video feed with bounding boxes and risk annotations.
    -   Real-time event timeline and historical logs.
    -   GPS mapping of incidents.
-   **Edge Optimized**: Designed to run efficiently on Raspberry Pi 4/5 or standard CPUs.

---

## 🏗 System Architecture

The system operates as a pipeline of synchronized modules:

1.  **Input**: Video stream (Camera, RTSP, or File).
2.  **Detection (The "Eyes")**: YOLOv8n scans frames for vehicles/people.
3.  **Tracking (The "Memory")**: ByteTrack assigns stable IDs to objects to follow them over time.
4.  **Feature Extraction (The "Brain")**:
    -   Computes Velocity (px/s → km/h), Acceleration, and Heading.
    -   Smoothes data over 5 frames to reduce jitter.
5.  **Risk Engine (The "Judge")**:
    -   Evaluates physics data against safety thresholds.
    -   Rules: Sudden Deceleration (>150px/s²), TTC < 1.0s, Swerving.
6.  **Response**:
    -   **AlertManager**: Saves media, sends alerts, updates database.
    -   **Dashboard**: Visualizes the live state via FastAPI & WebSockets.

---

## 📂 Project Structure

```
d:\Vehicle\
├── config/                 # Configuration files
│   ├── env.example         # Template for environment variables
│   └── config.py           # Pydantic configuration models
├── data/                   # Runtime data storage
│   ├── media/              # Saved snapshots and clips of accidents
│   ├── logs/               # JSON event logs and system logs
│   └── samples/            # Sample videos for testing
├── diagrams/               # Architecture diagrams
├── models/                 # AI Models (YOLOv8 ONNX/PT files)
├── scripts/                # Utility scripts (install, run, setup)
├── src/                    # Source Code
│   ├── app.py              # FastAPI Dashboard entry point
│   ├── main.py             # Core Pipeline entry point
│   ├── detection/          # YOLOv8 integration
│   ├── tracking/           # ByteTrack implementation
│   ├── risk/               # Physics & Risk Logic
│   ├── storage/            # File & Database handlers
│   └── lib/                # Shared utilities
├── web/                    # Frontend Dashboard
│   ├── templates/          # HTML templates
│   └── static/             # CSS/JS assets
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## ⚙ Installation & Setup

### Prerequisites
-   **OS**: Windows 10/11, Linux (Ubuntu/Raspbian), or macOS.
-   **Python**: Version 3.8 to 3.11.
-   **Hardware**: Webcam (for live) or Video File (for testing).

### Windows Setup Guide

1.  **Clone the Repository**
    ```powershell
    git clone <repository-url>
    cd Vehicle
    ```

2.  **Set PowerShell Policy** (Run as Admin)
    Allows script execution for virtual environments.
    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```

3.  **Create & Activate Virtual Environment**
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

4.  **Install Dependencies**
    ```powershell
    pip install -r requirements-windows.txt
    ```
    *Note: Use `requirements.txt` for Linux/Raspberry Pi.*

5.  **Setup the Model**
    Downloads/exports the YOLOv8 model to ONNX format.
    ```powershell
    python setup_model.py
    ```

---

## 🔧 Configuration

The system uses a `.env` file for all settings.

1.  **Create `.env`**
    ```powershell
    cp config\env.example .env
    ```

2.  **Edit `.env` (Key Settings)**
    Open `.env` in a text editor:

    -   **Input Source**:
        ```ini
        # '0' for webcam, or path to video file
        VIDEO_SOURCE=data/samples/traffic.mp4
        ```
    -   **Alert Configuration** (Optional):
        ```ini
        TWILIO_ACCOUNT_SID=your_sid
        TWILIO_AUTH_TOKEN=your_token
        SMS_TO=+1234567890
        ```
    -   **Hardware Toggles**:
        ```ini
        USE_IMU=false       # Set true only if MPU6050 is connected
        USE_GPS=false       # Set true only if GPS module is connected
        ```

---

## 🚀 Running the System

You generally run two components: the **Backend Pipeline** (for processing) and the **Dashboard** (for viewing).

### 1. Run the Detection Pipeline
Processes video, detects risks, and saves events.
```powershell
# Ensure venv is activated
python run_pipeline.py
```
*Press `q` in the video window to stop.*

### 2. Run the Dashboard
Starts the Web UI to view the stream and alerts.
```powershell
python -m src.app
```
*Access at: http://localhost:8000*

---

## 📊 Dashboard & Visualization

The web dashboard provides a comprehensive view of the system's status:

-   **Live Stream**: Shows the video with real-time bounding boxes.
    -   **Green Box**: Safe object.
    -   **Yellow**: Warning/Caution.
    -   **Red**: Critical/Danger.
-   **Event Log**: Sidebar list of all detected incidents. Click an event to view its details.
-   **Status Indicators**: Shows current system health (FPS, Connectivity).

---

## 🧪 Testing & Scenarios

To verify the system is working, you can use sample videos.

### Common Test Scenarios
1.  **Sudden Braking**:
    -   *Input*: Video of a car stopping abruptly.
    -   *Expected Result*: Risk level "High", alerts "Sudden Deceleration", visual indicator turns Red.
2.  **Tailgating / Low TTC**:
    -   *Input*: Car following another very closely at speed.
    -   *Expected Result*: Risk Level "Critical", "Time-to-Collision < 2s".
3.  **Stationary Vehicle**:
    -   *Input*: Car stopped in a moving lane.
    -   *Expected Result*: "Stationary Vehicle Detected" warning.

### Verifying Outputs
Check the `data/` folder for generated evidence:
-   `data/logs/events.json`: Text log of the incident.
-   `data/media/snapshots/`: JPG images of the moment of detection.
-   `data/media/clips/`: Short MP4 clips leading up to the event.

---

## ❓ Troubleshooting

**Q: I get "ModuleNotFoundError: No module named 'numpy'"**
A: Ensure your virtual environment is activated (`.venv\Scripts\Activate`) and you installed requirements.

**Q: The video is very slow / low FPS.**
A:
-   Resize the input video to 640x480 or lower.
-   Switch to `yolov8n.onnx` (Nano model) which is fastest.
-   Disable `DISPLAY_STREAM` in `.env` if running headless.

**Q: Dashboard shows no video.**
A: Ensure the pipeline (`run_pipeline.py`) is running. The dashboard relies on the pipeline to generate the visuals/data, or ensure `src/app.py` is configured to stream directly if using the integrated mode.

**Q: Alerts are not sending.**
A: Check your Twilio credentials in `.env`. Ensure you have internet connectivity.

---

## 🔮 Roadmap

-   [ ] **Night Mode**: Enhanced model training for low-light conditions.
-   [ ] **Multi-Camera Support**: Fusing data from multiple feeds.
-   [ ] **Hardware Integration**: CAN-bus support for reading real vehicle speed data.
-   [ ] **Cloud Sync**: Automatic upload of critical events to cloud storage.

---
**License**: MIT
**Disclaimer**: This system is for driver assistance and research. Always maintain control of your vehicle.
