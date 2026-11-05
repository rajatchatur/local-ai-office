import asyncio

from backend.agents.coder import CoderAgent


def test_project_locks_are_reused_per_project():
    agent = object.__new__(CoderAgent)

    assert agent._project_lock("alpha") is agent._project_lock("alpha")
    assert agent._project_lock("alpha") is not agent._project_lock("beta")


def test_same_project_updates_are_serialized():
    async def run_test():
        agent = object.__new__(CoderAgent)
        active = 0
        max_active = 0

        async def locked_update(task, project_name):
            nonlocal active, max_active

            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return project_name

        agent._update_existing_project_locked = locked_update

        await asyncio.gather(
            agent._update_existing_project("Update main.py", "alpha"),
            agent._update_existing_project("Update main.py", "alpha"),
        )

        assert max_active == 1

    asyncio.run(run_test())


def test_different_projects_are_not_serialized():
    async def run_test():
        agent = object.__new__(CoderAgent)
        active = 0
        max_active = 0

        async def locked_update(task, project_name):
            nonlocal active, max_active

            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return project_name

        agent._update_existing_project_locked = locked_update

        await asyncio.gather(
            agent._update_existing_project("Update main.py", "alpha"),
            agent._update_existing_project("Update main.py", "beta"),
        )

        assert max_active == 2

    asyncio.run(run_test())
