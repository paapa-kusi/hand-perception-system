"""
calibration.py

Implements dynamic calibration mapping raw curl angles to a standard [0.0, 1.0] range.
Utilizes Sliding-Window Normalization (SWN) to compute real-time Z-scores, adapting
to user anatomy and camera distance dynamically with a peak-seeking fallback.

Interactions:
- Used by: main.py
"""
import numpy as np
from collections import deque

class CalibrationManager:
    def __init__(self, window_size=150, gamma=0.02, min_sigma=1.0):
        """
        Implements Sliding-Window Normalization (SWN) and Peak-Seeking Hysteresis.
        """
        self.window_size = window_size
        self.gamma = gamma
        self.min_sigma = min_sigma
        
        # Buffers for each finger's raw curl values
        self.buffers = {
            "thumb": deque(maxlen=window_size),
            "index": deque(maxlen=window_size),
            "middle": deque(maxlen=window_size),
            "ring": deque(maxlen=window_size),
            "pinky": deque(maxlen=window_size)
        }
        
        # Peak trackers
        self.global_max = {f: None for f in self.buffers}
        self.global_min = {f: None for f in self.buffers}

    def update(self, finger, raw_curl):
        """
        Updates the temporal buffer and peak bounds for a finger.
        """
        if finger not in self.buffers:
            return
            
        self.buffers[finger].append(raw_curl)
        
        # Update global bounds with forgetting factor
        if self.global_max[finger] is None:
            self.global_max[finger] = raw_curl
            self.global_min[finger] = raw_curl
        else:
            if raw_curl > self.global_max[finger]:
                self.global_max[finger] = (1.0 - self.gamma) * self.global_max[finger] + self.gamma * raw_curl
            if raw_curl < self.global_min[finger]:
                self.global_min[finger] = (1.0 - self.gamma) * self.global_min[finger] + self.gamma * raw_curl

    def normalize_curl(self, finger, raw_curl):
        """
        Maps raw curl to [0.0, 1.0] using Z-score normalization with fallback to peak-seeking.
        """
        if finger not in self.buffers or len(self.buffers[finger]) < 10:
            # Fallback to peak-seeking if buffer is too small
            g_max = self.global_max[finger]
            g_min = self.global_min[finger]
            if g_max is None or abs(g_max - g_min) < 1e-5:
                return 0.0
            norm = (raw_curl - g_min) / (g_max - g_min)
            return float(np.clip(norm, 0.0, 1.0))

        # Z-Score Calculation
        data = np.array(self.buffers[finger])
        mu = np.mean(data)
        sigma = np.std(data)
        
        # Calculate Z-score
        z = (raw_curl - mu) / max(sigma, self.min_sigma)
        
        # Remap [-3, 3] Z-score range to [0.0, 1.0] and clamp
        norm = (z + 3.0) / 6.0
        return float(np.clip(norm, 0.0, 1.0))
