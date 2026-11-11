import cv2

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)

class Visualizer:
    def __init__(self):
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def draw_skeleton(self, frame, landmarks_pixel):
        """
        Since we extracted landmarks manually, if we want to use MediaPipe's drawer,
        we would need the original hand_landmarks object.
        For Phase 1, we assume the raw MediaPipe drawing is done before feature extraction if needed,
        or we can manually draw circles and lines. Let's do manual drawing.
        """
        if not landmarks_pixel:
            return
            
        # Draw connections
        for connection in HAND_CONNECTIONS:
            start_idx = connection[0]
            end_idx = connection[1]
            
            if start_idx < len(landmarks_pixel) and end_idx < len(landmarks_pixel):
                pt1 = landmarks_pixel[start_idx]
                pt2 = landmarks_pixel[end_idx]
                cv2.line(frame, pt1, pt2, (255, 255, 255), 2)
                
        # Draw joints
        for pt in landmarks_pixel:
            cv2.circle(frame, pt, 5, (0, 0, 255), -1)

    def draw_dashboard(self, frame, state, fps):
        """
        Draws telemetry data on the screen.
        """
        # Background panel
        h, w, _ = frame.shape
        panel_w = 250
        cv2.rectangle(frame, (0, 0), (panel_w, h), (0, 0, 0), -1)
        
        y_offset = 30
        
        # FPS and Confidence
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, y_offset), self.font, 0.7, (0, 255, 0), 2)
        y_offset += 30
        
        hand_status = "Detected" if state.get("hand_detected") else "Lost"
        conf = state.get("confidence", 0.0)
        cv2.putText(frame, f"State: {hand_status}", (10, y_offset), self.font, 0.7, (0, 255, 255), 2)
        y_offset += 30
        cv2.putText(frame, f"Conf: {conf:.2f}", (10, y_offset), self.font, 0.7, (0, 255, 255), 2)
        y_offset += 50
        
        if state.get("hand_detected") and "fingers" in state:
            fingers = state["fingers"]
            for finger in ["thumb", "index", "middle", "ring", "pinky"]:
                if finger in fingers:
                    curl = fingers[finger].get("curl", 0.0)
                    angle = fingers[finger].get("angle", 0.0)
                    
                    # Draw text
                    cv2.putText(frame, f"{finger.capitalize()}: {curl:.2f}", (10, y_offset), self.font, 0.6, (255, 255, 255), 1)
                    
                    # Draw bar
                    bar_w = 120
                    bar_fill = int(curl * bar_w)
                    cv2.rectangle(frame, (120, y_offset - 15), (120 + bar_w, y_offset), (100, 100, 100), 1)
                    cv2.rectangle(frame, (120, y_offset - 15), (120 + bar_fill, y_offset), (0, 255, 0), -1)
                    
                    y_offset += 35

