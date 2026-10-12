from backend.agents.base_agent import BaseAgent
from backend.llm.llama_cpp_client import LlamaCppClient


class AnalystAgent(BaseAgent):

    def __init__(
        self,
        event_bus=None,
        message_bus=None,
    ):

        super().__init__(
            name="analyst",
            role="Data and Business Analysis Specialist",
            event_bus=event_bus,
        )

        self.llm = LlamaCppClient()

        self.message_bus = message_bus

    async def run(
        self,
        task: str,
    ) -> str:

        self.set_status(
            "thinking",
            {
                "task": task,
            },
        )

        print(
            f"[{self.name}] Working on: {task}"
        )

        prompt = f"""
You are the Analyst in an AI office.

You have been assigned this task:

{task}

Instructions:

- Analyze the available information carefully.
- Identify important patterns and insights.
- Explain findings clearly.
- Be logical and structured.
- Do not invent information.
- Focus only on the assigned task.

Return your analysis.
"""

        try:

            result = await self.llm.generate(
                prompt
            )

            # --------------------------------------------------
            # Send result to Boss
            # --------------------------------------------------

            if self.message_bus:

                self.message_bus.send(
                    sender=self.name,
                    receiver="boss",
                    content=result,
                )

            self.set_status(
                "idle",
                {
                    "task": task,
                },
            )

            return result

        except Exception as exc:

            self.set_status(
                "failed",
                {
                    "task": task,
                    "error": str(exc),
                },
            )

            raise