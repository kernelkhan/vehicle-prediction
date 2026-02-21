# 🚀 What Else You Can Do - Complete Guide

## 1. 🌐 **Use the Web Dashboard** (Recommended!)

The dashboard provides a visual interface to view all your events, live stream, and analytics.

### Start the Dashboard:
```powershell
# In a NEW terminal window
cd D:\Vehicle
.\.venv\Scripts\Activate.ps1
uvicorn src.app:app --host 127.0.0.1 --port 8000 --reload
```

### Access the Dashboard:
- **Main Dashboard**: http://127.0.0.1:8000
- **Events Page**: http://127.0.0.1:8000/events
- **API Health**: http://127.0.0.1:8000/api/health
- **Events API**: http://127.0.0.1:8000/api/events

### Dashboard Features:
- ✅ Live video stream with detections
- ✅ Event timeline with all incidents
- ✅ Risk level indicators (HIGH/MEDIUM/LOW)
- ✅ Map view (if GPS data available)
- ✅ Event statistics and analytics
- ✅ Download/view snapshots and clips

---

## 2. ⚙️ **Customize Detection Settings**

Edit `.env` file to adjust sensitivity and behavior:

### Adjust Risk Thresholds:
```env
# Make detection more sensitive (lower thresholds)
RISK_VELOCITY_HIGH=10.0        # Default: 12.0 m/s
RISK_DECELERATION_HIGH=5.0     # Default: 6.0 m/s²
RISK_TTC_CRITICAL=2.0          # Default: 1.5 seconds

# Make detection less sensitive (higher thresholds)
RISK_VELOCITY_HIGH=15.0
RISK_DECELERATION_HIGH=8.0
RISK_TTC_CRITICAL=1.0
```

### Adjust Detection Confidence:
```env
# More detections (lower threshold)
MODEL_CONF_THRESHOLD=0.35       # Default: 0.45

# Fewer detections (higher threshold)
MODEL_CONF_THRESHOLD=0.60
```

### Change Video Settings:
```env
# Resolution
STREAM_RESOLUTION_WIDTH=1920
STREAM_RESOLUTION_HEIGHT=1080

# Frame rate
STREAM_FPS=30

# Display live video window
DISPLAY_STREAM=true
```

---

## 3. 📹 **Process Multiple Videos**

### Option A: Create a Batch Processing Script
Create `process_videos.ps1`:
```powershell
$videos = @("video11.mp4", "video2.mp4", "video3.mp4")

foreach ($video in $videos) {
    Write-Host "Processing $video..."
    (Get-Content .env) -replace 'VIDEO_SOURCE=.*', "VIDEO_SOURCE=$video" | Set-Content .env
    python -m src.main
    Start-Sleep -Seconds 2
}
```

### Option B: Process All Videos in Folder
```powershell
Get-ChildItem *.mp4 | ForEach-Object {
    Write-Host "Processing $($_.Name)..."
    (Get-Content .env) -replace 'VIDEO_SOURCE=.*', "VIDEO_SOURCE=$($_.Name)" | Set-Content .env
    python -m src.main
}
```

---

## 4. 📊 **Analyze Your Results**

### View Event Statistics:
```powershell
# Count total events
python -c "import json; data = json.load(open('data/logs/events.json')); print(f'Total events: {len(data[\"events\"])}')"

# Count by risk level
python -c "import json; from collections import Counter; data = json.load(open('data/logs/events.json')); levels = [e['risk_level'] for e in data['events']]; print(Counter(levels))"

# Find highest risk events
python -c "import json; data = json.load(open('data/logs/events.json')); sorted_events = sorted(data['events'], key=lambda x: x['risk_score'], reverse=True); [print(f\"{e['event_id']}: {e['risk_score']} - {', '.join(e['reasons'])}\") for e in sorted_events[:10]]"
```

### Generate Summary Report:
```powershell
# Create a summary
python -c "
import json
from collections import Counter
from datetime import datetime

data = json.load(open('data/logs/events.json'))
events = data['events']

print('=== EVENT SUMMARY ===')
print(f'Total Events: {len(events)}')
print(f'Risk Levels: {dict(Counter(e[\"risk_level\"] for e in events))}')
print(f'Average Risk Score: {sum(e[\"risk_score\"] for e in events) / len(events):.2f}')
print(f'\nTop 5 Highest Risk Events:')
for e in sorted(events, key=lambda x: x['risk_score'], reverse=True)[:5]:
    print(f\"  {e['event_id']}: Score {e['risk_score']:.2f} - {', '.join(e['reasons'])}\")
"
```

---

## 5. 🔔 **Set Up Alerts** (SMS/WhatsApp/Email)

