"""
features.py

Core biomechanical feature extraction module. Computes a palm-plane normal vector
to separate true finger flexion from out-of-plane abduction. Calculates 
range-of-motion clamped joint angles (MCP, PIP, DIP) and enforces PIP-DIP 
kinematic coupling under low-confidence conditions.

Interactions:
- Used by: main.py
"""
import numpy as np

# Landmark mapping based on MediaPipe Hands
FINGER_JOINTS = {
    "thumb": {"mcp": (0, 1, 2), "pip": (1, 2, 3), "dip": (2, 3, 4)},
    "index": {"mcp": (0, 5, 6), "pip": (5, 6, 7), "dip": (6, 7, 8)},
    "middle": {"mcp": (0, 9, 10), "pip": (9, 10, 11), "dip": (10, 11, 12)},
    "ring": {"mcp": (0, 13, 14), "pip": (13, 14, 15), "dip": (14, 15, 16)},
    "pinky": {"mcp": (0, 17, 18), "pip": (17, 18, 19), "dip": (18, 19, 20)}
}

def compute_palm_normal(landmarks):
    """
    Computes the palm normal vector using wrist, index MCP, and pinky MCP.
    """
    v1 = np.array(landmarks[5]) - np.array(landmarks[0]) # Wrist to Index MCP
    v2 = np.array(landmarks[17]) - np.array(landmarks[0]) # Wrist to Pinky MCP
    n = np.cross(v1, v2)
    norm = np.linalg.norm(n)
    return n / norm if norm > 1e-8 else np.array([0, 0, 1])

def angle_between_points(a, b, c, palm_normal=None):
    """
    Calculates the angle at point 'b' given points 'a', 'b', 'c'.
    If palm_normal is provided, projects vectors onto the plane perpendicular to the normal.
    """
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)

    if palm_normal is not None:
        # Project vectors onto the plane perpendicular to the palm normal
        # v_proj = v - (v dot n) * n
        ba = ba - np.dot(ba, palm_normal) * palm_normal
        bc = bc - np.dot(bc, palm_normal) * palm_normal

    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    
    if norm_ba < 1e-8 or norm_bc < 1e-8:
        return 180.0
        
    cosine = np.dot(ba, bc) / (norm_ba * norm_bc)
    cosine = np.clip(cosine, -1.0, 1.0)
    
    return np.degrees(np.arccos(cosine))

def extract_finger_features(landmarks, confidence=1.0):
    """
    Given landmarks, calculate joint angles with palm-plane projection,
    apply ROM clamps, and handle PIP-DIP coupling.
    """
    features = {}
    palm_normal = compute_palm_normal(landmarks)
    
    for finger_name, joints in FINGER_JOINTS.items():
        # Thumb uses raw 3D angles; others use projected angles
        projection = None if finger_name == "thumb" else palm_normal
        
        mcp_angle = angle_between_points(landmarks[joints["mcp"][0]], 
                                         landmarks[joints["mcp"][1]], 
                                         landmarks[joints["mcp"][2]], 
                                         palm_normal=projection)
                                         
        pip_angle = angle_between_points(landmarks[joints["pip"][0]], 
                                         landmarks[joints["pip"][1]], 
                                         landmarks[joints["pip"][2]], 
                                         palm_normal=projection)
                                         
        dip_angle = angle_between_points(landmarks[joints["dip"][0]], 
                                         landmarks[joints["dip"][1]], 
                                         landmarks[joints["dip"][2]], 
                                         palm_normal=projection)
        
        # Bend is defined as how far it is from straight (180 degrees)
        mcp_bend = 180.0 - mcp_angle
        pip_bend = 180.0 - pip_angle
        dip_bend = 180.0 - dip_angle
        
        # Hard Range of Motion (ROM) Clamps
        pip_clamped = False
        dip_clamped = False
        
        if pip_bend < 0.0:
            pip_bend = 0.0
            pip_clamped = True
        elif pip_bend > 100.0:
            pip_bend = 100.0
            pip_clamped = True
            
        if dip_bend < 0.0:
            dip_bend = 0.0
            dip_clamped = True
        elif dip_bend > 80.0:
            dip_bend = 80.0
            dip_clamped = True

        # PIP-DIP Biomechanical Coupling Override
        coupling_triggered = False
        if confidence < 0.5:
            dip_bend = 0.67 * pip_bend
            coupling_triggered = True
        
        # Re-calculate angles from clamped bends for consistency
        pip_angle = 180.0 - pip_bend
        dip_angle = 180.0 - dip_bend

        # Weighted raw curl
        raw_curl = 0.25 * mcp_bend + 0.50 * pip_bend + 0.25 * dip_bend
        
        features[finger_name] = {
            "angles": {
                "mcp": float(mcp_angle),
                "pip": float(pip_angle),
                "dip": float(dip_angle)
            },
            "raw_curl": float(raw_curl),
            "telemetry": {
                "pip_clamped": pip_clamped,
                "dip_clamped": dip_clamped,
                "coupling_triggered": coupling_triggered
            }
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
