import asyncio

from backend.agents.coder import CoderAgent


FAILURE = {
    "return_code": 1,
    "stdout": "",
    "stderr": (
        "GET /stories raised an exception:\n"
        "jinja2.exceptions.TemplateNotFound: stories.html\n\n"
        "GET /board raised an exception:\n"
        "jinja2.exceptions.TemplateNotFound: board.html\n"
    ),
}


def test_missing_template_names_lists_each_safe_name_once():
    result = {
        "stderr": (
            "TemplateNotFound: stories.html\n"
            "TemplateNotFound: stories.html\n"
            "TemplateNotFound: sub/page.html\n"
            "TemplateNotFound: ../secret.html\n"
            "TemplateNotFound: /etc/passwd.html\n"
            "TemplateNotFound: notes.txt\n"
        ),
        "stdout": "",
    }

    assert CoderAgent._missing_template_names(result) == [
        "stories.html",
        "sub/page.html",
    ]


def test_missing_template_names_ignores_other_failures():
    result = {"stderr": "NameError: name 'x' is not defined", "stdout": ""}
    assert CoderAgent._missing_template_names(result) == []
    assert CoderAgent._missing_template_names(None) == []


def make_agent(files, reply):
    agent = object.__new__(CoderAgent)
    created = {}

    class FakeWorkspace:
        def create_file(self, relative_path, content):
            created[relative_path] = content

    class FakeLLM:
        def __init__(self):
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            return reply

    agent.workspace = FakeWorkspace()
    agent.llm = FakeLLM()
    agent.inspect_project = lambda name: dict(files)
    return agent, created


def test_repair_creates_each_missing_template_and_strips_fences():
    agent, created = make_agent(
        {"Proj/main.py": "from flask import Flask\napp = Flask(__name__)\n"},
        "```html\n<h1>{{ title }}</h1>\n```",
    )

    repaired = asyncio.run(agent._repair_missing_templates("Proj", FAILURE))

    assert repaired is True
    assert set(created) == {
        "Proj/templates/stories.html",
        "Proj/templates/board.html",
    }
    assert created["Proj/templates/stories.html"] == "<h1>{{ title }}</h1>\n"


def test_repair_does_not_overwrite_existing_template():
    agent, created = make_agent(
        {
            "Proj/main.py": "app = None\n",
            "Proj/templates/stories.html": "<p>keep</p>\n",
            "Proj/templates/board.html": "<p>keep</p>\n",
        },
        "<p>new</p>",
    )

    repaired = asyncio.run(agent._repair_missing_templates("Proj", FAILURE))

    assert repaired is False
    assert created == {}
    assert agent.llm.calls == 0


def test_repair_ignores_replies_that_are_not_html():
    agent, created = make_agent(
        {"Proj/main.py": "app = None\n"},
        '{"file": "x"}',
    )

    repaired = asyncio.run(agent._repair_missing_templates("Proj", FAILURE))

    assert repaired is False
    assert created == {}
