import json
import os


class TechniqueValidator:
    def __init__(self, config_path="config.json"):
        self.config = {"elbow_min_angle": 45, "elbow_max_angle": 75}

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    self.config = json.load(f)
            except json.JSONDecodeError:
                print("Error: Invalid JSON format in config.json. Using default values.")
        else:
            print(f"Warning: File {config_path} not found. Using default settings.")

    def validate_elbow_position(self, angle: float) -> tuple[bool, str]:
        if angle is None:
            return False, "Movement not detected"

        min_a = self.config.get("elbow_min_angle", 45)
        max_a = self.config.get("elbow_max_angle", 75)

        if angle < min_a:
            return False, "Elbows too close to the body"
        elif angle > max_a:
            return False, "Elbows flaring too wide"

        return True, "Good form"

    def is_elbow_correct(self, angle: float) -> bool:
        is_correct, _ = self.validate_elbow_position(angle)
        return is_correct