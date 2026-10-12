import asyncio

import pytest

from backend.agents.boss_agent import BossAgent
from backend.core.agent_registry import AgentRegistry
from backend.core.event_bus import EventBus
from backend.core.message_bus import MessageBus
from backend.core.task_manager import TaskManager

def make_boss():
    task_manager = TaskManager()
    agent_registry = AgentRegistry()
    message_bus = MessageBus()
    event_bus = EventBus()

    boss = BossAgent(
        task_manager=task_manager,
        agent_registry=agent_registry,
        message_bus=message_bus,
        event_bus=event_bus,
    )

    return boss, task_manager, agent_registry, event_bus


def test_boss_initializes_with_core_dependencies():
    boss, task_manager, agent_registry, event_bus = make_boss()

    assert boss is not None
    assert boss.task_manager is task_manager
    assert boss.agent_registry is agent_registry


def test_boss_reports_worker_failure_instead_of_success():
    async def run_test():
        boss, task_manager, agent_registry, event_bus = make_boss()

        class FailingWorker:
            name = "researcher"

            async def run(self, task):
                raise RuntimeError("Simulated worker failure")

            def get_info(self):
                return {"name": self.name}

            def get_status(self):
                return "idle"

        agent_registry.register(FailingWorker())

        async def fake_plan(user_request):
            return [
                {
                    "description": "Perform the requested work",
                    "assigned_to": "researcher",
                }
            ]

        boss.create_plan = fake_plan

        result = await boss.run(
            "Build a complex application with multiple steps"
        )

        failed_tasks = [
            task for task in task_manager.get_all_tasks()
            if task.status == "failed"
        ]

        assert failed_tasks, "The failed worker task should be recorded"
        assert "Simulated worker failure" in failed_tasks[0].result
        assert isinstance(result, str)
        assert result.strip()
        assert "Simulated worker failure" in result or (
            "failed" in result.lower()
            or "incomplete" in result.lower()
        )

        event_types = [
            event.event_type for event in event_bus.get_all_events()
        ]
        assert "task_failed" in event_types

    asyncio.run(run_test())
def test_boss_reports_partial_failure_when_multiple_workers_run():
    async def run_test():
        boss, task_manager, agent_registry, event_bus = make_boss()

        class SuccessfulWorker:
            name = "researcher"

            async def run(self, task):
                return "Research findings are ready."

            def get_info(self):
                return {"name": self.name}

            def get_status(self):
                return "idle"

        class FailingWorker:
            name = "analyst"

            async def run(self, task):
                raise RuntimeError("Analysis service failed")

            def get_info(self):
                return {"name": self.name}

            def get_status(self):
                return "idle"

        agent_registry.register(SuccessfulWorker())
        agent_registry.register(FailingWorker())

        async def fake_plan(user_request):
            return [
                {
                    "description": "Research the requirements",
                    "assigned_to": "researcher",
                },
                {
                    "description": "Analyze the requirements",
                    "assigned_to": "analyst",
                },
            ]

        boss.create_plan = fake_plan

        async def fake_synthesize(user_request, worker_results):
            return "\n".join(
                item["result"] for item in worker_results
            )

        boss.synthesize = fake_synthesize

        result = await boss.run(
            "Build a complex application with multiple steps"
        )

        tasks = task_manager.get_all_tasks()
        assert len(tasks) == 2

        assert any(task.status == "completed" for task in tasks)
        assert any(task.status == "failed" for task in tasks)

        assert "Research findings are ready." in result
        assert "Analysis service failed" in result
        assert (
            "incomplete" in result.lower()
            or "failed" in result.lower()
        ), "The final answer should clearly disclose partial failure"

    asyncio.run(run_test())
