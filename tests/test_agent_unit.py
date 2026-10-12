from backend.agents.researcher import ResearcherAgent

def test_researcher_initializes():
    researcher = ResearcherAgent()

    assert researcher is not None
    assert callable(researcher.run)
    assert callable(researcher.get_info)
