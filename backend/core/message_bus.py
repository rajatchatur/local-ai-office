from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List


@dataclass
class AgentMessage:

    sender: str
    receiver: str
    content: str
    created_at: datetime


class MessageBus:

    def __init__(self):

        self.messages: List[AgentMessage] = []

        self.subscribers: List[
            Callable[[AgentMessage], None]
        ] = []


    def subscribe(
        self,
        subscriber: Callable[[AgentMessage], None],
    ):

        self.subscribers.append(
            subscriber
        )


    def send(
        self,
        sender: str,
        receiver: str,
        content: str,
    ):

        message = AgentMessage(
            sender=sender,
            receiver=receiver,
            content=content,
            created_at=datetime.now(),
        )

        self.messages.append(
            message
        )

        print(
            f"\nMESSAGE: {sender} → {receiver}"
        )

        print(
            f"         {content}"
        )

        for subscriber in self.subscribers:

            subscriber(
                message
            )

        return message


    def get_messages_for(
        self,
        receiver: str,
    ):

        return [
            message
            for message in self.messages
            if message.receiver == receiver
        ]


    def get_messages_from(
        self,
        sender: str,
    ):

        return [
            message
            for message in self.messages
            if message.sender == sender
        ]


    def get_all_messages(self):

        return list(
            self.messages
        )


    def clear(self):

        self.messages.clear()