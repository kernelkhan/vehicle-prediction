# Testing Guide: Sample Outputs & Video Suggestions

## 📹 Recommended Test Videos

### **Best Options (Free & Easy to Find):**

1. **Traffic Intersection Videos**
   - Search YouTube: "traffic intersection camera" or "road traffic monitoring"
   - Why: Multiple vehicles, pedestrians, clear movement patterns
   - What to look for: Sudden stops, lane changes, close following

2. **Dashcam Accident Compilations**
   - Search: "dashcam accidents compilation" or "near miss compilation"
   - Why: Real-world scenarios with sudden events
   - What to look for: Sudden braking, collisions, swerving

3. **Highway Traffic Videos**
   - Search: "highway traffic camera" or "motorway traffic"
   - Why: High-speed scenarios, multiple lanes
   - What to look for: High velocity, sudden lane changes

4. **Pedestrian Crossing Videos**
   - Search: "pedestrian crossing traffic" or "crosswalk camera"
   - Why: Mix of vehicles and pedestrians
   - What to look for: Low TTC, sudden stops

### **Where to Download:**
- **YouTube**: Use `yt-dlp` or online converters
- **Pexels Videos**: https://www.pexels.com/videos/ (free, high quality)
- **Pixabay**: https://pixabay.com/videos/ (free stock videos)
- **Your own dashcam footage**: Best for real-world testing

### **Video Requirements:**
- Format: MP4, AVI, MOV (any format OpenCV supports)
- Resolution: 640x480 or higher
- Duration: 30 seconds to 5 minutes (longer = more events)
- Content: Should have moving vehicles/pedestrians

---

## 📊 Sample Output Structure

### **1. Event Log (`data/logs/events.json`)**

```json
[
  {
    "event_id": "20250114153022_track3",
    "timestamp": "2025-01-14T15:30:22.543Z",
    "risk_level": "high",
    "risk_score": 0.75,
    "track_id": 3,
    "class_name": "car",
    "confidence": 0.89,
    "reasons": [
      "sudden deceleration (8.2 m/s²)",
      "low TTC (2.1s)",
      "high velocity (15.3 m/s)"
    ],
    "location": {
      "latitude": 28.6139,
      "longitude": 77.2090,
      "source": "mock"
    },
    "snapshot_path": "data/media/snapshots/20250114_153022_track3.jpg",
    "clip_path": "data/media/clips/20250114_153022_track3.mp4"
  },
  {
    "event_id": "20250114153045_track7",
    "timestamp": "2025-01-14T15:30:45.821Z",
    "risk_level": "critical",
    "risk_score": 0.92,
    "track_id": 7,
    "class_name": "truck",
    "confidence": 0.94,
    "reasons": [
      "critical TTC (0.9s)",
      "sudden deceleration (12.5 m/s²)",
      "trajectory convergence"
    ],
    "location": {
      "latitude": 28.6139,
      "longitude": 77.2090,
      "source": "mock"
    },
    "snapshot_path": "data/media/snapshots/20250114_153045_track7.jpg",
    "clip_path": "data/media/clips/20250114_153045_track7.mp4"
  }
]
```

### **2. Saved Files Structure**

```
data/
├── media/
│   ├── snapshots/
│   │   ├── 20250114_153022_track3.jpg    (High-risk event snapshot)
│   │   ├── 20250114_153045_track7.jpg    (Critical event snapshot)
│   │   └── ...
│   └── clips/
│       ├── 20250114_153022_track3.mp4    (10-12 sec video clip)
│       ├── 20250114_153045_track7.mp4    (10-12 sec video clip)
│       └── ...
└── logs/
    ├── events.json                       (All events log)
    └── pipeline.log                      (System logs)
```

### **3. Console Output (Terminal 1 - Detection Pipeline)**

```
[INFO] Pipeline started. Press Ctrl+C to exit.
[INFO] Detected 3 objects: [car(0.89), person(0.76), bicycle(0.82)]
[INFO] Tracking: 3 active tracks
[WARNING] High risk detected: Track ID 3, Score: 0.75
[INFO] Event saved: 20250114_153022_track3
[INFO] Snapshot saved: data/media/snapshots/20250114_153022_track3.jpg
[INFO] Clip saved: data/media/clips/20250114_153022_track3.mp4
[CRITICAL] Critical risk detected: Track ID 7, Score: 0.92
[INFO] Event saved: 20250114_153045_track7
```

