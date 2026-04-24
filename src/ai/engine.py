import cv2
import mediapipe as mp
import time
from src.ai.geometry import GeometryEngine
from src.ai.validator import TechniqueValidator
from src.ai.feedback import FeedbackEngine


class AIEngine:
    def __init__(self):
        self.mp_pose = mp.solutions.pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.geometry = GeometryEngine()
        self.validator = TechniqueValidator()
        self.feedback = FeedbackEngine()
        self.last_feedback_time = 0

    def process_video(self):
        cap = cv2.VideoCapture(0)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.mp_pose.process(rgb_frame)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                shoulder = [landmarks[11].x, landmarks[11].y]
                elbow = [landmarks[13].x, landmarks[13].y]
                wrist = [landmarks[15].x, landmarks[15].y]

                angle = self.geometry.calculate_angle(shoulder, elbow, wrist)

                is_correct, msg = self.validator.validate_elbow_position(angle)

                if not is_correct:
                    current_time = time.time()
                    if current_time - self.last_feedback_time > 3:
                        self.feedback.say(msg)
                        self.last_feedback_time = current_time

                mp.solutions.drawing_utils.draw_landmarks(
                    frame, results.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS
                )

            cv2.imshow('AI Trener - Wyciskanie', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()