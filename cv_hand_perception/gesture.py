from math import dist


class GestureTracker:
    """Recognize a pose after the same landmark pattern persists briefly."""

    def __init__(self, dwell_seconds=0.25, max_frame_gap=0.5, dropout_grace=0.65):
        self.dwell_seconds = dwell_seconds
        self.max_frame_gap = max_frame_gap
        self.candidate = "unknown"
        self.dropout_grace = dropout_grace
        self.held_seconds = 0.0
        self.last_frame = None
        self.last_seen = None

    def update(self, features, timestamp, landmarks=None, image_landmarks=None):
        pose = classify_pose(features, landmarks, image_landmarks)
        if self.last_frame is None or timestamp - self.last_frame > self.max_frame_gap:
            self.candidate = "unknown"
            self.held_seconds = 0.0
            self.last_seen = None

        if pose == "unknown":
            if self.last_seen is not None and timestamp - self.last_seen > self.dropout_grace:
                self.candidate = "unknown"
                self.held_seconds = 0.0
                self.last_seen = None
            self.last_frame = timestamp
            return "unknown"

        if pose != self.candidate or self.last_seen is None or timestamp - self.last_seen > self.dropout_grace:
            self.candidate = pose
            self.held_seconds = 0.0
        elif self.last_seen == self.last_frame:
            self.held_seconds += timestamp - self.last_frame
        self.last_seen = timestamp
        self.last_frame = timestamp
        if self.held_seconds >= self.dwell_seconds:
            return pose
        return "unknown"


def classify_pose(features, landmarks=None, image_landmarks=None):
    fingers = ("index", "middle", "ring", "pinky")
    if not all(finger in features for finger in fingers):
        return "unknown"

    # The PIP joint distinguishes extended and folded fingers without
    # counting the natural bend between the palm and an extended finger.
    angles = [features[finger]["angles"]["pip"] for finger in fingers]
    extended = [angle >= 150 for angle in angles]
    folded = [angle <= 125 for angle in angles]
    if all(extended[:2]) and all(folded[2:]):
        return "peace"
    if extended[0] and extended[3] and all(folded[1:3]):
        return "horns"
    if not extended[0] and all(extended[1:]) and landmarks is not None and len(landmarks) == 21:
        palm_width = dist(landmarks[5], landmarks[17])
        if palm_width > 0 and dist(landmarks[4], landmarks[8]) <= 0.35 * palm_width:
            return "okay"
    if looks_like_okay_in_image(image_landmarks):
        return "okay"
    if all(extended):
        return "open palm"
    if all(folded):
        return "fist"
    return "unknown"


def looks_like_okay_in_image(points):
    if points is None or len(points) != 21:
        return False
    palm_width = dist(points[5], points[17])
    if palm_width < 10 or dist(points[4], points[8]) > 0.4 * palm_width:
        return False

    # A curved index and three nearly straight fingers distinguish OK from
    # an open palm or a pinch with the other fingers folded.
    straightness = []
    for base in (5, 9, 13, 17):
        length = sum(dist(points[joint], points[joint + 1]) for joint in range(base, base + 3))
        if length == 0:
            return False
        straightness.append(dist(points[base], points[base + 3]) / length)
    return straightness[0] <= 0.92 and all(value >= 0.90 for value in straightness[1:])

