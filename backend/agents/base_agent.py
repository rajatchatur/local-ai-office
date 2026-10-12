from abc import ABC, abstractmethod


class BaseAgent(ABC):

    def __init__(
        self,
        name: str,
        role: str,
        event_bus=None,
    ):

        self.name = name
        self.role = role
        self.status = "idle"
        self.event_bus = event_bus

    def set_status(
        self,
        status: str,
        data: dict | None = None,
    ):

        self.status = status

        print(
            f"[{self.name}] STATUS → {status}"
        )

        if self.event_bus:

            event_type = f"agent_{status}"

            event_data = {
                "status": status,
            }

            if data:

                event_data.update(data)

            self.event_bus.publish(
                event_type=event_type,
                agent=self.name,
                data=event_data,
            )

    def get_status(self) -> str:

        return self.status

    def get_info(self):

        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }

    @abstractmethod
    async def run(
        self,
        task: str,
    ) -> str:

        pass