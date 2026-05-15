"""
main.py

Primary orchestrator for the Hand Perception Pipeline. Initializes all components
(camera, tracker, filters, calibrator), manages the real-time execution loop, 
enforces error recovery, and handles the final integration of the sensory state.

Interactions:
- Reads from: config.yaml
- Imports: camera.py, hand_tracker.py, features.py, filters.py, calibration.py, 
  telemetry.py, tester.py, visualizer.py
"""
import cv2
import time
import json
import yaml
import os

from camera import CameraManager
from hand_tracker import HandTracker
from features import extract_finger_features, normalize_landmarks
from filters import HandStateFilter
from calibration import CalibrationManager
from telemetry import TelemetryLogger, SessionSummaryLogger
from visualizer import Visualizer
from tester import PerformanceTester

def main():
    # Change working directory to the directory of this script to ensure relative paths work
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Load config
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found.")
        return
        
    camera_cfg = config["camera"]
    mp_cfg = config["mediapipe"]
    filter_cfg = config["filters"]
    calib_cfg = config["calibration"]
    operator_name = config.get("session", {}).get("operator_name", "default_user")
    
    if operator_name.strip() in ["", "default_user", "unknown", "CHANGE_ME"]:
        print("\n" + "="*50)
        print("ATTENTION: Session operator is not set in config.yaml.")
        print("Please enter your name to claim this session telemetry.")
        print("="*50)
        operator_name = input("Enter operator name: ").strip()
        if not operator_name:
            operator_name = "unknown_operator"
            
    # Initialize components
    camera = CameraManager(
        device_id=camera_cfg["device_id"], 
        width=camera_cfg["width"], 
        height=camera_cfg["height"], 
        fps=camera_cfg["fps"]
    )
    
    tracker = HandTracker(
        max_num_hands=mp_cfg["max_num_hands"],
        model_complexity=mp_cfg["model_complexity"],
        min_detection_confidence=mp_cfg["min_detection_confidence"],
        min_tracking_confidence=mp_cfg["min_tracking_confidence"]
    )
    
    state_filter = HandStateFilter(
        min_cutoff=filter_cfg["min_cutoff"],
        beta=filter_cfg["beta"],
        timeout_seconds=filter_cfg["timeout_seconds"],
        deadband_threshold=filter_cfg["deadband_threshold"]
    )
    
    calibrator = CalibrationManager(
        window_size=calib_cfg["window_size"],
        gamma=calib_cfg["gamma"],
        min_sigma=calib_cfg["min_sigma"]
    )
    
    telemetry = TelemetryLogger(log_dir="logs", operator_name=operator_name)
    summary_logger = SessionSummaryLogger(filter_params=filter_cfg, operator_name=operator_name)
    visualizer = Visualizer()
    tester = PerformanceTester(operator_name=operator_name)
    
    if not camera.start():
        return
        
    print("Starting Hand Perception Module (Phase 1 Upgraded)... Press 'q' to quit.")
    
    prev_time = time.time()
    last_print_time = time.time()
    
    consecutive_failures = 0
    max_failures = 30
    
    try:
        while True:
            ret, frame, frame_time = camera.read_frame()
            if not ret:
                consecutive_failures += 1
                if consecutive_failures > max_failures:
                    print(f"Error: Lost connection to camera.")
                    break
                time.sleep(0.01)
                continue
                
            consecutive_failures = 0
                
            current_time = time.time()
            fps = 1.0 / max(current_time - prev_time, 0.001)
            prev_time = current_time
            
            process_start_time = time.time()
            
            # 1. Detect Hand & Track Landmarks
            tracker_output = tracker.process_frame(frame)
            
            # Build Final JSON State
            final_state = {
                "timestamp": frame_time,
                "hand_detected": tracker_output["hand_detected"],
                "confidence": tracker_output["confidence"],
                "handedness": tracker_output["handedness"],
            }
            
            telemetry_flags = None
            
            if tracker_output["hand_detected"]:
                # 2. Feature Extraction (Projected & Clamped)
                raw_features = extract_finger_features(
                    tracker_output["landmarks_norm"], 
                    confidence=tracker_output["confidence"]
                )
                
                # Extract telemetry flags for logging
                telemetry_flags = {f: data["telemetry"] for f, data in raw_features.items()}
                
                # 3. Filtering (1 Euro Filter + Deadband)
                smoothed_features = state_filter.process(
                    tracker_output["hand_detected"], 
                    tracker_output["confidence"], 
                    raw_features, 
                    frame_time
                )
                
                # 4. Auto-Calibration (Z-Score)
                final_fingers = {}
                for finger, data in smoothed_features.items():
                    # Update calibration buffers with raw values
                    calibrator.update(finger, raw_features[finger]["raw_curl"])
                    # Normalize smoothed output
                    norm_curl = calibrator.normalize_curl(finger, data["curl"])
                    
                    final_fingers[finger] = {
                        "curl": norm_curl,
                        "angle": data["angle"]
                    }
                    
                final_state["fingers"] = final_fingers
                
            else:
                # Handle confidence drop/loss
                smoothed_features = state_filter.process(False, 0.0, {}, frame_time)
                final_fingers = {}
                if smoothed_features:
                    for finger, data in smoothed_features.items():
                        norm_curl = calibrator.normalize_curl(finger, data["curl"])
                        final_fingers[finger] = {
                            "curl": norm_curl,
                            "angle": data.get("angle", 0.0)
                        }
                final_state["fingers"] = final_fingers
                
            process_end_time = time.time()
            latency_ms = (process_end_time - process_start_time) * 1000.0
            
            # 5. Logging & Testing
            telemetry.log_frame(final_state, latency_ms)
            summary_logger.record_frame(tracker_output["hand_detected"], latency_ms, telemetry_flags)
            tester.update(tracker_output, final_state.get("fingers"), latency_ms, telemetry_flags)
            
            if current_time - last_print_time > 1.0:
                # Print concise state
                print(f"FPS: {fps:.1f} | Latency: {latency_ms:.1f}ms | Hand: {final_state['hand_detected']}")
                last_print_time = current_time
                
            # 6. Visualization
            if tracker_output["hand_detected"]:
                visualizer.draw_skeleton(frame, tracker_output["landmarks_pixel"])
            
            visualizer.draw_dashboard(frame, final_state, fps, is_testing=tester.is_testing)
            
            cv2.imshow("Hand Perception - Phase 1 Upgraded", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('t'):
                if tester.is_testing:
                    tester.stop_test()
                else:
                    tester.start_test()
                    
    finally:
        print("\nCleaning up...")
        camera.release()
        tracker.close()
        telemetry.close()
        summary_path = summary_logger.save_summary()
        print(f"Session summary saved to: {summary_path}")
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
