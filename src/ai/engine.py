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
from src.ai.feedback import FeedbackEngine

_MODEL_PATH = "pose_landmarker.task"
_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

_ANGLE_UP   = 125.0   # angle (degrees) above which the position is considered "up"
_ANGLE_DOWN =  85.0   # angle below which the position is considered "down"

_ANGLE_SMOOTH_FRAMES = 6  # number of frames averaged using a sliding window

_MIN_ANGLE_REACHED   =  70.0  # minimum angle that must be reached during the "down" phase
_MIN_TIME_DOWN_SEC   = 0.25   # minimum time (seconds) spent in the "down" phase
_MIN_FRAMES_UP       = 4      # consecutive frames above _ANGLE_UP required to confirm the return
_REP_COOLDOWN_FRAMES = 15     # frames locked after counting a rep (prevents double-counting)
_VISIBILITY_MIN      = 0.30   # minimum landmark visibility confidence (0–1)

_ELBOW_SYMMETRY_TOLERANCE = 0.20   # max Y difference between elbows (normalised) — bar level check
_ELBOW_FLARE_RATIO        = 2.10   # reserved threshold for elbow flare (not yet used)
_WRIST_BEND_TOLERANCE     = 0.12   # max X offset between wrist and elbow — wrist bend check
_FOOT_LIFT_TOLERANCE      = 0.08   # max ankle rise above baseline (normalised coords)
_FOOT_LIFT_FRAMES         = 8      # frames of foot lift before triggering the cue
_ELBOW_ASYMMETRY_DEG      = 20.0   # max L/R elbow angle difference (degrees)
_ELBOW_ASYMMETRY_FRAMES   = 8      # frames of asymmetry before triggering the cue

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

_GREEN  = (0, 184, 148)   # correct technique
_RED    = (48,  48, 214)  # technique error
_YELLOW = (0,  203, 253)  # accent (min angle in HUD, WAITING status)
_WHITE  = (255, 255, 255) # landmark border
_BLACK  = (0,    0,   0)  # HUD panel background
_FEEDBACK_INTERVAL = 3.0  # seconds between consecutive voice cues


