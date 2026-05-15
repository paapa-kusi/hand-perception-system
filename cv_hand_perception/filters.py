"""
filters.py

Temporal smoothing module for hand states. Implements an adaptive One Euro (1€) 
low-pass filter to dynamically reduce jitter during slow movements while maintaining 
low latency during fast motions. Includes deadband logic to prevent servo burnout.

Interactions:
- Used by: main.py
"""
import time
import math

class OneEuroFilter:
    def __init__(self, min_cutoff=1.0, beta=0.001, d_cutoff=1.0):
        # min_cutoff: static stability. Decreasing this reduces jitter but increases lag.
        self.min_cutoff = float(min_cutoff)
        # beta: speed coefficient. Increasing this reduces lag during fast movements but can introduce jitter.
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def update(self, value, timestamp):
        if self.t_prev is None or timestamp <= self.t_prev:
            self.x_prev = value
            self.dx_prev = 0.0
            self.t_prev = timestamp
            return value

        te = timestamp - self.t_prev
        if te <= 0:
            return self.x_prev

        # 1. Calculate raw derivative
        dx = (value - self.x_prev) / te
        
        # 2. Smooth derivative via fixed 1Hz low-pass
        alpha_d = 1.0 / (1.0 + 1.0 / (2.0 * math.pi * self.d_cutoff * te))
        if self.dx_prev is None:
            dx_hat = dx
        else:
            dx_hat = alpha_d * dx + (1.0 - alpha_d) * self.dx_prev
        
        # 3. Calculate adaptive cutoff
        fc = self.min_cutoff + self.beta * abs(dx_hat)
        
        # 4. Calculate smoothing factor
        alpha = 1.0 / (1.0 + 1.0 / (2.0 * math.pi * fc * te))
        
        # 5. Filtered value
        x_hat = alpha * value + (1.0 - alpha) * self.x_prev
        
        # Update state
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = timestamp
        
        return x_hat

    def reset(self):
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

class HandStateFilter:
    def __init__(self, min_cutoff=1.0, beta=0.001, timeout_seconds=0.3, deadband_threshold=0.5):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.timeout_seconds = timeout_seconds
        self.deadband_threshold = deadband_threshold
        
        self.last_valid_time = 0
        self.last_valid_state = None
        
        # Dict of OneEuroFilter filters for each finger's curl
        self.curl_filters = {
            "thumb": OneEuroFilter(min_cutoff=min_cutoff, beta=beta),
            "index": OneEuroFilter(min_cutoff=min_cutoff, beta=beta),
            "middle": OneEuroFilter(min_cutoff=min_cutoff, beta=beta),
            "ring": OneEuroFilter(min_cutoff=min_cutoff, beta=beta),
            "pinky": OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        }

    def process(self, hand_detected, confidence, raw_features, current_time):
        """
        Applies 1 Euro Filter and deadband logic to raw features.
        """
        neutral_state = {
            "thumb": {"curl": 0.0},
            "index": {"curl": 0.0},
            "middle": {"curl": 0.0},
            "ring": {"curl": 0.0},
            "pinky": {"curl": 0.0}
        }
        
        if not hand_detected or confidence < 0.5:
            time_since_last_valid = current_time - self.last_valid_time
            
            if time_since_last_valid < self.timeout_seconds and self.last_valid_state is not None:
                return self.last_valid_state
            else:
                for f in self.curl_filters.values():
                    f.reset()
                self.last_valid_state = neutral_state
                return neutral_state
                
        filtered_state = {}
        for finger, features in raw_features.items():
            raw_curl = features["raw_curl"]
            
            # Deadband check to eliminate servo jitter
            if self.last_valid_state and finger in self.last_valid_state:
                prev_val = self.last_valid_state[finger]["curl"]
                if abs(raw_curl - prev_val) < self.deadband_threshold:
                    # Skip update if within deadband
                    filtered_state[finger] = {
                        "curl": prev_val,
                        "angle": features["angles"]["pip"]
                    }
                    continue

            smoothed_curl = self.curl_filters[finger].update(raw_curl, current_time)
            filtered_state[finger] = {
                "curl": smoothed_curl,
                "angle": features["angles"]["pip"]
            }
            
        self.last_valid_time = current_time
        self.last_valid_state = filtered_state
        return filtered_state
