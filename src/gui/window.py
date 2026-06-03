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

import json
import os
import sys
import time
from typing import Optional

import cv2
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy,
    QSpinBox, QDoubleSpinBox, QFileDialog, QTabWidget,
)

from src.database.repository import WorkoutRepository

from src.gui.components import (
    PrimaryButton, SuccessButton, DangerButton, SecondaryButton,
    PALETTE, set_font,
)

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


def _metric_card(layout: QHBoxLayout, label: str, value: str) -> QLabel:
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


_DEFAULT_WEIGHT_KG = 60.0

_BTN_STOP_STYLE = f"""
    QPushButton {{
        background: {PALETTE['danger']}; color: #fff;
        border: none; border-radius: 8px; padding: 8px 20px;
        font-weight: bold; font-size: 11px;
    }}
    QPushButton:hover {{ background: #b52a2a; }}
"""

_BTN_START_STYLE = f"""
    QPushButton {{
        background: {PALETTE['success']}; color: #000;
        border: none; border-radius: 8px; padding: 8px 20px;
        font-weight: bold; font-size: 11px;
    }}
    QPushButton:hover {{ background: #00a383; }}
"""


def _apply_geometry(
    win: QMainWindow, lf: float, tf: float, wf: float, hf: float,
    tf_small: Optional[float] = None, hf_small: Optional[float] = None,
) -> None:
    screen = QApplication.primaryScreen().geometry()
    sw, sh = screen.width(), screen.height()
    x = max(0, min(int(sw * lf), sw - 100))
    y = max(0, min(int(sh * tf), sh - 100))
    w = min(int(sw * wf), sw - x - 20)
    h = min(int(sh * hf), sh - y - 20)
    if sw < 1200 and (tf_small is not None or hf_small is not None):
        y_s = int(sh * tf_small) if tf_small is not None else y
        h_s = int(sh * hf_small) if hf_small is not None else h
        win.setGeometry(x, y_s, w, h_s)
    else:
        win.setGeometry(x, y, w, h)


# ══════════════════════════════════════════════════════════════════════════════
# Window 1 — Training Control
# ══════════════════════════════════════════════════════════════════════════════

