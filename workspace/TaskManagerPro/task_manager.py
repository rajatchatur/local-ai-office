from dataclasses import dataclass

from typing import Optional
from json import load, dump

@dataclass
class Task:
    id: int
    title: str
    completed: bool

class TaskManager:
    def __init__(self):
        self.tasks = []
        self.load_tasks()

    def load_tasks(self):
        try:
            with open('tasks.json', 'r') as f:
                self.tasks = list(load(f, object_hook=self._parse_task))
        except Exception:
            pass

    def _parse_task(self, d):
        return Task(id=d['id'], title=d['title'], completed=d['completed'])

    def save_tasks(self):
        with open('tasks.json', 'w') as f:
            dump(self.tasks, f, default=str)

    def add_task(self, title: str):
        if not title:
            raise ValueError('Task title cannot be empty')
        self.tasks.append(Task(id=len(self.tasks), title=title, completed=False))
        self.save_tasks()

    def list_tasks(self):
        for task in self.tasks:
            print(f'{task.id}: {task.title} - {"Completed" if task.completed else "Not Completed"}')

    def mark_complete(self, task_id: int):
        for task in self.tasks:
            if task.id == task_id:
                task.completed = True
                self.save_tasks()
                return
        raise ValueError(f'No task found with ID {task_id}')

    def delete_task(self, task_id: int):
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self.save_tasks()
                return
        raise ValueError(f'No task found with ID {task_id}')

    def _parse_task(self, d):
        return Task(id=d['id'], title=d['title'], completed=d['completed'])