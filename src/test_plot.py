from database.repository import WorkoutRepository
from visualizer import WorkoutVisualizer

def test_visualization():
    repo = WorkoutRepository()
    

    history = repo.get_history()
    if not history:
        print("Database empty!")
        return
    
    last_session = history[0]

    # 1. Print Info
    WorkoutVisualizer.show_session_summary(last_session)

    # 2. Plot
    WorkoutVisualizer.plot_reps(last_session)

if __name__ == "__main__":
    test_visualization()
