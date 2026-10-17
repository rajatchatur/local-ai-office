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
            return [{
                "description": "Perform the requested work",
                "assigned_to": "researcher",
            }]

        boss.create_plan = fake_plan

        with pytest.raises(
            RuntimeError,
            match="Simulated worker failure",
        ) as exc_info:
            await boss.run(
                "Build a complex application with multiple steps"
            )

        assert "Request incomplete" in str(exc_info.value)
        assert boss.get_status() == "failed"

        failed_tasks = [
            task for task in task_manager.get_all_tasks()
            if task.status == "failed"
        ]
        assert failed_tasks
        assert "Simulated worker failure" in failed_tasks[0].result

        event_types = [
            event.event_type for event in event_bus.get_all_events()
        ]
        assert "task_failed" in event_types
        assert "agent_failed" in event_types

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

        with pytest.raises(
            RuntimeError,
            match="Analysis service failed",
        ) as exc_info:
            await boss.run(
                "Build a complex application with multiple steps"
            )

        assert "Request incomplete" in str(exc_info.value)
        assert boss.get_status() == "failed"

        tasks = task_manager.get_all_tasks()
        assert len(tasks) == 2
        assert any(task.status == "completed" for task in tasks)
        assert any(task.status == "failed" for task in tasks)

        event_types = [
            event.event_type for event in event_bus.get_all_events()
        ]
        assert "task_completed" in event_types
        assert "task_failed" in event_types
        assert "agent_failed" in event_types

    asyncio.run(run_test())


def test_boss_preserves_original_coder_result_when_synthesizing():
    import json

    from backend.agents.boss_agent import _coder_result_context

    async def run_test():
        boss, task_manager, agent_registry, event_bus = make_boss()

        project = {
            "project_name": "MultiWorkerProject",
            "summary": "Regression test project",
            "files": [
                {
                    "path": "main.py",
                    "content": "print('ok')",
                }
            ],
            "status": "success",
            "execution": {
                "return_code": 0,
                "stdout": "ok",
                "stderr": "",
            },
        }
        original_coder_json = json.dumps(project)

        class CoderWorker:
            name = "coder"

            async def run(self, task):
                return original_coder_json

            def get_info(self):
                return {"name": self.name}

            def get_status(self):
                return "idle"

        class ResearcherWorker:
            name = "researcher"

            async def run(self, task):
                return "Research findings are ready."

            def get_info(self):
                return {"name": self.name}

            def get_status(self):
                return "idle"

        agent_registry.register(CoderWorker())
        agent_registry.register(ResearcherWorker())

        async def fake_plan(user_request):
            return [
                {
                    "description": "Build the application",
                    "assigned_to": "coder",
                },
                {
                    "description": "Research supporting information",
                    "assigned_to": "researcher",
                },
            ]

        async def fake_synthesize(user_request, worker_results):
            assert len(worker_results) == 2
            assert {item["agent"] for item in worker_results} == {
                "coder",
                "researcher",
            }
            return "Synthesized final answer."

        boss.create_plan = fake_plan
        boss.synthesize = fake_synthesize

        final_answer = await boss.run(
            "Build a complex application with multiple steps"
        )

        assert final_answer == "Synthesized final answer."

        captured_result = _coder_result_context.get()
        assert captured_result == original_coder_json
        assert json.loads(captured_result) == project

        tasks = task_manager.get_all_tasks()
        assert len(tasks) == 2
        assert all(task.status == "completed" for task in tasks)

    asyncio.run(run_test())
