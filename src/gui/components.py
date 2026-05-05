"""
components.py — Basic reusable PyQt6 widgets for AI Trainer.
"""

from PyQt6.QtWidgets import QPushButton, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import Optional

# ── Colour palette ─────────────────────────────────────────────────────────────
PALETTE = {
    "bg":      "#0d0d0d",
    "panel":   "#1a1a2e",
    "card":    "#16213e",
    "accent":  "#e94560",
    "success": "#00b894",
    "danger":  "#d63031",
    "text":    "#ffffff",
    "muted":   "#a0a0b0",
    "border":  "#2d2d4e",
}


def set_font(widget: QWidget, size: int = 11, bold: bool = False) -> None:
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    widget.setFont(f)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        set_font(self, 11, bold=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['accent']}; color: #fff;
                border: none; border-radius: 8px; padding: 8px 20px;
            }}
            QPushButton:hover  {{ background: #c73652; }}
            QPushButton:disabled {{ background: #3d1a25; color: #666; }}
        """)


class SuccessButton(QPushButton):
    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        set_font(self, 11, bold=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['success']}; color: #000;
                border: none; border-radius: 8px; padding: 8px 20px;
            }}
            QPushButton:hover  {{ background: #00a383; }}
            QPushButton:disabled {{ background: #1a3d30; color: #444; }}
        """)


class DangerButton(QPushButton):
    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        set_font(self, 11, bold=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['danger']}; color: #fff;
                border: none; border-radius: 8px; padding: 8px 20px;
            }}
            QPushButton:hover  {{ background: #b52a2a; }}
            QPushButton:disabled {{ background: #3a1010; color: #555; }}
        """)


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        set_font(self, 11)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {PALETTE['text']};
                border: 1px solid {PALETTE['border']}; border-radius: 8px; padding: 7px 18px;
            }}
            QPushButton:hover {{ border-color: {PALETTE['accent']}; color: {PALETTE['accent']}; }}
            QPushButton:disabled {{ color: #555; border-color: #333; }}
        """)