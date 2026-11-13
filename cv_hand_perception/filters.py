import time

class ExponentialMovingAverage:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.state = None

    def update(self, value):
        if self.state is None:
            self.state = value
        else:
            self.state = self.alpha * value + (1.0 - self.alpha) * self.state
        return self.state

    def reset(self):
        self.state = None

class HandStateFilter:
    def __init__(self, alpha_curl=0.3, timeout_seconds=0.3):
        self.alpha_curl = alpha_curl
        self.timeout_seconds = timeout_seconds
        
        self.last_valid_time = 0
        self.last_valid_state = None
        
        # Dict of EMA filters for each finger's curl
        self.curl_filters = {
            "thumb": ExponentialMovingAverage(alpha=alpha_curl),
            "index": ExponentialMovingAverage(alpha=alpha_curl),
            "middle": ExponentialMovingAverage(alpha=alpha_curl),
            "ring": ExponentialMovingAverage(alpha=alpha_curl),
            "pinky": ExponentialMovingAverage(alpha=alpha_curl)
        }

    def process(self, hand_detected, confidence, raw_features, current_time):
        """
        Applies filtering to the raw features and handles tracking loss/confidence drops.
        """
        # Define a safe neutral state
        neutral_state = {
            "thumb": {"curl": 0.0},
            "index": {"curl": 0.0},
            "middle": {"curl": 0.0},
            "ring": {"curl": 0.0},
            "pinky": {"curl": 0.0}
        }
        
        # If no hand or low confidence
        if not hand_detected or confidence < 0.5:
            time_since_last_valid = current_time - self.last_valid_time
            
            if time_since_last_valid < self.timeout_seconds and self.last_valid_state is not None:
                # Keep last valid state for a brief moment
                return self.last_valid_state
            else:
                # Fallback to safe neutral state, reset filters
                for f in self.curl_filters.values():
                    f.reset()
                self.last_valid_state = neutral_state
                return neutral_state
                
        # We have a valid hand, update filters
        filtered_state = {}
        for finger, features in raw_features.items():
            smoothed_curl = self.curl_filters[finger].update(features["raw_curl"])
            filtered_state[finger] = {
                "curl": smoothed_curl,
                # we can also pass through raw angles if needed
                "angle": features["angles"]["pip"] # using PIP as a representative angle for the final output format
            }
            
        self.last_valid_time = current_time
        self.last_valid_state = filtered_state
        return filtered_state

