# How the Accident Risk Prediction System Works

This document explains the technical architecture and logic of the "Accident Risk Monitor" system you are running.

## 1. System Overview

The system processes video in real-time to detect vehicles, analyze their motion, and predict potential accidents before they happen. It combines computer vision (YOLOv8) with kinematic analysis (Physics) to flag dangerous driving behaviors.

### Core Components:

1.  **Video Stream Ingestion**: Reads video frames from a file or camera.
2.  **Object Detection (AI)**: Identifies cars, trucks, buses, motorcycles, and people.
3.  **Multi-Object Tracking (MOT)**: Assigns a unique ID to each detected object and follows it across frames.
4.  **Motion Analysis (Physics)**: Calculates speed, acceleration, and direction for every tracked object.
5.  **Risk Engine (Heuristics)**: Evaluates the motion data against safety rules to assign a "Risk Score".
6.  **Alerting & Dashboard**: Visualizes the results and sends notifications.

---

## 2. Detailed Pipeline Steps

### Step 1: Object Detection (The "Eyes")
-   **Model**: YOLOv8n (Nano) optimized for speed.
-   **Process**: Every frame is resized and fed into the neural network.
-   **Output**: Bounding boxes (coordinates) and class labels (e.g., "Car", "Bus") for all objects in the scene.

### Step 2: Tracking (The "Memory")
-   **Algorithm**: ByteTrack + Kalman Filter + Hungarian Algorithm.
-   **Why it's needed**: YOLO only sees "boxes" in a single image. The tracker connects box A in frame 1 to box A in frame 2.
-   **Improvement**: We use the *Hungarian Algorithm* to optimally match boxes based on their position and overlap (IoU), ensuring IDs don't swap even when cars cross paths.

### Step 3: Motion Feature Extraction (The "Brain")
-   **Velocity**: Calculated by measuring how many pixels an object moves per second. Smoothed over 5 frames to reduce camera jitter noise.
-   **Acceleration**: The rate of change of velocity. High negative acceleration = **Sudden Braking**.
-   **Lateral Drift**: Movement perpendicular to the main direction of travel. High drift = **Swerving/Lane Change**.

### Step 4: Risk Engine Assessment (The "Judge")
The system assigns a risk level (Low/Medium/High/Critical) based on these rules:
-   **Sudden Deceleration**: If a car slows down faster than `150 px/s²`, it flags a "panic stop".
-   **Time-to-Collision (TTC)**: Calculates if two objects are on a collision course. If `Time < 1.0s`, it triggers a CRITICAL alert.
-   **Swerving**: Sudden heading changes > 45 degrees.
-   **Proximity**: Following too closely at high speed.

### Step 5: Visualization (The "Display")
-   **Dynamic Coloring**:
    -   **Green**: Safe.
    -   **Yellow**: Caution.
    -   **Orange**: High Risk.
    -   **Red**: Critical Danger.
-   **Dashboard**: A React-like web interface (HTML/JS) that polls the backend API for new events and updates the UI in real-time.

---

## 3. Accuracy Improvements Made

To ensure high accuracy for your specific video:
1.  **Smoothed Velocity**: We now average motion over 5 frames instead of 2. This filters out the "shaking" of the camera or bounding box jitter.
2.  **Tuned Thresholds**: We increased the "Deceleration" threshold to `150.0`. This means minor slowing down (like normal traffic) is ignored, but *slamming on the brakes* is detected.
3.  **Advanced Matching**: Switched to a linear sum assignment tracker to prevent "ghost" tracks from appearing when cars overlap.

## 4. How to Interpret the Dashboard
-   **Live Feed**: Shows the raw video analysis. Boxes = tracked objects. Text = risk status.
-   **Event Log**: A historical record of every "High" or "Critical" event.
-   **Map**: Shows the GPS location of the incident (if GPS provided, otherwise simulates location).

This architecture allows the system to act as an automated "safety supervisor" for traffic monitoring.
