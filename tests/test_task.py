from backend.core.task_manager import TaskManager

def test_task_lifecycle():
    manager = TaskManager()
    
    task = manager.create_task(
        description="Research Indian motor vehicle laws",
        assigned_to="researcher",
    )
    
    assert task is not None
    manager.start_task(task.id)
    
    manager.complete_task(
        task.id, 
        "Research completed successfully.",
    )
    
    assert task.get_info() is not None
