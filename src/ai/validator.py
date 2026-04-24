import json
import os


class TechniqueValidator:
    def __init__(self, config_path='config.json'):
        self.config = {"elbow_min_angle": 45, "elbow_max_angle": 75}

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
            except json.JSONDecodeError:
                print("Błąd: Niepoprawny format JSON w config.json. Używam domyślnych wartości.")
        else:
            print(f"Uwaga: Nie znaleziono pliku {config_path}. Używam domyślnych ustawień.")

    def validate_elbow_position(self, angle):

        if angle is None:
            return False, "Nie wykryto ruchu"

        min_a = self.config.get('elbow_min_angle', 45)
        max_a = self.config.get('elbow_max_angle', 75)

        if angle < min_a:
            return False, "Łokcie zbyt blisko tułowia"
        elif angle > max_a:
            return False, "Łokcie zbyt szeroko"

        return True, "Pozycja poprawna"

    def is_elbow_correct(self, angle):
        is_correct, _ = self.validate_elbow_position(angle)
        return is_correct