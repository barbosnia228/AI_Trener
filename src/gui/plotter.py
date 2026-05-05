"""
plotter.py — Matplotlib charts embedded in PyQt6 for workout history & statistics.
"""

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

_BG     = "#0d0d0d"
_PANEL  = "#1a1a2e"
_ACCENT = "#e94560"
_GREEN  = "#00b894"
_MUTED  = "#a0a0b0"
_TEXT   = "#ffffff"
_BORDER = "#2d2d4e"


def _style_axes(fig, ax) -> None:
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_PANEL)
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.xaxis.label.set_color(_MUTED)
    ax.yaxis.label.set_color(_MUTED)
    ax.title.set_color(_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(_BORDER)


class EmbeddedChart(QWidget):
    """Base widget wrapping a single matplotlib axes."""

    def __init__(self, figsize=(6, 3), parent=None):
        super().__init__(parent)
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas)

    def _draw(self):
        self.fig.tight_layout(pad=2.0)
        self.canvas.draw_idle()

    def _no_data(self):
        self.ax.cla()
        _style_axes(self.fig, self.ax)
        self.ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                     color=_MUTED, transform=self.ax.transAxes, fontsize=11)
        self._draw()


class RepsHistoryChart(EmbeddedChart):
    """Bar chart — total reps per session.

    sessions: list of {"date": str, "total_reps": int}
    """

    def plot(self, sessions: list[dict]) -> None:
        self.ax.cla()
        _style_axes(self.fig, self.ax)
        if not sessions:
            return self._no_data()

        dates = [s["date"] for s in sessions]
        reps  = [s["total_reps"] for s in sessions]
        x = range(len(dates))

        bars = self.ax.bar(x, reps, color=_ACCENT, width=0.6)
        self.ax.set_xticks(list(x))
        self.ax.set_xticklabels(dates, rotation=35, ha="right", fontsize=7, color=_MUTED)
        self.ax.set_ylabel("Reps", color=_MUTED, fontsize=9)
        self.ax.set_title("Reps Per Session", color=_TEXT, fontsize=11)
        self.ax.yaxis.grid(True, color=_BORDER, linestyle="--", linewidth=0.5)
        self.ax.set_axisbelow(True)
        for bar, val in zip(bars, reps):
            self.ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                         str(val), ha="center", va="bottom", color=_TEXT, fontsize=7)
        self._draw()


class FormScoreChart(EmbeddedChart):
    """Line chart — average form score per session.

    sessions: list of {"date": str, "avg_form_score": float}
    """

    def plot(self, sessions: list[dict]) -> None:
        self.ax.cla()
        _style_axes(self.fig, self.ax)
        if not sessions:
            return self._no_data()

        dates  = [s["date"] for s in sessions]
        scores = [s["avg_form_score"] for s in sessions]
        x      = list(range(len(dates)))

        self.ax.plot(x, scores, color=_GREEN, linewidth=2, marker="o", markersize=5)
        self.ax.fill_between(x, scores, alpha=0.12, color=_GREEN)
        self.ax.axhline(75, color=_GREEN,    linewidth=0.8, linestyle="--", alpha=0.5)
        self.ax.axhline(45, color="#fdcb6e", linewidth=0.8, linestyle="--", alpha=0.5)
        self.ax.set_xticks(x)
        self.ax.set_xticklabels(dates, rotation=35, ha="right", fontsize=7, color=_MUTED)
        self.ax.set_ylim(0, 105)
        self.ax.set_ylabel("Form %", color=_MUTED, fontsize=9)
        self.ax.set_title("Form Score Trend", color=_TEXT, fontsize=11)
        self.ax.yaxis.grid(True, color=_BORDER, linestyle="--", linewidth=0.5)
        self.ax.set_axisbelow(True)
        self._draw()