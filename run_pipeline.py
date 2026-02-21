#!/usr/bin/env python3
"""
Script to run the accident detection pipeline with a video file.
"""
import os
import sys
from pathlib import Path

# Set the video source before importing the config
os.environ['VIDEO_SOURCE'] = 'video3.mp4'

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.config import load_config
from src.main import AccidentDetectionPipeline

if __name__ == '__main__':
    config = load_config()
    print(f"Running pipeline with video source: {config.stream.video_source}")
    print(f"Resolution: {config.stream.resolution}")
    print(f"FPS: {config.stream.fps}")
    
    pipeline = AccidentDetectionPipeline(config)
    pipeline.run()
