from typing import Dict

from backend.core.task import Task


class TaskManager:

    def __init__(self):

        self.tasks: Dict[str, Task] = {}

    def create_task(
        self,
        description: str,
        assigned_to: str,
    ) -> Task:

        task = Task(
            description=description,
            assigned_to=assigned_to,
        )

        self.tasks[task.id] = task

        return task

    def get_task(self, task_id: str):

        return self.tasks.get(task_id)

    def get_all_tasks(self):

        return list(self.tasks.values())

    def start_task(self, task_id: str):

        task = self.get_task(task_id)

        if task is None:
            raise ValueError(
                f"Task {task_id} not found"
            )

        task.start()

    def complete_task(
        self,
        task_id: str,
        result: str,
    ):

        task = self.get_task(task_id)

        if task is None:
            raise ValueError(
                f"Task {task_id} not found"
            )

        task.complete(result)