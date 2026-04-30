# AI Trainer — Incline Barbell Bench Press 🏋️‍♂️

An intelligent workout assistant that uses Computer Vision to analyze **Incline Barbell Bench Press** technique in real-time. The application counts repetitions, detects technical errors, and provides immediate voice feedback to ensure safety and efficiency.

## 🌟 Key Features
*   **AI Pose Estimation:** Powered by **MediaPipe** for high-precision tracking of joints and barbell trajectory.
*   **Real-time Technical Analysis:** Calculates joint angles and movement paths to identify common mistakes.
*   **Offline Voice Assistant:** Integrated via `pyttsx3` to provide instant vocal cues and corrections.
*   **Progress Tracking:** Visualizes workout history through **Matplotlib** charts embedded directly into the GUI.
*   **Local Data Storage:** All sessions, including rep counts and technical scores, are stored in a local **SQLite** database.

## 🛠 Tech Stack
*   **Language:** Python 3.10+
*   **GUI Framework:** **PyQt6** (Multithreaded architecture for smooth video and UI performance)
*   **Computer Vision:** OpenCV, MediaPipe Pose
*   **Database:** SQLite
*   **Audio:** pyttsx3 (Text-to-Speech)
*   **Analytics:** Matplotlib

## 📂 Project Structure
*   `src/` — Contains the core engine, AI logic, and PyQt6 window definitions.
*   `data.db` — SQLite database storing training logs and user history.
*   `config.json` — Customizable threshold values for movement detection.
*   `main.py` — The entry point of the application.

## 🚀 Installation & Setup
*later*

## 📊 How It Works
1.  **Main Menu:** Choose between **"Exercises"** to start a workout or **"Statistics"** to view past performance.
2.  **Exercise Setup:** Select "Incline Barbell Bench Press". Position your camera to capture your profile clearly.
3.  **Active Session:** Click **"Start Set"**. The AI begins analyzing your skeleton in real-time.
4.  **Feedback:** If a technical error is detected, the Voice Assistant will immediately suggest a correction.
5.  **Summary:** After finishing the set, the system generates a report including the number of reps and identified errors.

## 👥 Authors
*   **qvxrdxse** — Project Integration, Database Architecture & Core System Logic.
*   **ipit1y** — AI & Computer Vision (Pose Estimation & Tracking).
*   **artemooooooooon** — AI & Computer Vision (Movement Analysis & Logic).

---
*Developed as a laboratory project focusing on Intelligent Systems and Computer Vision.*
