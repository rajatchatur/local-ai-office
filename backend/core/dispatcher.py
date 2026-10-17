from backend.core.agent_registry import AgentRegistry
from backend.core.task_manager import TaskManager
from backend.core.event_bus import EventBus
import json

class Dispatcher:

    def __init__(
        self,
        agent_registry: AgentRegistry,
        task_manager: TaskManager,
        event_bus: EventBus,
    ):

        self.agent_registry = agent_registry
        self.task_manager = task_manager
        self.event_bus = event_bus

    async def dispatch(
        self,
        task_id: str,
    ):

        task = self.task_manager.get_task(
            task_id
        )

        if task is None:

            raise ValueError(
                f"Task {task_id} not found."
            )

        agent = self.agent_registry.get(
            task.assigned_to
        )

        if agent is None:

            raise ValueError(
                f"Agent '{task.assigned_to}' not found."
            )

        self.task_manager.start_task(
            task_id
        )

        self.event_bus.publish(
            event_type="task_started",
            agent=agent.name,
            data={
                "task_id": task.id,
                "description": task.description,
                "status": "working",
            },
        )

        self.event_bus.publish(
            event_type="agent_working",
            agent=agent.name,
            data={
                "task_id": task.id,
                "description": task.description,
            },
        )

        print(
            f"\n[{agent.name}] STARTED"
        )

        try:

            result = await agent.run(
                task.description
            )
            if agent.name == "coder":
                execution_result = result

                if isinstance(result, str):
                    try:
                        execution_result = json.loads(result)
                    except json.JSONDecodeError:
                        execution_result = None

                if isinstance(execution_result, dict):
                    execution = execution_result.get("execution", {})
                    if not isinstance(execution, dict):
                        execution = {}

                    return_code = execution.get("return_code")
                    status = str(
                        execution_result.get("status", "")
                    ).lower()

                    execution_failed = (
                        status == "failed"
                        or (
                            isinstance(return_code, int)
                            and return_code != 0
                        )
                    )

                    if execution_failed:
                        error = (
                            execution.get("stderr")
                            or execution_result.get("error")
                            or f"return_code={return_code}"
                        )

                        raise RuntimeError(
                            f"Coder execution failed: {error}"
                        )

            self.task_manager.complete_task(
                task_id,
                result,
            )

            self.event_bus.publish(
                event_type="task_completed",
                agent=agent.name,
                data={
                    "task_id": task.id,
                    "description": task.description,
                    "result": result,
                    "status": "completed",
                },
            )

            self.event_bus.publish(
                event_type="agent_completed",
                agent=agent.name,
                data={
                    "task_id": task.id,
                    "description": task.description,
                    "status": "completed",
                },
            )

            print(
                f"[{agent.name}] COMPLETED"
            )

            return result

        except Exception as exc:

            task.fail(
                str(exc)
            )

            self.event_bus.publish(
                event_type="task_failed",
                agent=agent.name,
                data={
                    "task_id": task.id,
                    "description": task.description,
                    "error": str(exc),
                    "status": "failed",
                },
            )

            self.event_bus.publish(
                event_type="agent_failed",
                agent=agent.name,
                data={
                    "task_id": task.id,
                    "description": task.description,
                    "error": str(exc),
                    "status": "failed",
                },
            )

            print(
                f"[{agent.name}] FAILED"
            )

            raise