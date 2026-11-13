from model_assets import ensure_models

import cv2
import numpy as np

from opencv_zoo.mp_handpose import MPHandPose
from opencv_zoo.mp_palmdet import MPPalmDet


class OpenCVHandTracker:
    def __init__(self, detection_threshold, presence_threshold):
        models = ensure_models()
        self.palm = MPPalmDet(
            str(models / "palm_detection_mediapipe_2023feb.onnx"),
            scoreThreshold=detection_threshold,
        )
        self.hand = MPHandPose(
            str(models / "handpose_estimation_mediapipe_2023feb.onnx"),
            confThreshold=presence_threshold,
        )
        self.tracked_palm = None

    def process_frame(self, frame):
        if self.tracked_palm is not None:
            # Reuse the last palm region, but estimate landmarks on the new frame.
            try:
                result = self.hand.infer(frame, self.tracked_palm)
            except (cv2.error, ValueError):
                result = None
            if result is not None:
                return self._hand_state(result)
            self.tracked_palm = None

        for palm in sorted(self.palm.infer(frame), key=lambda result: result[-1], reverse=True):
            result = self.hand.infer(frame, palm)
            if result is not None:
                return self._hand_state(result)
        return {
            "hand_detected": False,
            "confidence": 0.0,
            "handedness": None,
            "landmarks_norm": [],
            "landmarks_pixel": [],
        }

    def _hand_state(self, result):
        points = result[4:67].reshape(21, 3)[:, :2]
        palm_points = points[self.hand.PALM_LANDMARK_IDS]
        low = palm_points.min(axis=0)
        high = palm_points.max(axis=0)
        center = (low + high) / 2
        half_side = (high - low).max() * 0.6
        self.tracked_palm = (
            np.r_[center - half_side, center + half_side, palm_points.ravel(), result[-1]]
            if half_side >= 4 else None
        )
        return {
            "hand_detected": True,
            "confidence": float(result[-1]),
            "handedness": "Right" if result[-2] >= 0.5 else "Left",
            "landmarks_norm": result[67:130].reshape(21, 3),
            "landmarks_pixel": points.astype(int).tolist(),
        }

