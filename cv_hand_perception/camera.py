"""
camera.py

Handles video capture interfacing via OpenCV. Provides a CameraManager class 
that wraps hardware connection, manages resolution/FPS settings, and includes
basic error recovery to gracefully handle dropped frames without crashing.

Interactions:
- Hardware: Webcams/Cameras via OpenCV
- Used by: main.py
"""
import cv2
import time

class CameraManager:
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None

    def start(self):
        self.cap = cv2.VideoCapture(self.device_id)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.device_id}")
            return False
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        return True

    def read_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return False, None, None
            
        ret, frame = self.cap.read()
        timestamp = time.time()
        
        if not ret:
            print("Warning: Dropped frame")
            
        return ret, frame, timestamp

    def release(self):
        if self.cap is not None:
            self.cap.release()
