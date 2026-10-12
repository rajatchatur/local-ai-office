from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Task:

    description: str
    assigned_to: str

    id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    status: str = "pending"

    result: Optional[str] = None

    created_at: datetime = field(
        default_factory=datetime.now
    )

    started_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None

    def start(self):
        self.status = "working"
        self.started_at = datetime.now()

    def complete(self, result: str):
        self.status = "completed"
        self.result = result
        self.completed_at = datetime.now()

    def fail(self, error: str):
        self.status = "failed"
        self.result = error
        self.completed_at = datetime.now()

    def get_info(self):

        return {
            "id": self.id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "result": self.result,
        }