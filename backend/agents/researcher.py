from backend.agents.base_agent import BaseAgent
from backend.llm.llama_cpp_client import LlamaCppClient


class ResearcherAgent(BaseAgent):

    def __init__(
        self,
        event_bus=None,
        message_bus=None,
    ):

        super().__init__(
            name="researcher",
            role="Research Specialist",
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
You are the Research Specialist in an AI office.

Your job is to provide concise, accurate information
about the assigned task.

Task:
{task}

Instructions:

- Answer only the assigned task.
- Give the key facts needed by the Boss.
- Keep the response short: maximum 150 words.
- Prefer simple explanations and small examples when useful.
- Do not repeat the question.
- Do not add unnecessary background information.
- Do not invent facts.
- Do not claim that you searched the internet unless
  an actual web search tool was used.
- For technical questions, prioritize correctness.
- For Python questions, remember that dictionaries
  preserve insertion order in Python 3.7+.

Return only the research findings.
"""

        try:

            result = await self.llm.generate(
                prompt
            )

            # --------------------------------------------------
            # Send result to Boss through MessageBus
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