### Configure Twilio for SMS/WhatsApp:
1. Sign up at https://www.twilio.com
2. Get your Account SID and Auth Token
3. Update `.env`:
```env
SMS_ENABLED=true
WHATSAPP_ENABLED=true
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
SMS_FROM=+1234567890
SMS_TO=+0987654321
WHATSAPP_FROM=whatsapp:+1234567890
WHATSAPP_TO=whatsapp:+0987654321
```

### Configure Email Alerts:
```env
EMAIL_TO=your-email@example.com
```

---

## 6. ☁️ **Set Up Firebase Integration**

1. Create a Firebase project at https://console.firebase.google.com
2. Download credentials JSON file
3. Update `.env`:
```env
FIREBASE_CREDENTIALS_PATH=path/to/firebase-credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
```

This will:
- Upload events to Firebase Realtime Database
- Store snapshots and clips in Firebase Storage
- Enable cloud-based dashboard access

---

## 7. 🎥 **Use Live Camera Feed**

Instead of video files, use your webcam:

```powershell
# Use webcam (usually camera 0)
(Get-Content .env) -replace 'VIDEO_SOURCE=.*', 'VIDEO_SOURCE=0' | Set-Content .env
python -m src.main
```

Or use an RTSP stream:
```env
VIDEO_SOURCE=rtsp://username:password@ip:port/stream
```

---

## 8. 🗺️ **Add GPS Location Tracking**

If you have a USB GPS module:
1. Connect it to your computer
2. Update `.env`:
```env
USE_GPS=true
GPS_PORT=COM3  # Windows COM port
GPS_BAUDRATE=9600
```

The system will tag all events with GPS coordinates.

---

## 9. 📱 **View Events on Mobile**

If running on a network:
1. Find your computer's IP address:
   ```powershell
   ipconfig | findstr IPv4
   ```
2. Start dashboard with:
   ```powershell
   uvicorn src.app:app --host 0.0.0.0 --port 8000
   ```
3. Access from mobile: `http://YOUR_IP:8000`

---

## 10. 🧪 **Run Tests**

Test individual components:
```powershell
# Run all tests
pytest

# Test specific module
pytest tests/test_detection.py
pytest tests/test_tracking.py
pytest tests/test_risk_engine.py
```

---

## 11. 📈 **Export Data for Analysis**

### Export to CSV:
```powershell
python -c "
import json
import csv

data = json.load(open('data/logs/events.json'))
with open('events_export.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['event_id', 'timestamp', 'risk_level', 'risk_score', 'reasons'])
    writer.writeheader()
    for e in data['events']:
        writer.writerow({
            'event_id': e['event_id'],
            'timestamp': e['timestamp'],
            'risk_level': e['risk_level'],
            'risk_score': e['risk_score'],
            'reasons': '; '.join(e['reasons'])
        })
print('Exported to events_export.csv')
"
```

---

## 12. 🎨 **Customize Detection Classes**

Edit `models/detector_labels.txt` or update config to detect specific objects:
- person
- bicycle
- car
- motorcycle
- bus
- truck

---

## 13. 🔧 **Troubleshooting & Optimization**

### Improve Performance:
```env
# Lower resolution for faster processing
STREAM_RESOLUTION_WIDTH=640
STREAM_RESOLUTION_HEIGHT=480
STREAM_FPS=15

# Reduce detection confidence for faster inference
MODEL_CONF_THRESHOLD=0.50
```

### Debug Mode:
Check logs in `data/logs/` directory for detailed information.

---

## 14. 📚 **Explore the Code**

Key files to explore:
- `src/main.py` - Main pipeline
- `src/risk/risk_engine.py` - Risk calculation logic
- `src/detection/detector.py` - YOLO detection
- `src/tracking/tracker.py` - Object tracking
- `config/config.py` - Configuration system

---

## 15. 🎯 **Quick Commands Reference**

```powershell
# Switch video
(Get-Content .env) -replace 'VIDEO_SOURCE=.*', 'VIDEO_SOURCE=video2.mp4' | Set-Content .env

# View latest events
Get-Content data\logs\events.json -Tail 20

# Count saved files
(dir data\media\snapshots).Count
(dir data\media\clips).Count

# Open folders
explorer data\media\snapshots
explorer data\media\clips

# Start dashboard
uvicorn src.app:app --host 127.0.0.1 --port 8000 --reload

# Run detection
python -m src.main
```

---

## 🎉 **Recommended Next Steps:**

1. **Start the dashboard** - See your events visually
2. **Process more videos** - Test with different scenarios
3. **Adjust thresholds** - Fine-tune for your use case
4. **Set up alerts** - Get notified of incidents
5. **Analyze results** - Generate reports and statistics

Happy detecting! 🚗💨

