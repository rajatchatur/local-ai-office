import asyncio

from backend.llm.llama_cpp_client import LlamaCppClient


async def main():
    llm = LlamaCppClient()

    response = await llm.generate(
        prompt="Explain what an AI agent is in three sentences."
    )

    print("\nLOCAL AI RESPONSE:\n")
    print(response)

    if not response.strip():
        raise AssertionError("The local LLM returned an empty response.")

    print("\nPASS: Local LLM smoke test succeeded.")


if __name__ == "__main__":
    asyncio.run(main())
