import threading
import uvicorn
import cv2
import time
from src.main import AccidentDetectionPipeline, load_config
from src.app import app

def run_dashboard():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    # Start dashboard in a separate thread
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()

    print("Dashboard running at http://localhost:8000")

    # Run pipeline in the main thread (better for formatting/GUI events)
    try:
        config = load_config()
        pipeline = AccidentDetectionPipeline(config)
        pipeline.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error running pipeline: {e}")
