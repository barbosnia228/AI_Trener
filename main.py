import sys
from PyQt6.QtWidgets import QApplication

from src.gui.window import (
    TrainingControlWindow,
    AnalysisWindow,
    CameraWindow,
    APP_STYLESHEET,
)
from src.ai.engine import AIEngine


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    ctrl     = TrainingControlWindow()
    analysis = AnalysisWindow()
    cam      = CameraWindow()
    engine   = AIEngine()

    cam.worker.frame_signal.connect(engine.process_frame)
    engine.processed_frame.connect(cam.update_frame)
    engine.metrics_updated.connect(
        lambda angle, reps, form, elapsed: analysis.update(angle, reps, form, elapsed)
    )
    engine.feedback_message.connect(analysis.add_feedback)

    ctrl.training_started.connect(cam.start)
    ctrl.training_started.connect(analysis.on_training_started)

    ctrl.training_stopped.connect(cam.stop)
    ctrl.training_stopped.connect(analysis.on_training_stopped)
    ctrl.training_stopped.connect(engine.on_training_stopped)

    ctrl.set_started.connect(analysis.on_set_started)
    ctrl.set_started.connect(engine.on_set_started)

    ctrl.set_finished.connect(analysis.on_set_finished)
    ctrl.set_finished.connect(engine.on_set_finished)

    ctrl.show()
    analysis.show()
    cam.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()