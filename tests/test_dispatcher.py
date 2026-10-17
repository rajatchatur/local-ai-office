import asyncio
import pytest

from backend.core.event_bus import EventBus
from backend.core.agent_registry import AgentRegistry
from backend.core.dispatcher import Dispatcher
from backend.core.task_manager import TaskManager

class FakeResearcher:
    name = "researcher"

    async def run(self, task):
        return "Research completed successfully."

    def get_info(self):
        return {"name": self.name}


class FailingResearcher:
    name = "researcher"

    async def run(self, task):
        raise RuntimeError("Simulated worker failure")

    def get_info(self):
        return {"name": self.name}


def create_dispatcher(worker):
    task_manager = TaskManager()
    agent_registry = AgentRegistry()
    agent_registry.register(worker)
    event_bus = EventBus()

    dispatcher = Dispatcher(
        agent_registry=agent_registry,
        task_manager=task_manager,
        event_bus=event_bus,
    )

    return dispatcher, task_manager, event_bus


def test_dispatcher_completes_task_and_publishes_events():
    async def run_test():
        dispatcher, task_manager, event_bus = (
            create_dispatcher(FakeResearcher())
        )

        task = task_manager.create_task(
            description="Test dispatcher",
            assigned_to="researcher",
        )

        result = await dispatcher.dispatch(task.id)

        assert result == "Research completed successfully."
        assert task.status == "completed"
        assert task.result == result
        assert task.started_at is not None
        assert task.completed_at is not None

        event_types = [
            event.event_type for event in event_bus.get_all_events()
        ]

        assert "task_started" in event_types
        assert "agent_working" in event_types
        assert "task_completed" in event_types
        assert "agent_completed" in event_types

    asyncio.run(run_test())


def test_dispatcher_marks_task_failed_when_worker_raises():
    async def run_test():
        dispatcher, task_manager, event_bus = (
            create_dispatcher(FailingResearcher())
        )

        task = task_manager.create_task(
            description="Test worker failure",
            assigned_to="researcher",
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated worker failure",
        ):
            await dispatcher.dispatch(task.id)

        assert task.status == "failed"
        assert task.result == "Simulated worker failure"
        assert task.completed_at is not None

        event_types = [
            event.event_type for event in event_bus.get_all_events()
        ]

        assert "task_started" in event_types
        assert "task_failed" in event_types
        assert "agent_failed" in event_types

    asyncio.run(run_test())


def test_dispatcher_rejects_missing_worker():
    async def run_test():
        task_manager = TaskManager()
        event_bus = EventBus()

        dispatcher = Dispatcher(
            agent_registry=AgentRegistry(),
            task_manager=task_manager,
            event_bus=event_bus,
        )

        task = task_manager.create_task(
            description="Test missing worker",
            assigned_to="missing-agent",
        )

        with pytest.raises(
            ValueError,
            match="Agent 'missing-agent' not found",
        ):
            await dispatcher.dispatch(task.id)

        assert task.status == "pending"
        assert event_bus.get_all_events() == []

    asyncio.run(run_test())


class FailedExecutionCoder:
    name = "coder"

    async def run(self, task):
        import json

        return json.dumps({
            "project_name": "TaskManagerPro",
            "status": "failed",
            "execution": {
                "return_code": 1,
                "stdout": "",
                "stderr": "AttributeError: 'TaskManager' object has no attribute 'start'",
            },
        })

    def get_info(self):
        return {"name": self.name}


def test_dispatcher_marks_failed_coder_execution_as_failed():
    async def run_test():
        dispatcher, task_manager, event_bus = (
            create_dispatcher(FailedExecutionCoder())
        )

        task = task_manager.create_task(
            description="Build a working task manager",
            assigned_to="coder",
        )

        with pytest.raises(RuntimeError, match="execution failed"):
            await dispatcher.dispatch(task.id)

        assert task.status == "failed"
        assert "AttributeError" in task.result

        event_types = [
            event.event_type for event in event_bus.get_all_events()
        ]

        assert "task_failed" in event_types
        assert "agent_failed" in event_types
        assert "task_completed" not in event_types
        assert "agent_completed" not in event_types

    asyncio.run(run_test())
