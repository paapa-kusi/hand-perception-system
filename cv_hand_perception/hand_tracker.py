import cv2
import mediapipe as mp

class HandTracker:
    def __init__(self, max_num_hands=1, model_complexity=1, 
                 min_detection_confidence=0.6, min_tracking_confidence=0.6):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

    def process_frame(self, frame):
        # MediaPipe expects RGB images
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        frame_height, frame_width, _ = frame.shape
        
        output = {
            "hand_detected": False,
            "confidence": 0.0,
            "handedness": None,
            "landmarks_norm": [],
            "landmarks_pixel": []
        }

        if results.multi_hand_landmarks and results.multi_handedness:
            # For Phase 1, we only process the first hand detected
            hand_landmarks = results.multi_hand_landmarks[0]
            handedness_info = results.multi_handedness[0].classification[0]
            
            output["hand_detected"] = True
            output["confidence"] = handedness_info.score
            output["handedness"] = handedness_info.label  # 'Left' or 'Right'
            
            for lm in hand_landmarks.landmark:
                # Normalized coordinates (0 to 1)
                output["landmarks_norm"].append((lm.x, lm.y, lm.z))
                # Pixel coordinates
                output["landmarks_pixel"].append((
                    int(lm.x * frame_width), 
                    int(lm.y * frame_height)
                ))
                
        return output

    def close(self):
        self.hands.close()