class _SetRow(QFrame):
    """One row per set: label + Start / Finish / Skip buttons."""

    def __init__(self, index: int, reps: int, weight: float, on_start, on_finish, on_skip, parent=None):
        super().__init__(parent)
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



    @property
    def is_done(self) -> bool:
        return self._status.text() in ("Done ✓", "Skipped")

    @property
    def is_completed(self) -> bool:
        return self._status.text() == "Done ✓"

    def mark_active(self):
        self._status.setText("Active")
        self._status.setStyleSheet(f"color: {PALETTE['warning']};")
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
    """
    Signals
    -------
    training_started()
    training_stopped()
    set_started(index: int)
    set_finished(index: int)
    set_skipped(index: int)
    """

    training_started  = pyqtSignal()
    training_stopped  = pyqtSignal()
    set_started       = pyqtSignal(int)
    set_finished      = pyqtSignal(int)
    set_skipped       = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🏋️  AI Trainer — Control")
        _apply_geometry(self, 0.05, 0.05, 0.40, 0.50, hf_small=0.30)
        self.setMinimumHeight(620)

        self._rows: list[_SetRow] = []
        self._active: Optional[int]  = None
        self._elapsed = 0

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {PALETTE['bg']}; }}
            QTabBar::tab {{
                background: {PALETTE['panel']}; color: {PALETTE['muted']};
                padding: 8px 24px; border: none;
                border-bottom: 2px solid transparent;
                font-size: 11px; font-weight: bold;
            }}
            QTabBar::tab:selected {{
                color: {PALETTE['text']};
                border-bottom: 2px solid {PALETTE['accent']};
                background: {PALETTE['bg']};
            }}
            QTabBar::tab:hover {{ color: {PALETTE['text']}; }}
        """)
        outer.addWidget(self._tabs)

        training_tab = QWidget()
        root = QVBoxLayout(training_tab)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        self._tabs.addTab(training_tab, "🏋️  Training")
        self._stats_tab_index: int = -1  # set when stats tab is added

        # ── header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("AI TRAINER")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {PALETTE['accent']};")
        hdr.addWidget(title)
        hdr.addStretch()
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

        # ── Tab 2: Statistics ────────────────────────────────────────────────
        self._repo = WorkoutRepository()

        stats_tab = QWidget()
        sr = QVBoxLayout(stats_tab)
        sr.setContentsMargins(20, 16, 20, 16)
        sr.setSpacing(10)
        self._stats_tab_index = self._tabs.addTab(stats_tab, "📊  Statistics")

        sr.addWidget(_label("Overall", size=10, muted=True))
        sc_row = QHBoxLayout()
        sc_row.setSpacing(8)
        self._sv_workouts = _metric_card(sc_row, "Workouts",    "—")
        self._sv_reps     = _metric_card(sc_row, "Total Reps",  "—")
        self._sv_max      = _metric_card(sc_row, "Best Weight", "—")
        sr.addLayout(sc_row)

        sr.addWidget(_separator())
        sr.addWidget(_label("Progress", size=10, muted=True))
        self._stat_figure = Figure(figsize=(6, 2.6), facecolor=PALETTE["panel"])
        self._stat_canvas = FigureCanvasQTAgg(self._stat_figure)
        self._stat_canvas.setMinimumHeight(170)
        sr.addWidget(self._stat_canvas)

        sr.addWidget(_separator())
        sr.addWidget(_label("History", size=10, muted=True))
        hist_scroll = QScrollArea()
        hist_scroll.setWidgetResizable(True)
        hist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hist_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {PALETTE['border']}; border-radius: 8px; }}"
        )
        self._hist_widget = QWidget()
        self._hist_widget.setStyleSheet(f"background: {PALETTE['panel']};")
        self._hist_layout = QVBoxLayout(self._hist_widget)
        self._hist_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._hist_layout.setContentsMargins(8, 8, 8, 8)
        self._hist_layout.setSpacing(6)
        hist_scroll.setWidget(self._hist_widget)
        sr.addWidget(hist_scroll, 1)

        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ── private ────────────────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        if index == self._stats_tab_index:
            self._refresh_stats()

    def _refresh_stats(self) -> None:
        try:
            data = json.loads(self._repo.get_full_analytics_json())
        except Exception:
            return
        overall = data.get("overall", {})
        self._sv_workouts.setText(str(overall.get("total_workouts", 0)))
        self._sv_reps.setText(str(overall.get("total_reps", 0)))
        self._sv_max.setText(f"{overall.get('all_time_max', 0):.1f} kg")
        self._update_stat_charts(data.get("charts", {}))
        self._update_stat_history(data.get("history", []))

    def _update_stat_charts(self, charts: dict) -> None:
        labels      = charts.get("labels", [])
        volumes     = charts.get("volumes", [])
        max_weights = charts.get("max_weights", [])
        self._stat_figure.clear()
        self._stat_figure.patch.set_facecolor(PALETTE["panel"])
        if not labels:
            self._stat_canvas.draw()
            return
        ax1 = self._stat_figure.add_subplot(1, 2, 1)
        ax2 = self._stat_figure.add_subplot(1, 2, 2)
        for ax in (ax1, ax2):
            ax.set_facecolor(PALETTE["card"])
            for spine in ax.spines.values():
                spine.set_edgecolor(PALETTE["border"])
            ax.tick_params(colors=PALETTE["muted"], labelsize=7)
        xs = list(range(len(labels)))
        ax1.bar(xs, volumes, color=PALETTE["accent"], alpha=0.85)
        ax1.set_title("Volume (kg·reps)", color=PALETTE["text"], fontsize=8, pad=4)
        ax1.set_xticks(xs)
        ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=6, color=PALETTE["muted"])
        ax1.grid(axis="y", color=PALETTE["border"], linestyle="--", alpha=0.5)
        ax2.plot(xs, max_weights, color=PALETTE["success"], marker="o", linewidth=2, markersize=4)
        ax2.fill_between(xs, max_weights, alpha=0.15, color=PALETTE["success"])
        ax2.set_title("Max Weight (kg)", color=PALETTE["text"], fontsize=8, pad=4)
        ax2.set_xticks(xs)
        ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=6, color=PALETTE["muted"])
        ax2.grid(axis="y", color=PALETTE["border"], linestyle="--", alpha=0.5)
        self._stat_figure.tight_layout(pad=0.8)
        self._stat_canvas.draw()

    def _update_stat_history(self, history: list) -> None:
        while self._hist_layout.count():
            item = self._hist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not history:
            lbl = _label("No workouts recorded yet.", size=9, muted=True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hist_layout.addWidget(lbl)
            return
        for w in history:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {PALETTE['card']};
                    border: 1px solid {PALETTE['border']};
                    border-radius: 8px;
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(3)
            top = QHBoxLayout()
            top.addWidget(_label(w.get("date", "—"), size=10, bold=True))
            top.addStretch()
            top.addWidget(_label(f"⭐ {w.get('rating', 0)}/10", size=9))
            cl.addLayout(top)
            s = w.get("summary", {})
            cl.addWidget(_label(
                f"Vol: {s.get('volume', 0):.0f} kg·reps  ·  "
                f"Max: {s.get('max_weight', 0):.1f} kg  ·  "
                f"Reps: {s.get('reps_count', 0)}",
                size=8, muted=True,
            ))
            sets = w.get("sets", [])
            if sets:
                sets_str = "  ".join(
                    f"S{i+1}: {st['weight']:.0f}kg×{st['reps']}"
                    for i, st in enumerate(sets)
                )
                cl.addWidget(_label(sets_str, size=8, muted=True))
            errors = [e for e in w.get("errors", []) if e and e.lower() != "none"]
            if errors:
                err = _label(f"Errors: {', '.join(errors)}", size=8)
                err.setStyleSheet(f"color: {PALETTE['danger']}; background: transparent;")
                err.setWordWrap(True)
                cl.addWidget(err)
            self._hist_layout.addWidget(card)

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
            row = _SetRow(i, reps, _DEFAULT_WEIGHT_KG, self._on_start, self._on_finish, self._on_skip)
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
        if self._rows and all(row.is_done for row in self._rows):
            self._status_lbl.setText("🎉 All sets complete!")
            self._stop()

    def _update_sets_label(self):
        done  = sum(1 for r in self._rows if r.is_completed)
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
        _apply_geometry(self, 0.48, 0.05, 0.25, 0.45, tf_small=0.35, hf_small=0.25)
        self.setMinimumHeight(540)

        self._session_reps   = 0
        self._session_sets   = 0
        self._session_errors = 0
        self._current_set_reps = 0

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
        self._v_reps  = _metric_card(set_grid, "Reps",       "0")
        self._v_angle = _metric_card(set_grid, "Angle",      "—°")
        self._v_form  = _metric_card(set_grid, "Form",       "—%")
        self._v_time  = _metric_card(set_grid, "Set Time",   "00:00")
        root.addLayout(set_grid)

        root.addWidget(_separator())

        # ── session totals ───────────────────────────────────────────────────
        root.addWidget(_label("Session Totals", size=10, muted=True))
        sess_grid = QHBoxLayout()
        sess_grid.setSpacing(8)
        self._s_reps   = _metric_card(sess_grid, "Total Reps", "0")
        self._s_sets   = _metric_card(sess_grid, "Sets Done",  "0")
        self._s_errors = _metric_card(sess_grid, "Errors",     "0")
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

    # ── public API ────────────────────────────────────────────────────────────

    def update(self, angle: float, reps: int, form_score: int, elapsed: int) -> None:
        """Call this every frame from your backend worker thread (via queued signal)."""
        self._current_set_reps = reps
        self._v_reps.setText(str(reps))
        self._v_angle.setText(f"{angle:.1f}°")
        self._v_form.setText(f"{form_score}%")
        m, s = divmod(elapsed, 60)
        self._v_time.setText(f"{m:02d}:{s:02d}")

        colour = (PALETTE["success"] if form_score >= 75
                  else PALETTE["warning"] if form_score >= 45 else PALETTE["danger"])
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
        self._current_set_reps = 0
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
        self._session_reps += self._current_set_reps
        self._session_sets += 1
        self._s_reps.setText(str(self._session_reps))
        self._s_sets.setText(str(self._session_sets))


# ══════════════════════════════════════════════════════════════════════════════
# Window 3 — Camera Feed
# ══════════════════════════════════════════════════════════════════════════════

class CameraWorker(QThread):
    frame_signal   = pyqtSignal(np.ndarray)
    video_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running    = False
        self.cap        = None
        self.video_path: Optional[str] = None

    def start_capture(self, video_path: Optional[str] = None):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path if video_path else 0)
        if not self.cap.isOpened():
            print(f"Error: Could not open {'video file' if video_path else 'camera'}.")
            return
        self.running = True
        self.start()

    def stop_capture(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    def run(self):
        is_video = self.video_path is not None
        delay = (1.0 / (self.cap.get(cv2.CAP_PROP_FPS) or 30.0)) if is_video else 0.0
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame_signal.emit(frame)
                if is_video:
                    time.sleep(delay)
                else:
                    cv2.waitKey(1)
            else:
                if is_video:
                    self.video_finished.emit()
                break

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
        _apply_geometry(self, 0.05, 0.52, 0.35, 0.55, tf_small=0.62, hf_small=0.35)

        self._running    = False
        self._frames     = 0
        self._video_path: Optional[str] = None

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

        self._source_lbl = QLabel("Source: Camera")
        self._source_lbl.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 10px;")
        bar.addWidget(self._source_lbl)

        bar.addStretch()

        self._btn_load = SecondaryButton("📁 Load Video")
        self._btn_load.setFixedWidth(130)
        self._btn_load.clicked.connect(self._load_video)
        bar.addWidget(self._btn_load)

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
        self.worker.video_finished.connect(self._on_video_finished)

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
            self._btn_toggle.setStyleSheet(_BTN_STOP_STYLE)
            self._btn_load.setEnabled(False)
            self.worker.start_capture()
            self.camera_started.emit()
        else:
            self._video_path = None
            self._do_stop_ui()
            self.worker.stop_capture()
            self.camera_stopped.emit()

    def _load_video(self) -> None:
        if self._running:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv);;All Files (*)"
        )
        if not path:
            return
        self._video_path = path
        self._running = True
        name = os.path.basename(path)
        display = (name[:22] + "...") if len(name) > 25 else name
        self._status_dot.setText("● Playing")
        self._status_dot.setStyleSheet(f"color: {PALETTE['accent']}; font-size: 11px; font-weight: bold;")
        self._source_lbl.setText(f"📹 {display}")
        self._source_lbl.setStyleSheet(f"color: {PALETTE['accent']}; font-size: 10px;")
        self._btn_toggle.setText("■  Stop Video")
        self._btn_toggle.setStyleSheet(_BTN_STOP_STYLE)
        self._btn_load.setEnabled(False)
        self.worker.start_capture(path)
        self.camera_started.emit()

    @pyqtSlot()
    def _on_video_finished(self) -> None:
        if not self._running:
            return
        self._running = False
        self._video_path = None
        self._do_stop_ui()
        self.worker.stop_capture()
        self.camera_stopped.emit()

    def _do_stop_ui(self) -> None:
        self._status_dot.setText("● Inactive")
        self._status_dot.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px;")
        self._fps_lbl.setText("FPS: —")
        self._source_lbl.setText("Source: Camera")
        self._source_lbl.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 10px;")
        self._btn_toggle.setText("▶  Start Camera")
        self._btn_toggle.setStyleSheet(_BTN_START_STYLE)
        self._btn_load.setEnabled(True)
        self._show_placeholder()

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
        except Exception as exc:
            print(f"[CameraWindow] render error: {exc}", file=sys.stderr)

    def _show_placeholder(self) -> None:
        self._video.setText(
            f'<span style="color:{PALETTE["muted"]}; font-size:13px;">'
            "📷  No feed<br>"
            f'<span style="font-size:10px;">Press "Start Camera" for live feed or "Load Video" to analyse a file</span>'
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