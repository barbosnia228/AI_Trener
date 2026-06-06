# AI Trainer — Incline Barbell Bench Press 🏋️‍♂️

An intelligent workout assistant that uses Computer Vision to analyze **Incline Barbell Bench Press** technique in real-time. The application counts repetitions, detects technical errors, and provides immediate voice feedback to ensure safety and efficiency.

## 🌟 Key Features

- **AI Pose Estimation:** Powered by **MediaPipe** for high-precision tracking of joints and barbell trajectory.
- **Real-time Technical Analysis:** Calculates joint angles and movement paths to identify common mistakes.
- **Video File Support:** Analyze a pre-recorded workout video in addition to a live camera feed.
- **Offline Voice Assistant:** Integrated via `pyttsx3` to provide instant vocal cues and corrections.
- **Progress Tracking:** Visualizes workout history through **Matplotlib** charts embedded in the Statistics tab.
- **Local Data Storage:** All sessions, including rep counts and technical errors, are automatically saved to a local **SQLite** database after each workout.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | PyQt6 (multithreaded: camera runs in a separate QThread) |
| Computer Vision | OpenCV, MediaPipe Pose |
| Database | SQLite |
| Audio | pyttsx3 (Text-to-Speech) |
| Analytics | Matplotlib |

## 📂 Project Structure

```
AI_Trener/
├── main.py                  # Entry point — creates windows and wires signals
├── config.json              # Detection thresholds (elbow angles, rep threshold)
├── pose_landmarker.task     # MediaPipe model (auto-downloaded on first run)
├── requirements.txt
├── data/
│   └── trainer_data.db      # SQLite database with training history
└── src/
    ├── ai/
    │   ├── engine.py        # Core AI: pose detection, rep counting, technique validation
    │   ├── geometry.py      # Angle calculations
    │   └── feedback.py      # Voice feedback via pyttsx3
    ├── database/
    │   ├── connection.py    # SQLite connection and schema init
    │   ├── models.py        # WorkoutSession / WorkoutSet dataclasses
    │   └── repository.py    # CRUD and analytics queries
    └── gui/
        ├── window.py        # Three main windows + CameraWorker thread
        └── components.py    # Shared colour palette and button widgets
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

- `elbow_min_angle` / `elbow_max_angle` — angle range (degrees) that counts as the bottom position of a rep.
- `repetition_threshold` — angle (degrees) that must be reached on the way up to confirm rep completion.

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

The MediaPipe pose model (`pose_landmarker.task`) is downloaded automatically on the first run.

## 📊 How It Works

The application opens three windows simultaneously:

| Window | Purpose |
|---|---|
| **Training Control** | Configure sets/reps, start/stop training, view Statistics tab |
| **Live Analysis** | Real-time metrics — angle, reps, form score, feedback log |
| **Camera Feed** | Live camera or loaded video with skeleton overlay |

**Typical workflow:**

1. **Configure** the number of sets and reps in the *Training* tab.
2. **Choose source** — click **"▶ Start Camera"** for live feed, or **"📁 Load Video"** to analyze a recording.
3. **Start training** — click **"▶ Start Training"**. The camera activates automatically.
4. **Per set** — click **"Start"** on the set row when ready, perform the exercise, click **"Finish"** when done. Use **"Skip"** to skip a set.
5. **Live feedback** — the AI detects pose errors (uneven lowering, wrist bend, foot lift, shoulder asymmetry) and announces corrections via voice.
6. **Session saved** — when training stops (manually or after all sets complete), the session is automatically written to the SQLite database.
7. **Review progress** — switch to the **Statistics** tab to see total workouts, volume/weight charts, and full session history.

## 👥 Authors

- **qvxrdxse** — Project Integration, Database Architecture & Core System Logic
- **ipit1y** — AI & Computer Vision (Pose Estimation & Tracking)
- **artemooooooooon** — GUI (PyQt6) & UX Design

---
*Developed as a laboratory project focusing on Intelligent Systems and Computer Vision.*
