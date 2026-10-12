import asyncio

from backend.agents.boss_agent import BossAgent
from backend.agents.researcher import ResearcherAgent
from backend.agents.coder import CoderAgent
from backend.agents.analyst import AnalystAgent

from backend.core.task_manager import TaskManager
from backend.core.agent_registry import AgentRegistry
from backend.core.message_bus import MessageBus
from backend.core.event_bus import EventBus

async def main():

    # --------------------------------
    # Create core systems
    # --------------------------------

    task_manager = TaskManager()

    agent_registry = AgentRegistry()

    message_bus = MessageBus()

    event_bus = EventBus()

    def handle_event(event):

        print(
            f"\nUI RECEIVED EVENT: "
            f"{event.event_type}"
        )

        print(
            f"Agent: {event.agent}"
        )

        print(
            f"Data: {event.data}"
        )


    event_bus.subscribe(
        handle_event
    )

    # --------------------------------
    # Create worker
    # --------------------------------

    researcher = ResearcherAgent(
        event_bus=event_bus,
    message_bus=message_bus,
    )

    coder = CoderAgent(
        event_bus=event_bus,
    message_bus=message_bus,
    )

    analyst = AnalystAgent(
        event_bus=event_bus,
    message_bus=message_bus,
    )


    agent_registry.register(
        researcher
    )

    agent_registry.register(
        coder
    )

    agent_registry.register(
    analyst
)

    # --------------------------------
    # Create Boss
    # --------------------------------

    boss = BossAgent(
                        task_manager=task_manager,
                        agent_registry=agent_registry,
                        message_bus=message_bus,
                        event_bus=event_bus,
                    )

    # --------------------------------
    # User request
    # --------------------------------

    request = """
                Analyze the Indian motor vehicle law requirements
                for obtaining and maintaining a valid driving licence.

                I want:
                1. The relevant legal provisions researched.
                2. The important sections organized clearly.
                3. A structured analysis of the implications.
                """

    print("\n")
    print("=" * 70)
    print("LOCAL AI OFFICE")
    print("=" * 70)

    print("\nUSER:")
    print(request)

    # --------------------------------
    # Boss handles everything
    # --------------------------------
    
    final_answer = await boss.run(
        request
    )

    # --------------------------------
    # Final answer
    # --------------------------------

    print("\n")
    print("=" * 70)
    print("BOSS FINAL ANSWER")
    print("=" * 70)

    print(final_answer)

    # --------------------------------
    # Show task history
    # --------------------------------
    print("\n")
    print("=" * 70)
    print("MESSAGE HISTORY")
    print("=" * 70)

    for message in message_bus.get_all_messages():

        print(
            f"\n{message.sender} → {message.receiver}"
        )

        print(
            f"Message: {message.content}"
        )

        print(
            f"Time: {message.created_at}"
        )
    print("\n")
    print("=" * 70)
    print("TASK HISTORY")
    print("=" * 70)

    for task in task_manager.get_all_tasks():

        print(
            f"\nTask ID: {task.id}"
        )

        print(
            f"Assigned to: {task.assigned_to}"
        )

        print(
            f"Status: {task.status}"
        )


if __name__ == "__main__":

    asyncio.run(main())