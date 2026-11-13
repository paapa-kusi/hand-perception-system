import numpy as np

# Landmark mapping based on MediaPipe Hands
FINGER_JOINTS = {
    "thumb": {"mcp": (0, 1, 2), "pip": (1, 2, 3), "dip": (2, 3, 4)},
    "index": {"mcp": (0, 5, 6), "pip": (5, 6, 7), "dip": (6, 7, 8)},
    "middle": {"mcp": (0, 9, 10), "pip": (9, 10, 11), "dip": (10, 11, 12)},
    "ring": {"mcp": (0, 13, 14), "pip": (13, 14, 15), "dip": (14, 15, 16)},
    "pinky": {"mcp": (0, 17, 18), "pip": (17, 18, 19), "dip": (18, 19, 20)}
}

def angle_between_points(a, b, c):
    """
    Calculates the angle at point 'b' given points 'a', 'b', 'c'.
    Points are expected to be (x, y, z) tuples or numpy arrays.
    """
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)

    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    
    if norm_ba < 1e-8 or norm_bc < 1e-8:
        return 180.0  # Default to straight if points are co-located
        
    cosine = np.dot(ba, bc) / (norm_ba * norm_bc)
    cosine = np.clip(cosine, -1.0, 1.0)
    
    return np.degrees(np.arccos(cosine))

def extract_finger_features(landmarks):
    """
    Given a list of 21 landmarks (x, y, z), calculate joint angles and raw curl scores.
    """
    features = {}
    
    for finger_name, joints in FINGER_JOINTS.items():
        # Calculate angles
        mcp_angle = angle_between_points(landmarks[joints["mcp"][0]], 
                                         landmarks[joints["mcp"][1]], 
                                         landmarks[joints["mcp"][2]])
                                         
        pip_angle = angle_between_points(landmarks[joints["pip"][0]], 
                                         landmarks[joints["pip"][1]], 
                                         landmarks[joints["pip"][2]])
                                         
        dip_angle = angle_between_points(landmarks[joints["dip"][0]], 
                                         landmarks[joints["dip"][1]], 
                                         landmarks[joints["dip"][2]])
        
        # Bend is defined as how far it is from straight (180 degrees)
        mcp_bend = 180.0 - mcp_angle
        pip_bend = 180.0 - pip_angle
        dip_bend = 180.0 - dip_angle
        
        # Weighted raw curl
        raw_curl = 0.25 * mcp_bend + 0.50 * pip_bend + 0.25 * dip_bend
        
        features[finger_name] = {
            "angles": {
                "mcp": float(mcp_angle),
                "pip": float(pip_angle),
                "dip": float(dip_angle)
            },
            "raw_curl": float(raw_curl)
        }
        
    return features

def normalize_landmarks(landmarks):
    """
    Normalizes landmarks relative to the wrist (landmark 0).
    """
    if not landmarks:
        return []
        
    wrist = np.array(landmarks[0])
    normalized = []
    
    for lm in landmarks:
        norm_point = np.array(lm) - wrist
        normalized.append((float(norm_point[0]), float(norm_point[1]), float(norm_point[2])))
        
    return normalized

