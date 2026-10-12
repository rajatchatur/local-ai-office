from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List


@dataclass
class AgentEvent:

    event_type: str
    agent: str
    data: dict
    created_at: datetime


class EventBus:

    def __init__(self):

        self.events: List[AgentEvent] = []

        self.subscribers: List[
            Callable[[AgentEvent], None]
        ] = []

    def publish(
        self,
        event_type: str,
        agent: str,
        data: dict | None = None,
    ):

        event = AgentEvent(
            event_type=event_type,
            agent=agent,
            data=data or {},
            created_at=datetime.now(),
        )

        self.events.append(event)

        print(
            f"\nEVENT: {event.event_type}"
        )

        print(
            f"Agent: {event.agent}"
        )

        for subscriber in self.subscribers:

            subscriber(event)

        return event

    def subscribe(
        self,
        subscriber: Callable[[AgentEvent], None],
    ):

        self.subscribers.append(
            subscriber
        )

    def get_all_events(self):

        return list(self.events)

    def get_events_for_agent(
        self,
        agent_name: str,
    ):

        return [
            event
            for event in self.events
            if event.agent == agent_name
        ]

    def clear(self):

        self.events.clear()