import asyncio

from backend.core.task_manager import TaskManager
from backend.core.agent_registry import AgentRegistry
from backend.core.message_bus import MessageBus
from backend.core.event_bus import EventBus

from backend.agents.researcher import ResearcherAgent
from backend.agents.coder import CoderAgent
from backend.agents.analyst import AnalystAgent
from backend.agents.boss_agent import BossAgent
from backend.agents.generic_agent import GenericAgent

from backend.api.event_bridge import handle_agent_event
from backend.api.message_bridge import handle_agent_message
from backend.core.artifact_manager import ArtifactManager

class Application:

    def __init__(self):

        print(
            "\nINITIALIZING LOCAL AI OFFICE..."
        )

        self.task_manager = TaskManager()

        self.agent_registry = AgentRegistry()

        self.message_bus = MessageBus()

        self.event_bus = EventBus()

        self.artifact_manager = ArtifactManager()

        self.background_tasks: set[asyncio.Task] = set()


        # Event → WebSocket

        self.event_bus.subscribe(
            handle_agent_event
        )


        # Message → WebSocket

        self.message_bus.subscribe(
            handle_agent_message
        )


        # ------------------------------------------------
        # DEFAULT WORKERS
        # ------------------------------------------------

        self.researcher = ResearcherAgent(
            event_bus=self.event_bus,
            message_bus=self.message_bus,
        )

        self.coder = CoderAgent(
            event_bus=self.event_bus,
            message_bus=self.message_bus,
        )

        self.analyst = AnalystAgent(
            event_bus=self.event_bus,
            message_bus=self.message_bus,
        )


        self.agent_registry.register(
            self.researcher
        )

        self.agent_registry.register(
            self.coder
        )

        self.agent_registry.register(
            self.analyst
        )


        # ------------------------------------------------
        # BOSS
        # ------------------------------------------------

        self.boss = BossAgent(
            task_manager=self.task_manager,
            agent_registry=self.agent_registry,
            message_bus=self.message_bus,
            event_bus=self.event_bus,
        )


        print(
            "LOCAL AI OFFICE READY."
        )


    # ====================================================
    # BACKGROUND TASKS
    # ====================================================

    def track_task(
        self,
        coro,
        name: str | None = None,
    ) -> asyncio.Task:

        task = asyncio.create_task(
            coro,
            name=name,
        )

        self.background_tasks.add(task)

        task.add_done_callback(
            self.background_tasks.discard
        )

        return task


    async def shutdown(self) -> None:

        tasks = [
            task
            for task in self.background_tasks
            if not task.done()
        ]

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )


    # ====================================================
    # ADD AGENT
    # ====================================================

    def add_agent(
        self,
        name: str,
        role: str,
        instructions: str = "",
    ):

        agent = GenericAgent(

            name=name,

            role=role,

            instructions=instructions,

            event_bus=self.event_bus,

            message_bus=self.message_bus,
        )


        self.agent_registry.register(
            agent
        )


        self.event_bus.publish(

            event_type="agent_added",

            agent=name,

            data={
                "name": name,
                "role": role,
                "status": "idle",
            },
        )


        return agent


    # ====================================================
    # REMOVE AGENT
    # ====================================================

    def remove_agent(
        self,
        name: str,
    ):

        if name == "boss":

            raise ValueError(
                "Boss cannot be removed."
            )


        agent = self.agent_registry.get(
            name
        )


        if agent is None:

            raise ValueError(
                f"Agent '{name}' does not exist."
            )


        if agent.get_status() != "idle":

            raise ValueError(
                f"Agent '{name}' is currently "
                f"{agent.get_status()}."
            )


        self.agent_registry.remove(
            name
        )


        self.event_bus.publish(

            event_type="agent_removed",

            agent=name,

            data={
                "name": name,
            },
        )


        return True


application = Application()