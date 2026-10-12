from backend.agents.base_agent import BaseAgent
from backend.llm.llama_cpp_client import LlamaCppClient


class GenericAgent(BaseAgent):

    def __init__(
        self,
        name: str,
        role: str,
        instructions: str = "",
        event_bus=None,
        message_bus=None,
        model: str = "llama3.1:latest",
    ):

        super().__init__(
            name=name,
            role=role,
            event_bus=event_bus,
        )

        self.instructions = instructions
        self.message_bus = message_bus
        self.llm = LlamaCppClient(
            model=model
        )

    async def run(
        self,
        task: str,
    ) -> str:

        self.set_status(
            "thinking",
            {
                "task": task
            },
        )

        prompt = f"""
You are an AI worker inside a local multi-agent office.

Your name:
{self.name}

Your role:
{self.role}

Your instructions:
{self.instructions}

Task assigned by the Boss:
{task}

Complete the task as accurately as possible.

Important rules:

1. Do not invent facts.
2. Do not claim that you searched the internet.
3. Do not claim that you executed code unless you actually did.
4. Clearly state assumptions when necessary.
5. Return a useful result to the Boss.
"""

        try:

            result = await self.llm.generate(
                prompt
            )

            if self.message_bus:

                self.message_bus.send(
                    sender=self.name,
                    receiver="boss",
                    content=result,
                )

            self.set_status(
                "idle"
            )

            return result

        except Exception as exc:

            self.set_status(
                "failed",
                {
                    "error": str(exc)
                },
            )

            raise