def download_model() -> None:
    """
    Download the PoseLandmarker model from Google Storage if not already present.

    The file is saved in the current working directory as ``pose_landmarker.task``.
    Does nothing if the file already exists.
    """
    if not os.path.exists(_MODEL_PATH):
        print(f"[AIEngine] Downloading model -> {_MODEL_PATH} ...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print("[AIEngine] Model downloaded.")


class AIEngine(QObject):
    """
    Main AI engine — processes video frames and emits Qt signals.

    Inherits from ``QObject`` to integrate with the PyQt6 signal-slot architecture.
    All public methods should be called from Qt slots or the main thread.

    Signals
    -------
    processed_frame : np.ndarray
        BGR frame with skeleton and HUD rendered, ready for display.
    metrics_updated : (float, int, int, int)
        Four metrics: elbow angle, rep count, form score (0–100),
        elapsed set duration in seconds.
    feedback_message : (str, str)
        Pair of (message text, type: "info" | "warning") for display in the UI.
    set_summary : dict
        Set summary dict emitted when a set ends.
        Keys: set_index, reps, errors, avg_form, duration.
    """

    processed_frame  = pyqtSignal(np.ndarray)
    metrics_updated  = pyqtSignal(float, int, int, int)
    feedback_message = pyqtSignal(str, str)
    set_summary      = pyqtSignal(dict)

    def __init__(self, parent: QObject = None) -> None:
        """
        Initialise the AI engine: download the model, create the MediaPipe detector,
        and set up helper engines (geometry, voice feedback).
        Resets all set and rep state variables to their initial values.

        Parameters
        ----------
        parent : QObject, optional
            Qt parent object for lifetime management.
        """
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

        self._geometry = GeometryEngine()
        self._feedback = FeedbackEngine()

        self._angle_buffer: deque[float] = deque(maxlen=_ANGLE_SMOOTH_FRAMES)

        self._rep_state: str            = "up"
        self._reps: int                 = 0
        self._rep_frames_in_up: int     = 0
        self._rep_min_angle_seen: float = 180.0
        self._rep_down_start: float     = 0.0
        self._rep_cooldown: int         = 0

        self._foot_lift_frames: int  = 0
        self._ankle_baseline: float  = None
        self._elbow_asym_frames: int = 0

        self._set_active: bool           = False
        self._set_index: int             = 0
        self._set_start_time: float      = 0.0
        self._last_feedback_time: float  = 0.0
        self._errors_this_set: List[str] = []
        self._form_scores: List[int]     = []
        self._current_angle: float       = 0.0

    @pyqtSlot(int)
    def on_set_started(self, index: int) -> None:
        """
        Slot called by the UI when the user starts a new set.

        Resets rep counters, angle buffer, error history, and form score list.
        Emits a voice cue and a ``feedback_message`` signal.

        Parameters
        ----------
        index : int
            Zero-based set number. Displayed to the user as ``index + 1``.
        """
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
        self._ankle_baseline     = None
        self._foot_lift_frames   = 0
        self._elbow_asym_frames  = 0
        msg = f"Set {index + 1} started!"
        self._feedback.say(msg)
        self.feedback_message.emit(msg, "info")

    @pyqtSlot(int)
    def on_set_finished(self, index: int) -> None:
        """
        Slot called by the UI when a set is completed.

        Computes the average form score across all frames of the set,
        builds a summary dict, and emits the ``set_summary`` signal.
        Does nothing if no set was active.

        Parameters
        ----------
        index : int
            Zero-based index of the finished set.

        Emits
        -----
        set_summary : dict
            Keys: set_index (int), reps (int), errors (list[str]),
            avg_form (int, 0–100), duration (int, seconds).
        """
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
        """
        Slot called when training is interrupted (e.g. window closed).

        Deactivates the current set and resets the entire rep state machine
        to its initial state without emitting a summary.
        """
        self._set_active         = False
        self._reps               = 0
        self._rep_state          = "up"
        self._rep_frames_in_up   = 0
        self._rep_min_angle_seen = 180.0
        self._rep_down_start     = 0.0
        self._rep_cooldown       = 0
        self._angle_buffer.clear()

    @pyqtSlot(np.ndarray)
    def process_frame(self, bgr: np.ndarray) -> None:
        """
        Main per-frame processing method — called once per video frame.

        Executes the full pipeline:
          1. BGR → RGB conversion and MediaPipe pose detection.
          2. Smoothed elbow angle calculation (_avg_elbow_angle).
          3. Rep counting (_count_rep) when landmarks are visible.
          4. Technique checking (_check_technique) and error collection.
          5. Form score: 100 − (error_count × 25), minimum 0.
          6. Voice + visual feedback for the first error every _FEEDBACK_INTERVAL s.
          7. Skeleton and HUD rendering on the frame.
          8. Emission of ``processed_frame`` and ``metrics_updated`` signals.

        Parameters
        ----------
        bgr : np.ndarray
            Video frame in BGR format (OpenCV default), shape (H, W, 3).
        """
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

            if raw_angle is not None:
                self._count_rep(angle)

            if self._set_active:
                self._form_scores.append(form_score)
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

    def _lm_vis(self, lm, idx: int) -> float:
        """
        Return the visibility confidence of a landmark at the given index.

        Falls back to 1.0 if the landmark has no ``visibility`` attribute
        (e.g. older versions of MediaPipe).

        Parameters
        ----------
        lm : list[NormalizedLandmark]
            Landmark list from a single pose detection result.
        idx : int
            Landmark index (e.g. _L_ELBOW = 13).

        Returns
        -------
        float
            Visibility value in the range [0.0, 1.0].
        """
        return float(getattr(lm[idx], "visibility", 1.0))

    def _avg_elbow_angle(self, lm) -> Optional[float]:
        """
        Compute the average elbow angle across both arms.

        For each arm, checks the visibility of the shoulder–elbow–wrist triplet.
        A landmark is included only when all three points have visibility ≥ _VISIBILITY_MIN.
        The average is computed only from the visible arms.

        Parameters
        ----------
        lm : list[NormalizedLandmark]
            Landmark list from the current frame.

        Returns
        -------
        float | None
            Averaged elbow angle in degrees, or ``None`` if neither elbow
            is sufficiently visible.
        """
        angles = []
        for sh, el, wr in [(_L_SHOULDER, _L_ELBOW, _L_WRIST),
                            (_R_SHOULDER, _R_ELBOW, _R_WRIST)]:
            vis_ok = (self._lm_vis(lm, sh) >= _VISIBILITY_MIN
                      and self._lm_vis(lm, el) >= _VISIBILITY_MIN
                      and self._lm_vis(lm, wr) >= _VISIBILITY_MIN)
            if vis_ok:
                a = self._geometry.calculate_angle(
                    [lm[sh].x, lm[sh].y],
                    [lm[el].x, lm[el].y],
                    [lm[wr].x, lm[wr].y],
                )
                angles.append(a)
        return sum(angles) / len(angles) if angles else None

    def _count_rep(self, angle: float) -> None:
        """
        Run the rep-counting state machine on the current smoothed angle.

        States: "up" (starting position) → "down" (bar lowering) → "up".
        A rep is counted when:
          - The angle rises above _ANGLE_UP for at least _MIN_FRAMES_UP consecutive frames,
          - At least _MIN_TIME_DOWN_SEC was spent in the "down" phase,
          - The minimum angle reached during "down" was ≤ _MIN_ANGLE_REACHED.

        After a valid rep a cooldown of _REP_COOLDOWN_FRAMES blocks further counting.
        If the user stays in "down" for more than 6 seconds without reaching the
        required angle, the machine resets to "up" without counting a rep.

        Parameters
        ----------
        angle : float
            Current smoothed elbow angle in degrees.
        """
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

            elif time_in_down > 6.0 and self._rep_min_angle_seen > _MIN_ANGLE_REACHED:
                self._rep_state          = "up"
                self._rep_frames_in_up   = 0
                self._rep_min_angle_seen = 180.0
                self._rep_down_start     = 0.0

    def _check_technique(self, lm) -> List[str]:
        """
        Analyse the current landmarks for technique errors and return a list of cues.

        Checks performed (in priority order):
          1. **Bar symmetry** — Y difference between left and right elbows exceeds
             _ELBOW_SYMMETRY_TOLERANCE (bar not horizontal).
          2. **Wrist bend** — X offset between wrist and elbow exceeds
             _WRIST_BEND_TOLERANCE (checked only during the "down" phase).
          3. **Foot lift** — ankles rise above the established baseline by more than
             _FOOT_LIFT_TOLERANCE for at least _FOOT_LIFT_FRAMES consecutive frames.
          4. **Elbow asymmetry** — L/R elbow angle difference exceeds
             _ELBOW_ASYMMETRY_DEG for at least _ELBOW_ASYMMETRY_FRAMES consecutive
             frames (checked only during "down" when all landmarks are visible).

        Checks 3 and 4 use hysteresis (frame counters) to prevent cue flickering
        caused by momentary detection noise.

        Parameters
        ----------
        lm : list[NormalizedLandmark]
            Landmark list from the current frame.

        Returns
        -------
        list[str]
            List of human-readable error cues (may be empty).
            Callers should treat errors[0] as the highest-priority cue.
        """
        errors: List[str] = []

        l_el_vis  = self._lm_vis(lm, _L_ELBOW)    >= _VISIBILITY_MIN
        r_el_vis  = self._lm_vis(lm, _R_ELBOW)    >= _VISIBILITY_MIN
        l_wr_vis  = self._lm_vis(lm, _L_WRIST)    >= _VISIBILITY_MIN
        r_wr_vis  = self._lm_vis(lm, _R_WRIST)    >= _VISIBILITY_MIN
        l_sh_vis  = self._lm_vis(lm, _L_SHOULDER) >= _VISIBILITY_MIN
        r_sh_vis  = self._lm_vis(lm, _R_SHOULDER) >= _VISIBILITY_MIN
        l_ank_vis = self._lm_vis(lm, _L_ANKLE)    >= _VISIBILITY_MIN
        r_ank_vis = self._lm_vis(lm, _R_ANKLE)    >= _VISIBILITY_MIN
        if l_el_vis and r_el_vis:
            if abs(lm[_L_ELBOW].y - lm[_R_ELBOW].y) > _ELBOW_SYMMETRY_TOLERANCE:
                errors.append("Lower the bar evenly")
        if self._rep_state == "down":
            wrist_err = False
            if l_el_vis and l_wr_vis:
                if abs(lm[_L_WRIST].x - lm[_L_ELBOW].x) > _WRIST_BEND_TOLERANCE:
                    wrist_err = True
            if r_el_vis and r_wr_vis:
                if abs(lm[_R_WRIST].x - lm[_R_ELBOW].x) > _WRIST_BEND_TOLERANCE:
                    wrist_err = True
            if wrist_err:
                errors.append("Keep wrists straight over elbows")
        if l_ank_vis and r_ank_vis:
            avg_ankle_y = (lm[_L_ANKLE].y + lm[_R_ANKLE].y) / 2.0
            if self._ankle_baseline is None:
                self._ankle_baseline = avg_ankle_y
            if avg_ankle_y > self._ankle_baseline:
                self._ankle_baseline = avg_ankle_y * 0.95 + self._ankle_baseline * 0.05
            lift = self._ankle_baseline - avg_ankle_y
            if lift > _FOOT_LIFT_TOLERANCE:
                self._foot_lift_frames += 1
            else:
                self._foot_lift_frames = max(0, self._foot_lift_frames - 1)
            if self._foot_lift_frames >= _FOOT_LIFT_FRAMES:
                errors.append("Keep feet flat on the floor")
        else:
            self._foot_lift_frames = 0

        if (self._rep_state == "down"
                and l_el_vis and r_el_vis
                and l_wr_vis and r_wr_vis
                and l_sh_vis and r_sh_vis):
            l_angle = self._geometry.calculate_angle(
                [lm[_L_SHOULDER].x, lm[_L_SHOULDER].y],
                [lm[_L_ELBOW].x, lm[_L_ELBOW].y],
                [lm[_L_WRIST].x, lm[_L_WRIST].y],
            )
            r_angle = self._geometry.calculate_angle(
                [lm[_R_SHOULDER].x, lm[_R_SHOULDER].y],
                [lm[_R_ELBOW].x, lm[_R_ELBOW].y],
                [lm[_R_WRIST].x, lm[_R_WRIST].y],
            )
            if abs(l_angle - r_angle) > _ELBOW_ASYMMETRY_DEG:
                self._elbow_asym_frames += 1
            else:
                self._elbow_asym_frames = max(0, self._elbow_asym_frames - 1)
            if self._elbow_asym_frames >= _ELBOW_ASYMMETRY_FRAMES:
                errors.append("Keep shoulders level")

        return errors

    def _draw_skeleton(self, frame, lm, w: int, h: int, correct: bool) -> None:
        """
        Draw the pose skeleton on the frame using OpenCV.

        Connection lines and joint circles are green when technique is correct
        (``correct=True``) or red when errors are detected.
        Each joint is outlined in white for readability on any background.

        Parameters
        ----------
        frame : np.ndarray
            BGR frame to modify in-place.
        lm : list[NormalizedLandmark]
            Landmark list with normalised coordinates in [0, 1].
        w, h : int
            Frame width and height in pixels (used to scale coordinates).
        correct : bool
            ``True`` → green skeleton; ``False`` → red skeleton.
        """
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
        """
        Draw a semi-transparent HUD panel in the top-left corner of the frame.

        Panel contents:
          - Rep counter (REPS) — large font.
          - Current elbow angle and state machine status (UP / DOWN).
          - Minimum angle reached during the current descent (MIN) —
            shown only in the "down" phase, in yellow.
          - Status indicator: ● ACTIVE (green) or ● WAITING (yellow).

        Each text element is rendered twice: first with a thick black stroke
        (shadow), then with a thinner white layer — ensuring readability on
        any background colour.

        Parameters
        ----------
        frame : np.ndarray
            BGR frame to modify in-place.
        angle : float
            Current smoothed elbow angle in degrees.
        elapsed : int
            Time elapsed since the start of the current set in seconds
            (0 when no set is active).
        """
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (240, 125), _BLACK, -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        reps_text = f"REPS: {self._reps}"
        cv2.putText(frame, reps_text, (20, 65),
                    cv2.FONT_HERSHEY_DUPLEX, 1.6, _BLACK, 5, cv2.LINE_AA)
        cv2.putText(frame, reps_text, (18, 63),
                    cv2.FONT_HERSHEY_DUPLEX, 1.6, _WHITE, 3, cv2.LINE_AA)

        angle_text = f"ANG: {angle:.0f}  [{self._rep_state.upper()}]"
        cv2.putText(frame, angle_text, (20, 90),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, _BLACK, 2, cv2.LINE_AA)
        cv2.putText(frame, angle_text, (19, 89),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, _WHITE, 1, cv2.LINE_AA)

        if self._rep_state == "down":
            min_text = f"MIN: {self._rep_min_angle_seen:.0f}"
            cv2.putText(frame, min_text, (20, 103),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45, _BLACK, 2, cv2.LINE_AA)
            cv2.putText(frame, min_text, (19, 102),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45, _YELLOW, 1, cv2.LINE_AA)

        pill_colour = _GREEN if self._set_active else _YELLOW
        status_text = "● ACTIVE" if self._set_active else "● WAITING"
        cv2.putText(frame, status_text, (20, 118),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, _BLACK, 2, cv2.LINE_AA)
        cv2.putText(frame, status_text, (19, 117),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, pill_colour, 1, cv2.LINE_AA)