import argparse
from collections import deque
from contextlib import ExitStack
import logging
from pathlib import Path
import time

import cv2
import mediapipe as mp
import numpy as np
import yaml

from camera import CameraManager
from gesture_serial import BAUD_RATE, GestureController
from gestures import GestureGate, Observation


HERE = Path(__file__).resolve().parent
WINDOW = "Hand Gesture Demo"
LOG = logging.getLogger(__name__)


def monotonic_ms():
    return time.monotonic_ns() // 1_000_000


def observation_from_result(result, frame_ms):
    if len(result.hand_landmarks) != 1 or not result.gestures or not result.gestures[0]:
        return Observation(frame_ms, "No single hand")
    category = max(result.gestures[0], key=lambda item: item.score)
    return Observation(frame_ms, category.category_name, category.score)


def open_recognizer(model, observations):
    def record_result(result, _image, frame_ms):
        observations.append(observation_from_result(result, frame_ms))

    options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
        num_hands=2,
        result_callback=record_result,
    )
    return mp.tasks.vision.GestureRecognizer.create_from_options(options)


def draw_status(frame, lines):
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 10 + 24 * len(lines)), (0, 0, 0), -1)
    for index, line in enumerate(lines, start=1):
        cv2.putText(frame, line, (10, index * 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 1, cv2.LINE_AA)


def run_demo(camera, recognizer, observations, gate, controller):
    frame = np.zeros((240, 640, 3), dtype=np.uint8)
    failures = 0
    last_submitted_ms = -1
    accept_after_ms = -1
    last_observation = None
    last_decision = None

    while True:
        if camera is not None:
            ok, image, _ = camera.read_frame()
            if ok:
                failures = 0
                frame = image
                last_submitted_ms = max(monotonic_ms(), last_submitted_ms + 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                recognizer.recognize_async(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                                           last_submitted_ms)
            else:
                failures += 1
                if failures >= 30:
                    raise OSError("Lost the camera after 30 failed reads")
                time.sleep(0.01)

        now_ms = monotonic_ms()
        if controller is not None:
            previous_state = controller.state
            controller.poll(now_ms)
            if controller.state != "armed" or previous_state != "armed":
                gate.clear_candidate()
                gate.accepted = controller.pose
                accept_after_ms = now_ms

        if failures:
            gate.clear_candidate()
            accept_after_ms = now_ms

        gate.expire(now_ms)
        while observations:
            observation = observations.popleft()
            last_observation = observation
            if observation.frame_ms <= accept_after_ms:
                continue
            pose = gate.observe(observation, now_ms)
            if pose is not None:
                last_decision = pose
                LOG.info("decision pose=%s candidate_ms=%d frame_ms=%d decision_ms=%d",
                         pose, gate.candidate_since_ms, observation.frame_ms, now_ms)
                if controller is not None:
                    controller.move(pose, now_ms)
                    # New motion must finish before another gesture can qualify.
                    accept_after_ms = now_ms
                    break

        status = controller.state.upper() if controller is not None else "CAMERA ONLY"
        if camera is None:
            lines = [f"Controller: {status}", "A: arm  S: stop  1: open  2: peace  Q: quit"]
        else:
            prediction = "Waiting for a fresh result"
            if last_observation is not None and now_ms - last_observation.frame_ms <= gate.max_gap_ms:
                prediction = f"{last_observation.label} ({last_observation.score:.2f})"
            lines = [f"{status}   Last decision: {last_decision or '-'}",
                     f"Camera: {prediction}",
                     "A: arm  S: stop  Q: quit" if controller is not None else "Q: quit"]
        preview = frame.copy()
        draw_status(preview, lines)
        cv2.imshow(WINDOW, preview)
        key = cv2.waitKey(10 if camera is None else 1) & 0xFF
        if key == ord("q") or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            return
        if controller is not None:
            if key == ord("a"):
                controller.arm(monotonic_ms())
            elif key == ord("s"):
                controller.stop(monotonic_ms())
            elif camera is None and key in (ord("1"), ord("2")):
                controller.move("OPEN" if key == ord("1") else "PEACE", monotonic_ms())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recognize or manually test two robotic hand poses.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--gesture-demo", action="store_true", help="use webcam gesture recognition")
    modes.add_argument("--manual", action="store_true", help="test the controller without the camera")
    parser.add_argument("--port", help="gesture controller serial port, such as COM5")
    parser.add_argument("--model", type=Path, default=HERE / "gesture_recognizer.task")
    args = parser.parse_args(argv)
    if args.manual and not args.port:
        parser.error("--manual requires --port")
    if args.gesture_demo and not args.model.is_file():
        parser.error(f"model missing at {args.model}. See the README for the download command.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with (HERE / "config.yaml").open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    observations = deque(maxlen=32)
    gate = GestureGate(**config.get("gestures", {}))
    try:
        with ExitStack() as stack:
            stack.callback(cv2.destroyAllWindows)
            camera = recognizer = controller = None
            if args.gesture_demo:
                recognizer = stack.enter_context(open_recognizer(args.model, observations))
                camera = CameraManager(**config["camera"])
                stack.callback(camera.release)
                if not camera.start():
                    return 1
            if args.port:
                import serial

                port = serial.Serial(args.port, BAUD_RATE, timeout=0, write_timeout=0.1)
                controller = GestureController(port, monotonic_ms())
                stack.callback(controller.close)
            run_demo(camera, recognizer, observations, gate, controller)
    except (OSError, RuntimeError, ValueError, cv2.error) as error:
        LOG.error("Demo stopped: %s", error)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0
