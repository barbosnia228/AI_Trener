from __future__ import annotations
import os
import time
import urllib.request
from collections import deque
from typing import List, Optional

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from src.ai.geometry import GeometryEngine
from src.ai.validator import TechniqueValidator
from src.ai.feedback import FeedbackEngine

# ── Model ──────────────────────────────────────────────────────────────────────
_MODEL_PATH = "pose_landmarker.task"
_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# ── Rep counting thresholds ────────────────────────────────────────────────────
_ANGLE_UP   = 160.0
_ANGLE_DOWN =  70.0

_ANGLE_SMOOTH_FRAMES = 5

_MIN_ANGLE_REACHED   = 55.0
_MIN_TIME_DOWN_SEC   = 0.35
_MIN_FRAMES_UP       = 5
_REP_COOLDOWN_FRAMES = 20

# ── Visibility ─────────────────────────────────────────────────────────────────
_VISIBILITY_MIN = 0.35

# ── Body validation ────────────────────────────────────────────────────────────
_BACK_LEVEL_TOLERANCE    = 0.15  # side-view: one shoulder always further
_HIP_STABILITY_TOLERANCE = 0.15  # side-view: hips also appear uneven

# ── Landmark indices ───────────────────────────────────────────────────────────
_L_SHOULDER, _R_SHOULDER = 11, 12
_L_ELBOW,    _R_ELBOW    = 13, 14
_L_WRIST,    _R_WRIST    = 15, 16
_L_HIP,      _R_HIP      = 23, 24
_L_KNEE,     _R_KNEE     = 25, 26
_L_ANKLE,    _R_ANKLE    = 27, 28

_CONNECTIONS = [
    (_L_SHOULDER, _L_ELBOW), (_L_ELBOW, _L_WRIST),
    (_R_SHOULDER, _R_ELBOW), (_R_ELBOW, _R_WRIST),
    (_L_SHOULDER, _R_SHOULDER),
    (_L_SHOULDER, _L_HIP), (_R_SHOULDER, _R_HIP),
    (_L_HIP, _R_HIP),
    (_L_HIP, _L_KNEE), (_L_KNEE, _L_ANKLE),
    (_R_HIP, _R_KNEE), (_R_KNEE, _R_ANKLE),
]

_GREEN  = (0, 184, 148)
_RED    = (48,  48, 214)
_YELLOW = (0,  203, 253)
_WHITE  = (255, 255, 255)
_BLACK  = (0,    0,   0)

_FEEDBACK_INTERVAL = 3.0


