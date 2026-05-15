import time
import math
import os
import json
from datetime import datetime

class PerformanceTester:
    def __init__(self):
        self.is_testing = False
        self.reset()

    def reset(self):
        self.start_time = 0.0
        self.total_frames = 0
        self.detected_frames = 0
        
        self.prev_hand_detected = False
        self.lost_tracking_events = 0
        
        self.prev_landmarks = None
        self.accumulated_landmark_jitter = 0.0
        self.jitter_landmark_count = 0
        
        self.prev_angles = None
        self.accumulated_angle_jitter = 0.0
        self.jitter_angle_count = 0
        
        self.accumulated_latency = 0.0
        
        # New coupling violation counters
        self.pip_clamps = 0
        self.dip_clamps = 0
        self.coupling_overrides = 0

    def start_test(self):
        self.reset()
        self.is_testing = True
        self.start_time = time.time()
        print("\n--- ROBUSTNESS TEST STARTED ---")

    def stop_test(self):
        self.is_testing = False
        duration = time.time() - self.start_time
        print("\n--- ROBUSTNESS TEST STOPPED ---")
        self.print_report(duration)

    def update(self, tracker_output, final_fingers, latency_ms, telemetry_flags=None):
        if not self.is_testing:
            return

        self.total_frames += 1
        self.accumulated_latency += latency_ms
        
        hand_detected = tracker_output.get("hand_detected", False)
        if hand_detected:
            self.detected_frames += 1
            
            # Record coupling violations
            if telemetry_flags:
                for finger, flags in telemetry_flags.items():
                    if flags.get("pip_clamped"): self.pip_clamps += 1
                    if flags.get("dip_clamped"): self.dip_clamps += 1
                    if flags.get("coupling_triggered"): self.coupling_overrides += 1
            
        # Lost tracking event
        if self.prev_hand_detected and not hand_detected:
            self.lost_tracking_events += 1
            
        # Landmark Jitter
        current_landmarks = tracker_output.get("landmarks_norm")
        if hand_detected and current_landmarks and self.prev_hand_detected and self.prev_landmarks:
            total_dist = 0.0
            points = min(len(current_landmarks), len(self.prev_landmarks))
            for i in range(points):
                p1 = current_landmarks[i]
                p2 = self.prev_landmarks[i]
                dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)
                total_dist += dist
            avg_dist = total_dist / max(1, points)
            self.accumulated_landmark_jitter += avg_dist
            self.jitter_landmark_count += 1
            
        # Angle Jitter
        if hand_detected and final_fingers and self.prev_hand_detected and self.prev_angles:
            total_angle_diff = 0.0
            angle_count = 0
            for finger in final_fingers:
                if finger in self.prev_angles:
                    diff = abs(final_fingers[finger].get("angle", 0.0) - self.prev_angles[finger].get("angle", 0.0))
                    total_angle_diff += diff
                    angle_count += 1
            if angle_count > 0:
                self.accumulated_angle_jitter += (total_angle_diff / angle_count)
                self.jitter_angle_count += 1

        # Store previous state
        self.prev_hand_detected = hand_detected
        self.prev_landmarks = current_landmarks if hand_detected else None
        self.prev_angles = final_fingers if hand_detected else None

    def print_report(self, duration):
        if self.total_frames == 0:
            print("No frames recorded during test.")
            return

        fps = self.total_frames / max(duration, 0.001)
        detection_rate = (self.detected_frames / self.total_frames) * 100.0
        
        avg_landmark_jitter = 0.0
        if self.jitter_landmark_count > 0:
            avg_landmark_jitter = self.accumulated_landmark_jitter / self.jitter_landmark_count
            
        avg_angle_jitter = 0.0
        if self.jitter_angle_count > 0:
            avg_angle_jitter = self.accumulated_angle_jitter / self.jitter_angle_count
            
        avg_latency_ms = self.accumulated_latency / self.total_frames

        row_str = f"| [Fill in] | {fps:.1f} | {detection_rate:.1f}% | LM: {avg_landmark_jitter:.4f}, Ang: {avg_angle_jitter:.2f} | Latency: {avg_latency_ms:.1f}ms, Violations: {self.pip_clamps+self.dip_clamps+self.coupling_overrides} |"

        print("\nTest Matrix Row:")
        print("| Condition | FPS | Detection Rate | Jitter | Notes |")
        print(row_str)
        print()

        report_dir = "test_reports"
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(report_dir, f"report_{timestamp}.json")
        
        report_data = {
            "timestamp": timestamp,
            "condition": "[Fill in]",
            "duration_seconds": duration,
            "fps": fps,
            "detection_rate_pct": detection_rate,
            "avg_landmark_jitter": avg_landmark_jitter,
            "avg_angle_jitter": avg_angle_jitter,
            "avg_latency_ms": avg_latency_ms,
            "lost_tracking_events": self.lost_tracking_events,
            "coupling_violations": {
                "pip_clamps": self.pip_clamps,
                "dip_clamps": self.dip_clamps,
                "pip_dip_coupling_overrides": self.coupling_overrides,
                "total": self.pip_clamps + self.dip_clamps + self.coupling_overrides
            },
            "notes": ""
        }
        
        with open(filepath, "w") as f:
            json.dump(report_data, f, indent=4)
            
        print(f"✅ Saved detailed test report to: {filepath}")
        print("Tip: Run `python aggregate_tests.py` later to compile all reports into the markdown matrix.\n")