### **4. Dashboard Output (Terminal 2 - Web Server)**

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     127.0.0.1:52341 "GET / HTTP/1.1" 200 OK
INFO:     127.0.0.1:52341 "GET /static/css/main.css HTTP/1.1" 200 OK
INFO:     127.0.0.1:52342 "GET /api/events HTTP/1.1" 200 OK
INFO:     127.0.0.1:52343 "GET /static/js/stream.js HTTP/1.1" 200 OK
```

---

## ✅ What to Look For (Proof It's Working)

### **1. Visual Indicators on Video:**
- ✅ Green bounding boxes around detected objects
- ✅ Track IDs displayed (e.g., "car:3", "person:5")
- ✅ Risk level labels: "HIGH", "MEDIUM", "LOW" above objects
- ✅ Real-time updates as objects move

### **2. File System Evidence:**
```powershell
# Check if events are being saved
Get-Content data\logs\events.json | ConvertFrom-Json | Select-Object -First 5

# Check saved snapshots
dir data\media\snapshots

# Check saved video clips
dir data\media\clips
```

### **3. Dashboard Evidence:**
- ✅ Live video feed showing detections
- ✅ Risk status indicator (HIGH/MEDIUM/LOW)
- ✅ Event timeline with timestamps
- ✅ Map view (if GPS data available)
- ✅ Event count increasing over time

### **4. Console Logs:**
- ✅ Detection messages: "Detected X objects"
- ✅ Risk warnings: "High risk detected"
- ✅ Save confirmations: "Event saved", "Snapshot saved"

---

## 🎬 Specific Video Scenarios to Test

### **Scenario 1: Sudden Braking**
- **What to use**: Video with vehicle suddenly stopping
- **Expected output**: 
  - Risk level: HIGH
  - Reason: "sudden deceleration"
  - Snapshot + clip saved

### **Scenario 2: Close Following**
- **What to use**: Video with vehicles very close together
- **Expected output**:
  - Risk level: HIGH/CRITICAL
  - Reason: "low TTC", "high closing speed"
  - Multiple events logged

### **Scenario 3: Intersection Traffic**
- **What to use**: Busy intersection with multiple vehicles
- **Expected output**:
  - Multiple tracks (cars, buses, pedestrians)
  - Various risk levels
  - Multiple events over time

### **Scenario 4: Pedestrian Near Miss**
- **What to use**: Video with pedestrian crossing, vehicle approaching
- **Expected output**:
  - Risk level: CRITICAL
  - Reason: "critical TTC", "trajectory convergence"
  - Both vehicle and pedestrian tracked

---

## 📝 Quick Test Checklist

- [ ] Video loads and plays in detection pipeline
- [ ] Objects detected (bounding boxes visible)
- [ ] Objects tracked (IDs remain consistent)
- [ ] Risk levels displayed (HIGH/MEDIUM/LOW)
- [ ] Events saved to `data/logs/events.json`
- [ ] Snapshots saved to `data/media/snapshots/`
- [ ] Video clips saved to `data/media/clips/`
- [ ] Dashboard shows live feed
- [ ] Dashboard shows event timeline
- [ ] API endpoints return data (`/api/events`)

---

## 🔗 Quick Download Commands

### **Using yt-dlp (if installed):**
```powershell
# Install yt-dlp first
pip install yt-dlp

# Download a traffic video
yt-dlp "https://www.youtube.com/watch?v=VIDEO_ID" -o test_video.mp4
```

### **Or use online converters:**
1. Find a YouTube video
2. Use: https://www.y2mate.com/ or similar
3. Download as MP4
4. Place in `D:\Vehicle\` folder
5. Update `.env`: `VIDEO_SOURCE=test_video.mp4`

---

## 💡 Pro Tips

1. **Start with short videos** (30-60 seconds) to test quickly
2. **Use videos with clear, moving objects** (better detection)
3. **Check console output** for real-time feedback
4. **Monitor `events.json`** to see events being logged
5. **Use dashboard** to visualize everything together

---

## 📸 Sample Screenshots to Capture

1. **Detection window** showing bounding boxes and risk labels
2. **Dashboard** showing event timeline
3. **File explorer** showing saved snapshots/clips
4. **Event log** showing JSON structure
5. **Console output** showing detection messages

These prove the system is working end-to-end!