def download_model() -> None:
    if not os.path.exists(_MODEL_PATH):
        print(f"[AIEngine] Downloading model -> {_MODEL_PATH} ...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print("[AIEngine] Model downloaded.")


class AIEngine(QObject):

    processed_frame  = pyqtSignal(np.ndarray)
    metrics_updated  = pyqtSignal(float, int, int, int)
    feedback_message = pyqtSignal(str, str)
    set_summary      = pyqtSignal(dict)

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

        download_model()

        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._detector = mp_vision.PoseLandmarker.create_from_options(options)

        self._geometry  = GeometryEngine()
        self._validator = TechniqueValidator()
        self._feedback  = FeedbackEngine()

        # Smoothing buffer
        self._angle_buffer: deque[float] = deque(maxlen=_ANGLE_SMOOTH_FRAMES)

        # Rep state
        self._rep_state: str            = "up"
        self._reps: int                 = 0
        self._rep_frames_in_up: int     = 0
        self._rep_min_angle_seen: float = 180.0
        self._rep_down_start: float     = 0.0   # timestamp входу в DOWN
        self._rep_cooldown: int         = 0

        # Set state
        self._set_active: bool           = False
        self._set_index: int             = 0
        self._set_start_time: float      = 0.0
        self._last_feedback_time: float  = 0.0
        self._errors_this_set: List[str] = []
        self._form_scores: List[int]     = []
        self._current_angle: float       = 0.0

    # ── Set lifecycle ─────────────────────────────────────────────────────────

    @pyqtSlot(int)
    def on_set_started(self, index: int) -> None:
        self._set_index          = index
        self._reps               = 0
        self._rep_state          = "up"
        self._rep_frames_in_up   = 0
        self._rep_min_angle_seen = 180.0
        self._rep_down_start     = 0.0
        self._rep_cooldown       = 0
        self._angle_buffer.clear()
        self._set_active         = True
        self._set_start_time     = time.time()
        self._last_feedback_time = 0.0
        self._errors_this_set    = []
        self._form_scores        = []
        msg = f"Set {index + 1} started!"
        self._feedback.say(msg)
        self.feedback_message.emit(msg, "info")

    @pyqtSlot(int)
    def on_set_finished(self, index: int) -> None:
        if not self._set_active:
            return
        self._set_active = False
        avg_form = (
            int(sum(self._form_scores) / len(self._form_scores))
            if self._form_scores else 0
        )
        summary = {
            "set_index": index,
            "reps":      self._reps,
            "errors":    list(self._errors_this_set),
            "avg_form":  avg_form,
            "duration":  int(time.time() - self._set_start_time),
        }
        self.set_summary.emit(summary)
        msg = f"Set {index + 1} finished. {self._reps} reps."
        self._feedback.say(msg)
        self.feedback_message.emit(msg, "info")

    @pyqtSlot()
    def on_training_stopped(self) -> None:
        self._set_active         = False
        self._reps               = 0
        self._rep_state          = "up"
        self._rep_frames_in_up   = 0
        self._rep_min_angle_seen = 180.0
        self._rep_down_start     = 0.0
        self._rep_cooldown       = 0
        self._angle_buffer.clear()

    # ── Main frame processing ─────────────────────────────────────────────────

    @pyqtSlot(np.ndarray)
    def process_frame(self, bgr: np.ndarray) -> None:
        rgb      = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = self._detector.detect(mp_image)

        frame      = bgr.copy()
        angle      = self._current_angle
        form_score = 0

        if result.pose_landmarks:
            lm = result.pose_landmarks[0]
            h, w = frame.shape[:2]

            raw_angle = self._avg_elbow_angle(lm)
            if raw_angle is not None:
                self._angle_buffer.append(raw_angle)
                smooth_angle = sum(self._angle_buffer) / len(self._angle_buffer)
                self._current_angle = smooth_angle
                angle = smooth_angle

            errors     = self._check_technique(lm)
            form_score = max(0, 100 - len(errors) * 25)

            if self._set_active:
                self._form_scores.append(form_score)
                if raw_angle is not None:
                    self._count_rep(angle)

                if errors:
                    now = time.time()
                    if now - self._last_feedback_time >= _FEEDBACK_INTERVAL:
                        self._last_feedback_time = now
                        msg = errors[0]
                        self._errors_this_set.append(msg)
                        self._feedback.say(msg)
                        self.feedback_message.emit(msg, "warning")

            self._draw_skeleton(frame, lm, w, h, not errors)

        elapsed = int(time.time() - self._set_start_time) if self._set_active else 0
        self._draw_hud(frame, angle, elapsed)

        self.processed_frame.emit(frame)
        self.metrics_updated.emit(angle, self._reps, form_score, elapsed)

    # ── Rep counter ───────────────────────────────────────────────────────────

    def _lm_vis(self, lm, idx: int) -> float:
        return float(getattr(lm[idx], "visibility", 1.0))

    def _avg_elbow_angle(self, lm) -> Optional[float]:
        angles = []
        for sh, el, wr in [(_L_SHOULDER, _L_ELBOW, _L_WRIST),
                            (_R_SHOULDER, _R_ELBOW, _R_WRIST)]:
            if (self._lm_vis(lm, sh) >= _VISIBILITY_MIN
                    and self._lm_vis(lm, el) >= _VISIBILITY_MIN
                    and self._lm_vis(lm, wr) >= _VISIBILITY_MIN):
                angles.append(self._geometry.calculate_angle(
                    [lm[sh].x, lm[sh].y],
                    [lm[el].x, lm[el].y],
                    [lm[wr].x, lm[wr].y],
                ))
        return sum(angles) / len(angles) if angles else None

    def _count_rep(self, angle: float) -> None:
        # Cooldown після зарахованого репа
        if self._rep_cooldown > 0:
            self._rep_cooldown -= 1
            return

        if self._rep_state == "up":
            self._rep_frames_in_up = 0
            if angle < _ANGLE_DOWN:

                self._rep_state          = "down"
                self._rep_min_angle_seen = angle
                self._rep_down_start     = time.time()

        elif self._rep_state == "down":

            self._rep_min_angle_seen = min(self._rep_min_angle_seen, angle)

            if angle > _ANGLE_UP:
                self._rep_frames_in_up += 1
            else:
                self._rep_frames_in_up = 0

            time_in_down = time.time() - self._rep_down_start

            if (self._rep_frames_in_up >= _MIN_FRAMES_UP
                    and time_in_down >= _MIN_TIME_DOWN_SEC
                    and self._rep_min_angle_seen <= _MIN_ANGLE_REACHED):
                self._rep_state          = "up"
                self._rep_frames_in_up   = 0
                self._rep_min_angle_seen = 180.0
                self._rep_down_start     = 0.0
                self._rep_cooldown       = _REP_COOLDOWN_FRAMES
                self._reps              += 1
                msg = f"Rep {self._reps}"
                self._feedback.say(msg)
                self.feedback_message.emit(f"checkmark {msg}", "info")

            # Якщо занадто довго в DOWN без досягнення мінімуму — скидаємо
            # (наприклад людина просто тримає руки зігнутими)
            elif time_in_down > 5.0 and self._rep_min_angle_seen > _MIN_ANGLE_REACHED:
                self._rep_state          = "up"
                self._rep_frames_in_up   = 0
                self._rep_min_angle_seen = 180.0
                self._rep_down_start     = 0.0

    # ── Technique validation ──────────────────────────────────────────────────

    def _check_technique(self, lm) -> List[str]:
        errors: List[str] = []
        if abs(lm[_L_SHOULDER].y - lm[_R_SHOULDER].y) > _BACK_LEVEL_TOLERANCE:
            errors.append("Keep your back straight")
        if abs(lm[_L_HIP].y - lm[_R_HIP].y) > _HIP_STABILITY_TOLERANCE:
            errors.append("Keep hips stable, feet on the floor")
        return errors

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_skeleton(self, frame, lm, w: int, h: int, correct: bool) -> None:
        colour = _GREEN if correct else _RED
        for a, b in _CONNECTIONS:
            if a < len(lm) and b < len(lm):
                cv2.line(frame,
                         (int(lm[a].x * w), int(lm[a].y * h)),
                         (int(lm[b].x * w), int(lm[b].y * h)),
                         colour, 2, cv2.LINE_AA)
        for i in [_L_SHOULDER, _R_SHOULDER, _L_ELBOW, _R_ELBOW,
                  _L_WRIST, _R_WRIST, _L_HIP, _R_HIP, _L_KNEE, _R_KNEE]:
            if i < len(lm):
                cx, cy = int(lm[i].x * w), int(lm[i].y * h)
                cv2.circle(frame, (cx, cy), 5, colour, -1, cv2.LINE_AA)
                cv2.circle(frame, (cx, cy), 5, _WHITE,  1, cv2.LINE_AA)

    def _draw_hud(self, frame, angle: float, elapsed: int) -> None:
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (220, 115), _BLACK, -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        reps_text = f"REPS: {self._reps}"
        cv2.putText(frame, reps_text, (20, 65),
                    cv2.FONT_HERSHEY_DUPLEX, 1.6, _BLACK, 5, cv2.LINE_AA)
        cv2.putText(frame, reps_text, (18, 63),
                    cv2.FONT_HERSHEY_DUPLEX, 1.6, _WHITE, 3, cv2.LINE_AA)

        # Поточний кут — допомагає калібрувати пороги
        angle_text = f"ANG: {angle:.0f}"
        cv2.putText(frame, angle_text, (20, 88),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, _BLACK, 2, cv2.LINE_AA)
        cv2.putText(frame, angle_text, (19, 87),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, _WHITE, 1, cv2.LINE_AA)

        pill_colour = _GREEN if self._set_active else _YELLOW
        status_text = "● ACTIVE" if self._set_active else "● WAITING"
        cv2.putText(frame, status_text, (20, 108),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, _BLACK, 2, cv2.LINE_AA)
        cv2.putText(frame, status_text, (19, 107),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, pill_colour, 1, cv2.LINE_AA)