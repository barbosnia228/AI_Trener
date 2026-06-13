# AI Trainer — Incline Barbell Bench Press 🏋️‍♂️

An intelligent workout assistant that uses Computer Vision to analyze **Incline Barbell Bench Press** technique in real-time. The application counts repetitions, detects technical errors, provides voice coaching, and tracks your progress over time.

## 🌟 Key Features

- **AI Pose Estimation:** Powered by **MediaPipe PoseLandmarker** (lite model, auto-downloaded on first run) for precise tracking of joints across both arms.
- **Real-time Rep Counting:** A state-machine tracks the full range of motion — angle smoothing over 6 frames, minimum depth validation, cooldown guard — to count only clean reps.
- **Technique Analysis:** Detects four classes of errors with hysteresis to avoid false positives:
  - Uneven bar lowering (elbow Y asymmetry)
  - Wrist bend (wrist X offset from elbow)
  - Foot lift (ankle rising above baseline)
  - Shoulder asymmetry (L/R elbow angle difference > 20°)
- **Voice Coaching:** Priority-based TTS — **Windows SAPI** (`win32com`) as primary engine, **pyttsx3** as cross-platform fallback. Messages are deduplicated and queued in a daemon thread so they never block the video loop. Prefers English voice on SAPI; falls back to Polish if found.
- **Weight Recommendation:** Analyzes session history after each workout and recommends whether to increase, maintain, or decrease working weight.
- **Session Rating:** Scores each completed workout 0–10 based on sets completed, rep deficit, and form errors detected.
- **Progress Charts:** Volume (kg·reps) and max weight trend charts rendered via **Matplotlib** in the Statistics tab.
- **Local Data Storage:** All sessions — sets, weights, rep counts, errors, and rating — are automatically saved to a local **SQLite** database after each workout.
- **Video File Support:** Analyze a pre-recorded workout video instead of (or alongside) a live camera feed.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | PyQt6 — three windows, `CameraWorker` runs in a separate `QThread` |
| Computer Vision | OpenCV, MediaPipe Pose (PoseLandmarker lite) |
| Angle Calculation | NumPy (`arctan2`-based geometry in `GeometryEngine`) |
| Database | SQLite (via stdlib `sqlite3`) |
| Audio — primary | win32com · Windows SAPI (`pywin32 >= 300`) |
| Audio — fallback | pyttsx3 >= 2.90 (cross-platform TTS) |
| Analytics | Matplotlib >= 3.5 (`FigureCanvasQTAgg` embedded in PyQt6) |

## 📂 Project Structure

```
AI_Trener/
├── main.py                      # Entry point — wires all Qt signals between windows and AIEngine
├── config.json                  # Detection thresholds (elbow angles, rep threshold)
├── pose_landmarker.task         # MediaPipe model (auto-downloaded on first run)
├── requirements.txt
├── data/
│   └── trainer_data.db          # SQLite database with training history
└── src/
    ├── ai/
    │   ├── engine.py            # Core AI: pose detection, rep state-machine, technique checks, HUD rendering
    │   ├── geometry.py          # GeometryEngine — angle calculation via NumPy arctan2
    │   └── feedback.py          # FeedbackEngine — async TTS queue (SAPI → pyttsx3 fallback)
    ├── database/
    │   ├── connection.py        # SQLite connection, schema init
    │   ├── models.py            # WorkoutSession / WorkoutSet dataclasses
    │   ├── repository.py        # CRUD, analytics queries, weight recommendation logic
    │   └── rating.py            # Session rating algorithm (0–10 score)
    └── gui/
        ├── window.py            # TrainingControlWindow, AnalysisWindow, CameraWindow + CameraWorker
        └── components.py        # Shared colour palette (PALETTE) and button widgets
```

## ⚙️ config.json

Tune detection sensitivity without touching code:

```json
{
  "elbow_min_angle": 45,
  "elbow_max_angle": 75,
  "repetition_threshold": 160
}
```

| Key | Description |
|---|---|
| `elbow_min_angle` / `elbow_max_angle` | Angle range (degrees) that counts as the bottom position of a rep |
| `repetition_threshold` | Angle (degrees) that must be reached on the way up to confirm rep completion |

## 🚀 Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/barbosnia228/AI_Trener.git
cd AI_Trener

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python main.py
```

> **Windows:** Voice feedback uses Windows SAPI by default — no extra setup needed.  
> **Other OS:** `pywin32` will fail to import; the app automatically falls back to `pyttsx3`.  
> **MediaPipe model:** `pose_landmarker.task` is downloaded automatically on the first run (~5.5 MB).

## 📊 How It Works

The application opens three windows simultaneously and connects them via Qt signals:

| Window | Purpose |
|---|---|
| **Training Control** | Configure sets/reps, start/stop training, view weight recommendation and Statistics tab |
| **Live Analysis** | Real-time metrics — elbow angle, rep count, form score (0–100 %), session totals, feedback log |
| **Camera Feed** | Live camera or loaded video with skeleton overlay and HUD (REPS, ANG, MIN, status) |

**Signal flow:**

```
CameraWorker.frame_signal → AIEngine.process_frame
AIEngine.processed_frame  → CameraWindow.update_frame
AIEngine.metrics_updated  → AnalysisWindow.update
AIEngine.feedback_message → AnalysisWindow.add_feedback
AIEngine.set_summary      → TrainingControlWindow.on_set_summary → DB save + rating
```

**Typical workout:**

1. **Configure** — set the number of sets and reps. A weight recommendation from your last sessions is shown automatically.
2. **Choose source** — **"▶ Start Camera"** for live feed, or **"📁 Load Video"** to analyze a recording.
3. **Start training** — **"▶ Start Training"**. The camera activates automatically.
4. **Per set** — click **"Start"** when ready, perform the exercise, click **"Finish"** when done. **"Skip"** to skip a set.
5. **Live feedback** — the AI announces detected errors via voice; the feedback log updates in real time.
6. **Session saved** — when training stops (manually or after all sets complete), the session is rated and written to SQLite automatically.
7. **Review** — switch to the **Statistics** tab for volume/weight charts, full session history with ratings, and the next weight recommendation.

## 👥 Authors

- **qvxrdxse** — Project Integration, Database Architecture & Core System Logic
- **ipit1y** — AI & Computer Vision (Pose Estimation & Tracking)
- **artemooooooooon** — GUI (PyQt6) & UX Design

---
*Developed as a laboratory project focusing on Intelligent Systems and Computer Vision.*
