import csv
import os
import time

class Logger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(self.log_dir, f"hand_telemetry_{timestamp_str}.csv")
        
        self.headers = [
            "timestamp", 
            "hand_detected", 
            "confidence", 
            "handedness",
            "thumb_curl", "thumb_angle",
            "index_curl", "index_angle",
            "middle_curl", "middle_angle",
            "ring_curl", "ring_angle",
            "pinky_curl", "pinky_angle",
            "gesture_label"
        ]
        
        with open(self.filepath, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)

    def log(self, state, gesture_label="unknown"):
        row = [
            state.get("timestamp", 0.0),
            state.get("hand_detected", False),
            state.get("confidence", 0.0),
            state.get("handedness", "Unknown"),
        ]
        
        if state.get("hand_detected") and "fingers" in state:
            fingers = state["fingers"]
            for finger in ["thumb", "index", "middle", "ring", "pinky"]:
                if finger in fingers:
                    row.append(fingers[finger].get("curl", 0.0))
                    row.append(fingers[finger].get("angle", 0.0))
                else:
                    row.extend([0.0, 0.0])
        else:
            row.extend([0.0] * 10) # 5 fingers * 2 values
            
        row.append(gesture_label)
        
        with open(self.filepath, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

