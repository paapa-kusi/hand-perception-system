import cv2
import time
import json
import yaml

from camera import CameraManager
from hand_tracker import HandTracker
from features import extract_finger_features, normalize_landmarks
from filters import HandStateFilter
from calibration import CalibrationManager
from logger import Logger
from visualizer import Visualizer

def main():
    # Load config
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found. Please ensure you run this script from the cv_hand_perception directory.")
        return
        
    camera_cfg = config["camera"]
    mp_cfg = config["mediapipe"]
    filter_cfg = config["filters"]
    calib_cfg = config["calibration"]
    
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
        alpha_curl=filter_cfg["alpha_curl"],
        timeout_seconds=filter_cfg["timeout_seconds"]
    )
    
    calibrator = CalibrationManager(
        default_open=calib_cfg["default_open"],
        default_closed=calib_cfg["default_closed"]
    )
    
    logger = Logger(log_dir="logs")
    visualizer = Visualizer()
    
    if not camera.start():
        return
        
    print("Starting Hand Perception Module... Press 'q' to quit.")
    
    prev_time = time.time()
    last_print_time = time.time()
    
    consecutive_failures = 0
    max_failures = 30
    
    while True:
        ret, frame, frame_time = camera.read_frame()
        if not ret:
            consecutive_failures += 1
            if consecutive_failures > max_failures:
                print(f"Error: Lost connection to camera after {max_failures} consecutive failed frames.")
                break
            time.sleep(0.01) # Small sleep before retry
            continue
            
        consecutive_failures = 0 # Reset on success
            
        # Calculate FPS
        current_time = time.time()
        fps = 1.0 / max(current_time - prev_time, 0.001)
        prev_time = current_time
        
        # 1. Detect Hand & Track Landmarks
        tracker_output = tracker.process_frame(frame)
        
        # Build Final JSON State
        final_state = {
            "timestamp": frame_time,
            "hand_detected": tracker_output["hand_detected"],
            "confidence": tracker_output["confidence"],
            "handedness": tracker_output["handedness"],
        }
        
        if tracker_output["hand_detected"]:
            # 2. Feature Extraction
            # We use normalized coordinates for angles as they represent the 3D space relative to camera better
            raw_features = extract_finger_features(tracker_output["landmarks_norm"])
            
            # 3. Filtering
            smoothed_features = state_filter.process(
                tracker_output["hand_detected"], 
                tracker_output["confidence"], 
                raw_features, 
                frame_time
            )
            
            # 4. Calibration (map to 0-1)
            final_fingers = {}
            for finger, data in smoothed_features.items():
                norm_curl = calibrator.normalize_curl(finger, data["curl"])
                final_fingers[finger] = {
                    "curl": norm_curl,
                    "angle": data["angle"]
                }
                
            final_state["fingers"] = final_fingers
            
        else:
            # Handle confidence drop/loss
            smoothed_features = state_filter.process(False, 0.0, {}, frame_time)
            # Calibration for neutral state fallback
            final_fingers = {}
            if smoothed_features:
                for finger, data in smoothed_features.items():
                    norm_curl = calibrator.normalize_curl(finger, data["curl"])
                    final_fingers[finger] = {
                        "curl": norm_curl,
                        "angle": data.get("angle", 0.0)
                    }
            final_state["fingers"] = final_fingers
            
        # Optional: Gesture Label logic (stubbed for now)
        gesture = "unknown"
        
        # 5. Logging
        logger.log(final_state, gesture)
        
        # Print state at lower frequency (e.g. every 1 second)
        if current_time - last_print_time > 1.0:
            print(json.dumps(final_state, indent=2))
            last_print_time = current_time
            
        # 6. Visualization
        if tracker_output["hand_detected"]:
            visualizer.draw_skeleton(frame, tracker_output["landmarks_pixel"])
        
        visualizer.draw_dashboard(frame, final_state, fps)
        
        cv2.imshow("Hand Perception - Phase 1", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    camera.release()
    tracker.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    import sys

    if sys.argv[1:]:
        from gesture_demo import main as gesture_main

        sys.exit(gesture_main())
    main()
