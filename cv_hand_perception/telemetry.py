"""
telemetry.py

Handles high-frequency performance and state logging. Streams raw frame data, 
latency metrics, and filter flags to JSON Lines (JSONL) files. Aggregates data into
session summaries to track long-term stability and detection rates.

Interactions:
- Writes to: logs/*.jsonl, test_reports/summary_*.json
- Used by: main.py
"""
import os
import json
import time
from datetime import datetime

class TelemetryLogger:
    def __init__(self, log_dir="logs", operator_name="unknown"):
        self.log_dir = log_dir
        self.operator_name = operator_name
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(self.log_dir, f"telemetry_{self.session_id}.jsonl")
        
        # We use JSONL (JSON Lines) for continuous streaming to disk
        self.log_file = open(self.filepath, mode='w', encoding='utf-8')

    def log_frame(self, state, process_time_ms):
        """
        Logs a single frame's state and processing latency in JSON format.
        """
        entry = {
            "timestamp": state.get("timestamp", time.time()),
            "operator_name": self.operator_name,
            "latency_ms": process_time_ms,
            "hand_detected": state.get("hand_detected", False),
            "confidence": state.get("confidence", 0.0),
            "handedness": state.get("handedness", "Unknown"),
            "fingers": state.get("fingers", {})
        }
        
        # Add telemetry flags if available (from features.py)
        # Note: In main.py we'll need to make sure these flags are passed through
        
        self.log_file.write(json.dumps(entry) + "\n")
        self.log_file.flush() # Ensure it's written even if app crashes

    def close(self):
        if self.log_file:
            self.log_file.close()

class SessionSummaryLogger:
    """
    Aggregates data over a fixed test interval for tuning and stability tracking.
    """
    def __init__(self, filter_params, operator_name="unknown"):
        self.filter_params = filter_params
        self.operator_name = operator_name
        self.reset()

    def reset(self):
        self.start_time = time.time()
        self.frames = 0
        self.latencies = []
        self.detection_events = 0
        self.lost_tracking_events = 0
        self.prev_hand_detected = False
        
        self.pip_clamps = 0
        self.dip_clamps = 0
        self.coupling_overrides = 0

    def record_frame(self, hand_detected, latency_ms, telemetry_flags=None):
        self.frames += 1
        self.latencies.append(latency_ms)
        
        if hand_detected:
            self.detection_events += 1
            if telemetry_flags:
                for finger, flags in telemetry_flags.items():
                    if flags.get("pip_clamped"): self.pip_clamps += 1
                    if flags.get("dip_clamped"): self.dip_clamps += 1
                    if flags.get("coupling_triggered"): self.coupling_overrides += 1
        
        if self.prev_hand_detected and not hand_detected:
            self.lost_tracking_events += 1
            
        self.prev_hand_detected = hand_detected

    def save_summary(self, log_dir="test_reports"):
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        duration = time.time() - self.start_time
        fps = self.frames / max(duration, 0.001)
        avg_latency = sum(self.latencies) / max(len(self.latencies), 1)
        det_rate = (self.detection_events / max(self.frames, 1)) * 100.0
        
        summary = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "operator_name": self.operator_name,
            "filter_params": self.filter_params,
            "duration_seconds": duration,
            "fps": fps,
            "avg_latency_ms": avg_latency,
            "detection_rate_pct": det_rate,
            "lost_tracking_events": self.lost_tracking_events,
            "coupling_violations": {
                "pip_clamps": self.pip_clamps,
                "dip_clamps": self.dip_clamps,
                "pip_dip_coupling_overrides": self.coupling_overrides,
                "total": self.pip_clamps + self.dip_clamps + self.coupling_overrides
            }
        }
        
        filepath = os.path.join(log_dir, f"summary_{summary['session_id']}.json")
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=4)
        return filepath
