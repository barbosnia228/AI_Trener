"""
window.py — Three main PyQt6 windows for AI Trainer.

Windows
-------
TrainingControlWindow  — set config, start/stop training, per-set buttons, history and statistics buttons
AnalysisWindow         — real-time exercise metrics for the current set/session
CameraWindow           — live camera feed with start/stop button, FPS, status

Quick start (main.py)
---------------------
    app      = QApplication(sys.argv)
    ctrl     = TrainingControlWindow()
    analysis = AnalysisWindow()
    cam      = CameraWindow()

    ctrl.training_started.connect(cam.start)
    ctrl.training_stopped.connect(cam.stop)
    ctrl.set_started.connect(analysis.on_set_started)

    ctrl.show(); analysis.show(); cam.show()
    sys.exit(app.exec())
"""

from __future__ import annotations

import sys

import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy,
    QSpinBox, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont, QScreen

from src.gui.components import (
    PrimaryButton, SuccessButton, DangerButton, SecondaryButton,
    PALETTE, set_font,
)
from typing import Optional

# ── App-wide stylesheet ────────────────────────────────────────────────────────
APP_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {PALETTE['bg']};
    color: {PALETTE['text']};
    font-family: 'Segoe UI', sans-serif;
}}
QSpinBox, QDoubleSpinBox {{
    background: {PALETTE['panel']};
    color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 30px;
}}
QLabel {{ background: transparent; }}
QScrollBar:vertical {{
    background: {PALETTE['bg']}; width: 6px;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE['border']}; border-radius: 3px;
}}
"""


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {PALETTE['border']};")
    return line


def _label(text: str, size: int = 10, muted: bool = False, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    set_font(lbl, size, bold)
    colour = PALETTE["muted"] if muted else PALETTE["text"]
    lbl.setStyleSheet(f"color: {colour};")
    return lbl


# ══════════════════════════════════════════════════════════════════════════════
# Window 1 — Training Control
# ══════════════════════════════════════════════════════════════════════════════

class _SetRow(QFrame):
    """One row per set: label + Start / Finish / Skip buttons."""

    def __init__(self, index: int, reps: int, weight: float, on_start, on_finish, on_skip, parent=None):
        super().__init__(parent)
        self._done = False
        self._reps = reps
        self._weight = weight
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 8px;
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        self._lbl = _label(f"Set {index + 1}", size=11, bold=True)
        self._lbl.setFixedWidth(70)
        row.addWidget(self._lbl)

        self._info = _label(f"{reps} reps · {weight:.1f} kg", size=9, muted=True)
        row.addWidget(self._info, 1)

        self._status = _label("Pending", size=9, muted=True)
        self._status.setFixedWidth(70)
        row.addWidget(self._status)

        self._spin_weight = QDoubleSpinBox()
        self._spin_weight.setRange(0, 500)
        self._spin_weight.setSingleStep(2.5)
        self._spin_weight.setValue(weight)
        self._spin_weight.setSuffix(" kg")
        self._spin_weight.valueChanged.connect(self._update_info)
        row.addWidget(self._spin_weight)

        self._btn_start  = SuccessButton("Start")
        self._btn_finish = PrimaryButton("Finish")
        self._btn_skip   = SecondaryButton("Skip")
        for btn in (self._btn_start, self._btn_finish, self._btn_skip):
            btn.setFixedWidth(80)
            btn.setMinimumHeight(36)
            row.addWidget(btn)

        self._btn_finish.setEnabled(False)
        self._btn_start.clicked.connect(lambda: on_start(index))
        self._btn_finish.clicked.connect(lambda: on_finish(index))
        self._btn_skip.clicked.connect(lambda: on_skip(index))

    def _update_info(self):
        self._info.setText(f"{self._reps} reps · {self._spin_weight.value():.1f} kg")



    def mark_active(self):
        self._status.setText("Active")
        self._status.setStyleSheet(f"color: {PALETTE['warning'] if 'warning' in PALETTE else '#fdcb6e'};")
        self._btn_start.setEnabled(False)
        self._btn_finish.setEnabled(True)
        self._btn_skip.setEnabled(False)
        self.setStyleSheet(f"""
            QFrame {{ background: #1e1a00; border: 1px solid {PALETTE['border']}; border-radius: 8px; }}
        """)

    def mark_done(self, skipped=False):
        text   = "Skipped" if skipped else "Done ✓"
        colour = PALETTE["muted"] if skipped else PALETTE["success"]
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {colour};")
        for btn in (self._btn_start, self._btn_finish, self._btn_skip):
            btn.setEnabled(False)
        self.setStyleSheet(f"""
            QFrame {{ background: {PALETTE['panel']}; border: 1px solid {PALETTE['border']}; border-radius: 8px; }}
        """)

class TrainingControlWindow(QMainWindow):
    def _set_geometry(self, left_frac: float, top_frac: float, width_frac: float, height_frac: float) -> None:
        """Set window geometry as fractions of primary screen."""
        screen = QApplication.primaryScreen().geometry()
        screen_w, screen_h = screen.width(), screen.height()
        x = int(screen_w * left_frac)
        y = int(screen_h * top_frac)
        w = int(screen_w * width_frac)
        h = int(screen_h * height_frac)
        # Clamp to screen bounds
        x = max(0, min(x, screen_w - 100))
        y = max(0, min(y, screen_h - 100))
        w = min(w, screen_w - x - 20)
        h = min(h, screen_h - y - 20)
        # Small screen stack vertically
        if screen_w < 1200:
            if self.windowTitle() == "🏋️  AI Trainer — Control":
                self.setGeometry(x, y, w, int(0.3 * screen_h))
            elif self.windowTitle() == "⚡  AI Trainer — Live Analysis":
                self.setGeometry(x, int(0.35 * screen_h), w, int(0.25 * screen_h))
            elif self.windowTitle() == "📷  AI Trainer — Camera Feed":
                self.setGeometry(x, int(0.62 * screen_h), w, int(0.35 * screen_h))
            else:
                self.setGeometry(x, y, w, h)
        else:
            self.setGeometry(x, y, w, h)
    """
    Signals
    -------
    training_started()
    training_stopped()
    set_started(index: int)
    set_finished(index: int)
    set_skipped(index: int)
    history_requested()
    stats_requested()
    """

    training_started  = pyqtSignal()
    training_stopped  = pyqtSignal()
    set_started       = pyqtSignal(int)
    set_finished      = pyqtSignal(int)
    set_skipped       = pyqtSignal(int)
    stats_requested   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🏋️  AI Trainer — Control")
        self._set_geometry(0.05, 0.05, 0.40, 0.50)
        self.setMinimumHeight(620)

        self._rows: list[_SetRow] = []
        self._active: Optional[int]  = None
        self._elapsed = 0

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("AI TRAINER")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {PALETTE['accent']};")
        hdr.addWidget(title)
        hdr.addStretch()
        self._btn_stats   = SecondaryButton("📊 Stats")
        self._btn_stats.clicked.connect(self.stats_requested)
        hdr.addWidget(self._btn_stats)
        root.addLayout(hdr)
        root.addWidget(_separator())

        # ── config ──────────────────────────────────────────────────────────
        root.addWidget(_label("Workout Configuration", size=10, muted=True))

        grid = QHBoxLayout()
        grid.setSpacing(12)
        for spin_attr, label_text, mn, mx, val, suffix in [
            ("_spin_sets",   "Sets",     1, 20,  4,  " sets"),
            ("_spin_reps",   "Reps",     1, 50, 10,  " reps"),
        ]:
            col = QVBoxLayout()
            col.addWidget(_label(label_text, size=9, muted=True))
            if spin_attr == "_spin_weight":
                spin = QDoubleSpinBox()
                spin.setSingleStep(2.5)
            else:
                spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(val)
            spin.setSuffix(suffix)
            col.addWidget(spin)
            setattr(self, spin_attr, spin)
            grid.addLayout(col)
        root.addLayout(grid)

        # ── start / stop ────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        self._btn_start = SuccessButton("▶  Start Training")
        self._btn_stop  = DangerButton("■  Stop Training")
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._start)
        self._btn_stop.clicked.connect(self._stop)
        ctrl.addWidget(self._btn_start)
        ctrl.addWidget(self._btn_stop)
        root.addLayout(ctrl)

        # ── quick stats ─────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        self._lbl_elapsed = _label("⏱  00:00", size=10)
        self._lbl_sets    = _label("Sets: 0 / 0", size=10, muted=True)
        stats_row.addWidget(self._lbl_elapsed)
        stats_row.addStretch()
        stats_row.addWidget(self._lbl_sets)
        root.addLayout(stats_row)

        root.addWidget(_separator())
        root.addWidget(_label("Exercise Sets", size=10, muted=True))

        # ── set list ────────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {PALETTE['border']}; border-radius: 8px; }}")

        self._sets_widget = QWidget()
        self._sets_widget.setStyleSheet(f"background: {PALETTE['panel']};")
        self._sets_layout = QVBoxLayout(self._sets_widget)
        self._sets_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._sets_layout.setContentsMargins(8, 8, 8, 8)
        self._sets_layout.setSpacing(6)

        scroll.setWidget(self._sets_widget)
        root.addWidget(scroll, 1)

        # ── status ──────────────────────────────────────────────────────────
        self._status_lbl = _label("Configure your workout and press Start.", size=9, muted=True)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status_lbl)

        # timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── private ────────────────────────────────────────────────────────────────

    def _start(self):
        n = self._spin_sets.value()
        reps = self._spin_reps.value()

        # rebuild rows
        for row in self._rows:
            self._sets_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._active = None

        for i in range(n):
            row = _SetRow(i, reps, 60.0, self._on_start, self._on_finish, self._on_skip)
            self._sets_layout.addWidget(row)
            self._rows.append(row)

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        for sp in (self._spin_sets, self._spin_reps):
            sp.setEnabled(False)

        self._elapsed = 0
        self._timer.start(1000)
        self._update_sets_label()
        self._status_lbl.setText("Training active — press Start on your first set.")
        self.training_started.emit()

    def _stop(self):
        self._timer.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        for sp in (self._spin_sets, self._spin_reps):
            sp.setEnabled(True)
        self._status_lbl.setText("Training stopped.")
        self.training_stopped.emit()

    def _on_start(self, idx: int):
        if self._active is not None:
            return
        self._rows[idx].mark_active()
        self._active = idx
        self._status_lbl.setText(f"Set {idx + 1} in progress…")
        self.set_started.emit(idx)

    def _on_finish(self, idx: int):
        self._rows[idx].mark_done()
        self._active = None
        self._update_sets_label()
        self._status_lbl.setText(f"Set {idx + 1} done! Rest before next set.")
        self.set_finished.emit(idx)
        self._check_all_done()

    def _on_skip(self, idx: int):
        self._rows[idx].mark_done(skipped=True)
        self._update_sets_label()
        self.set_skipped.emit(idx)
        self._check_all_done()

    def _check_all_done(self):
        if self._rows and all(
            row._status.text() in ("Done ✓", "Skipped") for row in self._rows
        ):
            self._status_lbl.setText("🎉 All sets complete!")
            self._stop()

    def _update_sets_label(self):
        done  = sum(1 for r in self._rows if r._status.text() == "Done ✓")
        total = len(self._rows)
        self._lbl_sets.setText(f"Sets: {done} / {total}")

    def _tick(self):
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self._lbl_elapsed.setText(f"⏱  {m:02d}:{s:02d}")


# ══════════════════════════════════════════════════════════════════════════════
# Window 2 — Live Analysis
# ══════════════════════════════════════════════════════════════════════════════

class AnalysisWindow(QMainWindow):
    """
    Shows real-time metrics for the current set and accumulated session totals.

    Feed data each frame via :meth:`update`.
    update(angle, reps, form_score, elapsed_sec)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡  AI Trainer — Live Analysis")
        TrainingControlWindow._set_geometry(self, 0.48, 0.05, 0.25, 0.45)
        self.setMinimumHeight(540)

        self._session_reps   = 0
        self._session_sets   = 0
        self._session_errors = 0

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.addWidget(_label("⚡  Live Analysis", size=15, bold=True))
        hdr.addStretch()
        self._indicator = _label("● Idle", size=10, muted=True)
        hdr.addWidget(self._indicator)
        root.addLayout(hdr)
        root.addWidget(_separator())

        # ── current set ─────────────────────────────────────────────────────
        root.addWidget(_label("Current Set", size=10, muted=True))
        set_grid = QHBoxLayout()
        set_grid.setSpacing(8)
        self._v_reps  = self._metric_col(set_grid, "Reps",       "0")
        self._v_angle = self._metric_col(set_grid, "Angle",      "—°")
        self._v_form  = self._metric_col(set_grid, "Form",       "—%")
        self._v_time  = self._metric_col(set_grid, "Set Time",   "00:00")
        root.addLayout(set_grid)

        root.addWidget(_separator())

        # ── session totals ───────────────────────────────────────────────────
        root.addWidget(_label("Session Totals", size=10, muted=True))
        sess_grid = QHBoxLayout()
        sess_grid.setSpacing(8)
        self._s_reps   = self._metric_col(sess_grid, "Total Reps", "0")
        self._s_sets   = self._metric_col(sess_grid, "Sets Done",  "0")
        self._s_errors = self._metric_col(sess_grid, "Errors",     "0")
        root.addLayout(sess_grid)

        root.addWidget(_separator())

        # ── feedback log ─────────────────────────────────────────────────────
        root.addWidget(_label("Feedback", size=10, muted=True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: 1px solid {PALETTE['border']}; border-radius: 8px; }}
        """)
        self._log_widget = QWidget()
        self._log_widget.setStyleSheet(f"background: {PALETTE['panel']};")
        self._log_layout = QVBoxLayout(self._log_widget)
        self._log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._log_layout.setContentsMargins(8, 8, 8, 8)
        self._log_layout.setSpacing(3)
        scroll.setWidget(self._log_widget)
        root.addWidget(scroll, 1)

        self._log_entries = []

    # ── helpers ───────────────────────────────────────────────────────────────

    def _metric_col(self, layout, label: str, value: str) -> QLabel:
        """Add a value+label column to a layout, return the value label."""
        col = QVBoxLayout()
        col.setSpacing(2)
        v = QLabel(value)
        set_font(v, 18, bold=True)
        v.setStyleSheet(f"color: {PALETTE['text']};")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        k = _label(label, size=8, muted=True)
        k.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 8px;
            }}
        """)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.addWidget(v)
        inner.addWidget(k)
        layout.addWidget(card)
        return v

    # ── public API ────────────────────────────────────────────────────────────

    def update(self, angle: float, reps: int, form_score: int, elapsed: int) -> None:
        """Call this every frame from your backend worker thread (via queued signal)."""
        self._v_reps.setText(str(reps))
        self._v_angle.setText(f"{angle:.1f}°")
        self._v_form.setText(f"{form_score}%")
        m, s = divmod(elapsed, 60)
        self._v_time.setText(f"{m:02d}:{s:02d}")

        colour = (PALETTE["success"] if form_score >= 75
                  else "#fdcb6e" if form_score >= 45 else PALETTE["danger"])
        self._v_form.setStyleSheet(f"color: {colour};")

    def add_feedback(self, message: str, level: str = "info") -> None:
        """level: 'info' | 'warning' | 'error'"""
        colour = {"info": PALETTE["muted"],
                  "warning": "#fdcb6e",
                  "error": PALETTE["danger"]}.get(level, PALETTE["muted"])
        lbl = QLabel(f"• {message}")
        set_font(lbl, 9)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {colour}; background: transparent;")
        self._log_layout.addWidget(lbl)
        self._log_entries.append(lbl)
        if len(self._log_entries) > 40:
            old = self._log_entries.pop(0)
            self._log_layout.removeWidget(old)
            old.deleteLater()
        if level == "error":
            self._session_errors += 1
            self._s_errors.setText(str(self._session_errors))

    def reset_set(self) -> None:
        self._v_reps.setText("0")
        self._v_angle.setText("—°")
        self._v_form.setText("—%")
        self._v_time.setText("00:00")

    # ── slots ─────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def on_training_started(self) -> None:
        self._indicator.setText("● Active")
        self._indicator.setStyleSheet(f"color: {PALETTE['success']}; font-weight: bold;")
        self._session_reps = self._session_sets = self._session_errors = 0
        self._s_reps.setText("0")
        self._s_sets.setText("0")
        self._s_errors.setText("0")
        self.reset_set()

    @pyqtSlot()
    def on_training_stopped(self) -> None:
        self._indicator.setText("● Idle")
        self._indicator.setStyleSheet(f"color: {PALETTE['muted']};")

    @pyqtSlot(int)
    def on_set_started(self, _: int) -> None:
        self.reset_set()

    @pyqtSlot(int)
    def on_set_finished(self, _: int) -> None:
        reps = int(self._v_reps.text())
        self._session_reps += reps
        self._session_sets += 1
        self._s_reps.setText(str(self._session_reps))
        self._s_sets.setText(str(self._session_sets))


# ══════════════════════════════════════════════════════════════════════════════
# Window 3 — Camera Feed
# ══════════════════════════════════════════════════════════════════════════════

class CameraWorker(QThread):
    frame_signal = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.cap = None

    def start_capture(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: Could not open camera.")
            return
        self.running = True
        self.start()

    def stop_capture(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame_signal.emit(frame)
            cv2.waitKey(1)

class CameraWindow(QMainWindow):
    """
    Displays the live camera frame.

    Call :meth:`update_frame(bgr_numpy_array)` from your OpenCV thread —
    it is thread-safe via a queued signal.

    Signals
    -------
    camera_started()
    camera_stopped()
    """

    camera_started = pyqtSignal()
    camera_stopped = pyqtSignal()

    _frame_signal = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📷  AI Trainer — Camera Feed")
        TrainingControlWindow._set_geometry(self, 0.05, 0.52, 0.35, 0.55)

        self._running = False
        self._frames  = 0

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── video label ──────────────────────────────────────────────────────
        self._video = QLabel()
        self._video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video.setStyleSheet(f"""
            background: #050505;
            border: 2px solid {PALETTE['border']};
            border-radius: 10px;
        """)
        self._video.setMinimumHeight(380)
        self._show_placeholder()
        root.addWidget(self._video, 1)

        # ── bottom bar ───────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(16)

        self._status_dot = QLabel("● Inactive")
        self._status_dot.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px;")
        bar.addWidget(self._status_dot)

        self._fps_lbl = QLabel("FPS: —")
        self._fps_lbl.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 10px;")
        bar.addWidget(self._fps_lbl)

        bar.addStretch()

        self._btn_toggle = SuccessButton("▶  Start Camera")
        self._btn_toggle.setFixedWidth(150)
        self._btn_toggle.clicked.connect(self._toggle)
        bar.addWidget(self._btn_toggle)

        root.addLayout(bar)

        # ── fps timer ────────────────────────────────────────────────────────
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)

        self.worker = CameraWorker(self)
        self.worker.frame_signal.connect(self.update_frame)

        # thread-safe frame relay
        self._frame_signal.connect(self._render_frame, Qt.ConnectionType.QueuedConnection)

    # ── public API ────────────────────────────────────────────────────────────

    def update_frame(self, bgr: "np.ndarray") -> None:
        """Thread-safe. Pass annotated BGR frame from OpenCV."""
        self._frame_signal.emit(bgr)
        self._frames += 1

    @pyqtSlot()
    def start(self) -> None:
        if not self._running:
            self._toggle()

    @pyqtSlot()
    def stop(self) -> None:
        if self._running:
            self._toggle()

    # ── private ───────────────────────────────────────────────────────────────

    def _toggle(self):
        self._running = not self._running
        if self._running:
            self._status_dot.setText("● Active")
            self._status_dot.setStyleSheet(f"color: {PALETTE['success']}; font-size: 11px; font-weight: bold;")
            self._btn_toggle.setText("■  Stop Camera")
            self._btn_toggle.setStyleSheet(self._btn_toggle.styleSheet().replace(
                PALETTE["success"], PALETTE["danger"]).replace("#00a383", "#b52a2a"))
            self.worker.start_capture()
            self.camera_started.emit()
        else:
            self._status_dot.setText("● Inactive")
            self._status_dot.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px;")
            self._fps_lbl.setText("FPS: —")
            self._btn_toggle.setText("▶  Start Camera")
            # restore green
            self._btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['success']}; color: #000;
                    border: none; border-radius: 8px; padding: 8px 20px;
                    font-weight: bold; font-size: 11px;
                }}
                QPushButton:hover {{ background: #00a383; }}
            """)
            self.worker.stop_capture()
            self._show_placeholder()
            self.camera_stopped.emit()

    @pyqtSlot(np.ndarray)
    def _render_frame(self, bgr: np.ndarray) -> None:
        if not self._running:
            return
        try:
            rgb = bgr[:, :, ::-1].copy()
            h, w, ch = rgb.shape
            q_img  = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img).scaled(
                self._video.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._video.setPixmap(pixmap)
        except Exception:
            pass

    def _show_placeholder(self) -> None:
        self._video.setText(
            f'<span style="color:{PALETTE["muted"]}; font-size:13px;">'
            "📷  No camera feed<br>"
            f'<span style="font-size:10px;">Press "Start Camera" to begin</span>'
            "</span>"
        )
        self._video.setTextFormat(Qt.TextFormat.RichText)

    def _update_fps(self) -> None:
        if self._running:
            self._fps_lbl.setText(f"FPS: {self._frames}")
        self._frames = 0


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    from pathlib import Path

    # Add project root to path for direct execution
    sys.path.insert(0, str(Path(__file__).parent.parent))

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    ctrl = TrainingControlWindow()
    analysis = AnalysisWindow()
    cam = CameraWindow()

    ctrl.training_started.connect(cam.start)
    ctrl.training_stopped.connect(cam.stop)
    ctrl.set_started.connect(analysis.on_set_started)

    ctrl.show()
    analysis.show()
    cam.show()

    sys.exit(app.exec())