import matplotlib.pyplot as plt
import io

class WorkoutVisualizer:
    @staticmethod
    def show_session_summary(session):
        """Выводит в консоль или возвращает строку с красивым описанием"""
        header = f" {session.date} "
        print(f"\n{'='*10}{header}{'='*10}")
        print(f"🏋️ Weight: {session.weight} kg")
        print(f"⭐ Rating: {session.rating}/5")
        print(f"💬 Feedback: {session.weight_feedback}")
        
        print("\n📊 Sets Performance:")
        for i, reps in enumerate(session.sets, 1):
            print(f"   Set {i}: {reps} reps")

        if session.errors:
            print("\n❌ Technical Errors:")
            for err in set(session.errors):
                count = session.errors.count(err)
                print(f"   - {err} ({count} times)")
        else:
            print("\n✅ Perfect Technique!")
        print(f"{'='*(20 + len(header))}\n")

    @staticmethod
    def plot_reps(session):
        """Prints plot"""
        if not session.sets:
            print("No sets to plot!")
            return

        set_numbers = list(range(1, len(session.sets) + 1))
        reps = session.sets

        plt.figure(figsize=(8, 5))
        bars = plt.bar(set_numbers, reps, color='skyblue', edgecolor='navy', alpha=0.8)
        
        plt.xlabel('Set Number', fontsize=12)
        plt.ylabel('Reps Count', fontsize=12)
        plt.title(f'Workout Progress - {session.date}', fontsize=14)
        plt.xticks(set_numbers) 
        
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.1, yval, ha='center', va='bottom', fontweight='bold')

        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()
