from datetime import datetime, timedelta


def record_meditation(session_id, start_time, end_time, duration, preferences="default"):
    session = {
        "id": session_id,
        "start": start_time,
        "end": end_time,
        "duration": duration,
        "preferences": preferences
    }
    return session


if __name__ == "__main__":
    # Example usage
    session_id = 1
    start = datetime(2023, 1, 1, 8, 0, 0)
    end = datetime(2023, 1, 1, 8, 30, 0)
    duration = (end - start).total_seconds()
    preferences = "preferred_style"
    session = record_meditation(session_id, start, end, duration, preferences)
    print(f"Session {session_id} recorded from {start} to {end} ({duration} seconds)")

    # Example of retrieving session
    session = record_meditation(1)
    print(f"Session {session['id']} lasted {session['duration']} seconds")