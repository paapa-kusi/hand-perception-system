from dataclasses import dataclass


POSES = {"Victory": "PEACE", "Open_Palm": "OPEN"}


@dataclass(frozen=True)
class Observation:
    frame_ms: int
    label: str
    score: float = 0.0


class GestureGate:
    def __init__(self, threshold=0.70, dwell_ms=200, max_gap_ms=150):
        self.threshold = threshold
        self.dwell_ms = dwell_ms
        self.max_gap_ms = max_gap_ms
        self.last_frame_ms = None
        self.candidate = None
        self.candidate_since_ms = None
        self.accepted = None

    def clear_candidate(self):
        self.candidate = None
        self.candidate_since_ms = None

    def expire(self, now_ms):
        if self.last_frame_ms is not None and now_ms - self.last_frame_ms > self.max_gap_ms:
            self.clear_candidate()

    def observe(self, observation, now_ms):
        frame_ms = observation.frame_ms
        if self.last_frame_ms is not None and frame_ms <= self.last_frame_ms:
            return None

        self.expire(frame_ms)
        self.last_frame_ms = frame_ms
        pose = POSES.get(observation.label) if observation.score >= self.threshold else None
        if pose is None or now_ms - frame_ms > self.max_gap_ms:
            self.clear_candidate()
            return None

        if pose != self.candidate:
            self.candidate = pose
            self.candidate_since_ms = frame_ms

        if pose != self.accepted and frame_ms - self.candidate_since_ms >= self.dwell_ms:
            self.accepted = pose
            return pose
        return None
