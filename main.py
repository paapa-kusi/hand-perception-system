import cv2
import mediapipe as mp

# Initialize MediaPipe Hand Tracking module
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

def get_gesture(landmarks):
    thumb_tip = landmarks[4]
    index_finger_tip = landmarks[8]
    middle_finger_tip = landmarks[12]
    ring_finger_tip = landmarks[16]
    pinky_finger_tip = landmarks[20]

    if thumb_tip.y < index_finger_tip.y and \
       index_finger_tip.y < middle_finger_tip.y and \
       middle_finger_tip.y < ring_finger_tip.y and \
       ring_finger_tip.y < pinky_finger_tip.y:
        return "Fist"
    elif thumb_tip.y > index_finger_tip.y:
        return "Open Palm"
    else:
        return "Unknown"

def main():
    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Convert the image to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                landmarks = hand_landmarks.landmark
                gesture = get_gesture(landmarks)
                cv2.putText(frame, f"Gesture: {gesture}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('Hand Tracking', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
