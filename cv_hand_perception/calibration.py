import numpy as np

class CalibrationManager:
    def __init__(self, default_open=0.0, default_closed=90.0):
        # We store the expected raw curl values for an open hand vs closed fist.
        # These default values are rough estimates (bend degrees).
        self.baselines = {
            "thumb": {"open": default_open, "closed": default_closed},
            "index": {"open": default_open, "closed": default_closed},
            "middle": {"open": default_open, "closed": default_closed},
            "ring": {"open": default_open, "closed": default_closed},
            "pinky": {"open": default_open, "closed": default_closed}
        }

    def calibrate(self, finger, pose, raw_curl_value):
        """
        pose should be 'open' or 'closed'
        """
        if pose in ["open", "closed"]:
            self.baselines[finger][pose] = raw_curl_value

    def normalize_curl(self, finger, raw_curl):
        """
        Maps the raw curl value to a 0.0 - 1.0 range based on calibrated baselines.
        """
        open_baseline = self.baselines[finger]["open"]
        closed_baseline = self.baselines[finger]["closed"]
        
        # Avoid division by zero
        if abs(closed_baseline - open_baseline) < 1e-5:
            return 0.0
            
        normalized = (raw_curl - open_baseline) / (closed_baseline - open_baseline)
        return float(np.clip(normalized, 0.0, 1.0))
