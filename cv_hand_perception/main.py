import argparse
from contextlib import ExitStack
from pathlib import Path

import cv2
import time
import json
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
import serial
import yaml

from camera import CameraManager
from features import extract_finger_features
from gesture import GestureTracker
from filters import HandStateFilter
from calibration import CalibrationManager
from logger import Logger
from visualizer import Visualizer
from servo_pose import PeacePose, servo_target

POSE_HOLD_SECONDS = 3.0


def main():
    parser = argparse.ArgumentParser(description="Preview hand poses and optionally send them to a Mega.")
    parser.add_argument("--port", help="Serial port for the Mega, such as COM3.")
    parser.add_argument("--peace-target", action="append", type=servo_target, default=[])
    parser.add_argument("--open-palm-target", action="append", type=servo_target, default=[])
    parser.add_argument("--fist-target", action="append", type=servo_target, default=[])
    parser.add_argument("--horns-target", action="append", type=servo_target, default=[])
    parser.add_argument("--okay-target", action="append", type=servo_target, default=[])
    parser.add_argument("--opencv", action="store_true", help="Use OpenCV DNN models and DirectShow on Windows.")
    args = parser.parse_args()
    targets_by_pose = {
        pose: targets
        for pose, targets in (
            ("peace", args.peace_target), ("open palm", args.open_palm_target),
            ("fist", args.fist_target), ("horns", args.horns_target), ("okay", args.okay_target),
        )
        if targets
    }
    if bool(args.port) != bool(targets_by_pose):
        parser.error("--port and at least one pose target must be provided together.")
    if "okay" in targets_by_pose and "open palm" not in targets_by_pose:
        parser.error("Configure an open palm pose to use as the starting position for OK.")
    for pose, targets in targets_by_pose.items():
        if len({pin for pin, _ in targets}) != len(targets):
            parser.error(f"Provide at most one target angle per pin for {pose}.")

    with Path(__file__).with_name("config.yaml").open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with ExitStack() as cleanup:
        run(config, cleanup, args, targets_by_pose)


def run(config, cleanup, args, targets_by_pose):
        
    camera_cfg = config["camera"]
    mp_cfg = config["mediapipe"]
    filter_cfg = config["filters"]
    calib_cfg = config["calibration"]
    
    # Initialize components
    camera = CameraManager(
        device_id=camera_cfg["device_id"], 
        width=camera_cfg["width"], 
        height=camera_cfg["height"], 
        fps=camera_cfg["fps"],
        backend=cv2.CAP_DSHOW if args.opencv and sys.platform == "win32" else cv2.CAP_ANY,
    )
    cleanup.callback(camera.release)
    
    if args.opencv:
        from opencv_tracker import OpenCVHandTracker

        tracker = OpenCVHandTracker(
            mp_cfg.get("opencv_palm_confidence", mp_cfg["min_detection_confidence"]),
            mp_cfg["min_tracking_confidence"],
        )
    else:
        from hand_tracker import HandTracker

        tracker = HandTracker(
            max_num_hands=mp_cfg["max_num_hands"],
            model_complexity=mp_cfg["model_complexity"],
            min_detection_confidence=mp_cfg["min_detection_confidence"],
            min_tracking_confidence=mp_cfg["min_tracking_confidence"],
        )
        cleanup.callback(tracker.close)
    cleanup.callback(cv2.destroyAllWindows)
    
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
    gesture_tracker = GestureTracker()
    pose_output = None
    status = "Hold a pose for 3 s | Q: quit" if args.port else "Q: quit"
    last_attempted_pose = None
    last_acknowledged_pose = None
    last_landmarks = []
    last_hand_time = None
    
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
            gesture_tracker.update({}, time.monotonic())
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
        
        raw_features = {}
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
            
        pose_time = time.monotonic()
        gesture = gesture_tracker.update(
            raw_features, pose_time, tracker_output["landmarks_norm"],
            tracker_output["landmarks_pixel"],
        )
        final_state["gesture"] = gesture
        can_send_pose = gesture in targets_by_pose and gesture != last_attempted_pose
        okay_needs_reset = (
            gesture == "okay" and can_send_pose and last_acknowledged_pose != "open palm"
        )
        can_send_pose = can_send_pose and not okay_needs_reset
        remaining = POSE_HOLD_SECONDS - gesture_tracker.held_seconds
        if can_send_pose:
            status_text = f"Hold {gesture}: {remaining:.1f} s | Q: quit" if remaining > 0 else f"Sending {gesture}..."
        elif okay_needs_reset:
            status_text = "Hold open palm first, then show OK | Q: quit"
        elif (
            not raw_features and gesture_tracker.candidate in targets_by_pose
            and gesture_tracker.candidate != last_attempted_pose
        ):
            status_text = "Reacquiring hand. Countdown paused | Q: quit"
        else:
            status_text = status
        
        # 5. Logging
        logger.log(final_state, gesture)
        
        # Print state at lower frequency (e.g. every 1 second)
        if current_time - last_print_time > 1.0:
            print(json.dumps(final_state, indent=2))
            last_print_time = current_time
            
        # 6. Visualization
        if tracker_output["hand_detected"]:
            last_landmarks = tracker_output["landmarks_pixel"]
            last_hand_time = pose_time
        if last_hand_time is not None and pose_time - last_hand_time <= gesture_tracker.dropout_grace:
            visualizer.draw_skeleton(frame, last_landmarks)
        
        visualizer.draw_dashboard(frame, final_state, fps)
        cv2.putText(
            frame, f"Pose: {gesture}", (10, frame.shape[0] - 43),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 240, 80), 2,
        )
        cv2.putText(
            frame, status_text, (10, frame.shape[0] - 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
        )
        
        cv2.imshow("Hand Perception - Phase 1", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if can_send_pose and remaining <= 0:
            last_attempted_pose = gesture
            last_acknowledged_pose = None
            try:
                targets = targets_by_pose[gesture]
                if pose_output is None:
                    pose_output = PeacePose(args.port, targets)
                    cleanup.callback(pose_output.close)
                pose_output.send(targets)
                status = f"Mega acknowledged {gesture} | Q: quit"
            except (serial.SerialException, RuntimeError) as error:
                print(f"Servo command failed: {error}", flush=True)
                status = "Servo command failed. See the console | Q: quit"
            else:
                last_acknowledged_pose = gesture
                print(f"Mega acknowledged the configured {gesture} pose.", flush=True)

if __name__ == "__main__":
    main()

