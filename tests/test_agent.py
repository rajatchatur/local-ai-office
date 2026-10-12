import asyncio

from backend.agents.researcher import ResearcherAgent


async def main():

    researcher = ResearcherAgent()

    print("Agent:")
    print(researcher.get_info())

    result = await researcher.run(
        "Research Indian motor vehicle laws"
    )

    print("\nResult:")
    print(result)

    print("\nAgent after task:")
    print(researcher.get_info())


if __name__ == "__main__":
    asyncio.run(main())
