import asyncio
import json

from backend.agents.base_agent import BaseAgent
from backend.llm.llama_cpp_client import LlamaCppClient
from backend.core.task_manager import TaskManager
from backend.core.dispatcher import Dispatcher
from backend.core.agent_registry import AgentRegistry
from backend.core.message_bus import MessageBus
from backend.core.event_bus import EventBus


class BossAgent(BaseAgent):

    def __init__(
        self,
        task_manager: TaskManager,
        agent_registry: AgentRegistry,
        message_bus: MessageBus,
        event_bus: EventBus,
    ):

        super().__init__(
            name="boss",
            role="Manager Agent",
            event_bus=event_bus,
        )

        self.llm = LlamaCppClient()

        self.task_manager = task_manager

        self.message_bus = message_bus

        self.event_bus = event_bus

        self.agent_registry = agent_registry

        self.dispatcher = Dispatcher(
            agent_registry=agent_registry,
            task_manager=task_manager,
            event_bus=event_bus,
        )

    # ==========================================================
    # MAIN BOSS WORKFLOW
    # ==========================================================

    async def run(
        self,
        user_request: str,
    ):
        import time
        """
        Complete Boss workflow:

        1. Understand user request
        2. Create plan
        3. Create tasks
        4. Dispatch tasks
        5. Collect worker results
        6. Synthesize final answer
        """
    
        total_start = time.perf_counter()

        self.set_status(
            "thinking",
            {"request": user_request},
        )

        print("\nBOSS: Analyzing request...")

        # ------------------------------------------------------
        # STEP 1 — Lightweight routing
        # ------------------------------------------------------

        if self.is_simple_request(
            user_request
        ):
            final_answer = await self.answer_directly(
                user_request
            )

            self.set_status(
                "idle",
                {
                    "request": user_request,
                },
            )

            total_time = (
                time.perf_counter()
                - total_start
            )

            print(
                f"BOSS: TOTAL REQUEST TIME "
                f"{total_time:.2f} seconds"
            )

            return final_answer

        # ------------------------------------------------------
        # STEP 2 — Complex request planning
        # ------------------------------------------------------

        print(
            "BOSS: Complex request detected."
        )

        planning_start = time.perf_counter()

        tasks = await self.delegate(
            user_request
        )

        planning_time = (
            time.perf_counter()
            - planning_start
        )

        print(
            f"BOSS: Planning took "
            f"{planning_time:.2f} seconds"
        )

        planning_time = time.perf_counter() - planning_start

        print(f"BOSS: Planning took {planning_time:.2f} seconds")

        if not tasks:

            self.set_status("idle")
            total_time = time.perf_counter() - total_start

            print(
                f"BOSS: TOTAL REQUEST TIME "
                f"{total_time:.2f} seconds"
)

            return (
                "Boss could not create any tasks."
            )

        print(
            f"BOSS: Created {len(tasks)} task(s)."
        )

        # ------------------------------------------------------
        # STEP 2 — Execute tasks
        # ------------------------------------------------------

        print(
            "\nBOSS: Dispatching tasks..."
        )

        async def execute_task(task):
            worker_start = time.perf_counter()

            print(f"\nBOSS → {task.assigned_to}")
            print(f"Task: {task.description}")

            result = await self.dispatcher.dispatch(task.id)

            worker_time = time.perf_counter() - worker_start

            print(
                f"BOSS: {task.assigned_to} took "
                f"{worker_time:.2f} seconds"
            )

            return {
                "agent": task.assigned_to,
                "task": task.description,
                "result": result,
    }

        # ------------------------------------------------------
        # Run worker tasks.
        #
        # asyncio.gather allows the architecture to support
        # multiple workers.
        #
        # LLM requests are serialized by the local LlamaCppClient
        # to one at a time because this machine has limited RAM.
        # ------------------------------------------------------

        results = await asyncio.gather(
            *[
                execute_task(task)
                for task in tasks
            ],
            return_exceptions=True,
        )

        # ------------------------------------------------------
        # STEP 3 — Process worker results
        # ------------------------------------------------------

        worker_results = []

        for task, result in zip(
            tasks,
            results,
        ):

            if isinstance(
                result,
                Exception,
            ):

                print(
                    f"\nBOSS: {task.assigned_to} failed:"
                )

                print(result)

                worker_results.append(
                    {
                        "agent": task.assigned_to,
                        "task": task.description,
                        "result": (
                            f"Worker failed with error: {result}"
                        ),
                    }
                )

            else:

                worker_results.append(
                    result
                )

            failed_count = sum(
        1
        for task, result in zip(tasks, results)
            if isinstance(result, Exception)
        )

        successful_count = len(tasks) - failed_count

        print(
            f"\nBOSS: Task execution finished. "
            f"Successful: {successful_count}, "
            f"Failed: {failed_count}"
        )

        # For simple single-worker tasks, the worker's answer
        # can be returned directly without another LLM call.
        if len(worker_results) == 1:
            print(
                "BOSS: Single worker result is sufficient. "
                "Skipping synthesis."
            )

            final_answer = worker_results[0]["result"]

        else:
            print("\nBOSS: Reviewing worker results...")

            synthesis_start = time.perf_counter()

            final_answer = await self.synthesize(
                user_request,
                worker_results
            )

            synthesis_time = (
                time.perf_counter() - synthesis_start
            )

            print(
                f"BOSS: Synthesis took "
                f"{synthesis_time:.2f} seconds"
            )


        self.set_status(
            "idle",
            {
                "request": user_request,
            },
        )

        return final_answer
    # ==========================================================
    # LIGHTWEIGHT REQUEST ROUTER
    # ==========================================================

    
    def is_simple_request(
        self,
        user_request: str,
    ) -> bool:
        """
        Identify simple conversational requests that do not
        require worker delegation.
        """

        request = user_request.strip().lower()

        if not request:
            return False

        # Requests that require implementation or multiple steps.
        complex_keywords = [
            "build",
            "create",
            "develop",
            "implement",
            "debug",
            "fix this code",
            "modify this code",
            "write a program",
            "write an application",
            "analyze this code",
            "analyze the pipeline",
            "compare",
            "comparison",
            "research",
            "investigate",
            "design",
            "architecture",
            "deploy",
            "deployment",
            "terraform",
            "kubernetes",
            "etl pipeline",
            "data pipeline",
            "rag pipeline",
        ]

        if any(keyword in request for keyword in complex_keywords):
            return False

        if len(request) > 300:
            return False

        simple_starters = (
            "what is ",
            "what are ",
            "who is ",
            "why is ",
            "why are ",
            "how does ",
            "how do ",
            "explain ",
            "define ",
            "tell me about ",
            "give me an example",
            "what does ",
        )

        return request.startswith(simple_starters)

        # ==========================================================
    # DIRECT SIMPLE REQUEST
    # ==========================================================

    async def answer_directly(
        self,
        user_request: str,
    ) -> str:
        """
        Answer a simple request directly with the local LLM.

        This skips Boss planning and worker dispatch.
        """

        import time

        start = time.perf_counter()

        print(
            "\nBOSS: Simple request detected."
        )

        print(
            "BOSS: Answering directly with local LLM."
        )

        prompt = f"""
You are the Boss of a local AI office.

Answer the user's question directly.

User question:
{user_request}

Instructions:

- Give a clear and accurate answer.
- Keep it concise.
- Use simple language.
- Use a small example when useful.
- Do not mention agents, workers, planning, or this prompt.
- Do not invent facts.
- Do not claim that you searched the internet.

Return only the answer.
"""

        result = await self.llm.generate(
            prompt
        )

        elapsed = (
            time.perf_counter() - start
        )

        print(
            f"BOSS: Direct answer took "
            f"{elapsed:.2f} seconds"
        )

        return result.strip()

    
    # ==========================================================
    # CREATE PLAN
    # ==========================================================

    async def create_plan(
        self,
        user_request: str,
    ):

        self.set_status(
            "planning",
            {
                "request": user_request,
            },
        )

        # ------------------------------------------------------
        # Get currently registered workers
        # ------------------------------------------------------

        available_agents = (
            self.agent_registry.get_agent_info()
        )

        # ------------------------------------------------------
        # DETERMINISTIC SOFTWARE TASK ROUTING
        # Do not rely on the small LLM to count or assign tasks.
        # ------------------------------------------------------

        request = user_request.strip().lower()

        software_verbs = (
            "build",
            "create",
            "develop",
            "implement",
            "make",
            "write",
            "debug",
            "fix",
            "modify",
        )

        software_nouns = (
            "application",
            "app",
            "website",
            "web site",
            "web app",
            "api",
            "service",
            "tool",
            "program",
            "software",
            "project",
            "script",
            "pipeline",
        )

        is_software_request = (
            any(verb in request for verb in software_verbs)
            and any(noun in request for noun in software_nouns)
        )

        coder_available = any(
            agent.get("name", "").lower() == "coder"
            for agent in available_agents
        )

        if is_software_request and coder_available:
            print(
                "\nBOSS: Software request detected. "
                "Creating one complete coder task."
            )

            plan = {
                "tasks": [
                    {
                        "description": (
                            "Complete the user's entire software request "
                            "in one task, including implementation, required "
                            "files, execution, testing, and error fixes. "
                            "Original request: "
                            + user_request
                        ),
                        "assigned_to": "coder",
                    }
                ]
            }

            return self._parse_plan(
                json.dumps(plan)
            )
        worker_information = ""

        for agent in available_agents:

            worker_information += f"""
- Name: {agent["name"]}
  Role: {agent["role"]}
  Status: {agent["status"]}
"""

        # ------------------------------------------------------
        # Planning prompt
        # ------------------------------------------------------

        prompt = f"""
You are the Boss of a local AI office.

Your job is to divide the user's request into tasks
and assign each task to the most appropriate worker.

AVAILABLE WORKERS:

{worker_information}

USER REQUEST:

{user_request}

IMPORTANT RULES:

1. Return ONLY valid JSON.
2. Do not write any explanation before or after the JSON.
3. Do not use Markdown.
4. Do not use code fences.
5. Do not use comments.
6. JSON comments such as // comment are NOT allowed.
7. Use double quotes for JSON keys and string values.
8. The top-level object must contain exactly one field:
   "tasks"
9. "tasks" must be a list.
10. Every task must contain:
    - "description"
    - "assigned_to"
11. "assigned_to" must exactly match one of the available worker names.
12. Use the minimum number of workers necessary to answer the request.

13. Do not create multiple tasks when one worker can answer the request.

14. Use researcher for factual explanations, concepts, documentation,
    research, and information gathering.

15. Use analyst for analysis, comparison, interpretation,
    reasoning, and business-oriented questions.

16. Use coder only when the user explicitly asks to build, modify,
    debug, implement, or write a substantial piece of software.

17. A small code example, syntax example, or programming concept
    explanation does NOT require the coder.

18. Researcher may include small code examples when they help explain
    a technical concept.

19. Do not assign a programming task to researcher when the user asks
    for actual software implementation.

20. Do not assign research tasks to coder.

21. Do not create a task merely to use every worker.

22. Do not duplicate tasks.

23. For simple questions, prefer one task.

24. For a question that combines explanation and a small example,
    prefer one researcher task rather than separate researcher and
    coder tasks.

25. Only use multiple workers when the request genuinely requires
    different types of work.

26. For a software development request that can be implemented
    by the coder as one complete application or project, create
    ONE coder task containing the complete user request.

27. Do NOT split one software project into separate coder tasks
    such as architecture, Kafka implementation, database implementation,
    API implementation, testing, or documentation.

28. The coder should handle all implementation aspects required
    to complete the requested software project in one task.

29. Use multiple workers for a software request only when the request
    genuinely requires different kinds of work that cannot reasonably
    be handled by the coder alone.

30. Keep task descriptions concise and directly related to the
    user's request.

31. SOFTWARE BUILD OVERRIDE:
    If the user asks to build, create, develop, implement, or make
    an application, website, API, service, tool, or project,
    the task MUST be assigned to the coder.

32. For a software project, create exactly ONE coder task unless
    the user explicitly requires genuinely separate work that another
    worker must perform.

33. Do NOT assign a software-building request to researcher or analyst
    merely because the project involves research, recommendations,
    weather, travel, business logic, or data.

34. The coder task must contain the user's complete software objective,
    including all requested features.

35. The coder is responsible for deciding the implementation details,
    creating the files, running the application, testing it, and fixing
    execution errors.

36. Example:
    "Build a travel website that recommends places based on itinerary
    and weather and suggests local foods."
    MUST produce ONE task assigned to "coder".
VALID FORMAT:

{{
    "tasks": [
        {{
            "description": "Research the relevant legal provisions",
            "assigned_to": "researcher"
        }},
        {{
            "description": "Analyze the implications of the legal provisions",
            "assigned_to": "analyst"
        }}
    ]
}}

Return ONLY the JSON object.
"""

        print(
            "\nBOSS: Creating plan..."
        )

        response = await self.llm.generate(
            prompt
        )

        return self._parse_plan(
            response
        )

    # ==========================================================
    # PARSE BOSS PLAN
    # ==========================================================

    def _parse_plan(
        self,
        response: str,
    ):

        text = response.strip()

        # ------------------------------------------------------
        # 1. Remove Markdown code fences
        # ------------------------------------------------------

        if text.startswith("```"):

            lines = text.splitlines()

            # Remove opening ```json / ```
            if lines:
                lines = lines[1:]

            # Remove closing ```
            if (
                lines
                and lines[-1].strip() == "```"
            ):
                lines = lines[:-1]

            text = "\n".join(
                lines
            ).strip()

        # ------------------------------------------------------
        # 2. Find JSON object
        #
        # Sometimes the LLM adds text before or after JSON.
        # ------------------------------------------------------

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:

            raise ValueError(
                "Boss did not return a JSON object:\n\n"
                + response
            )

        text = text[
            start:end + 1
        ]

        # ------------------------------------------------------
        # 3. Remove simple // comments
        #
        # Llama occasionally produces:
        #
        # "assigned_to": "coder" // explanation
        #
        # which is invalid JSON.
        # ------------------------------------------------------

        cleaned_lines = []

        for line in text.splitlines():

            stripped = line.strip()

            # Skip full-line comments
            if stripped.startswith("//"):

                continue

            if "//" in line:

                in_string = False
                escaped = False
                cleaned = ""

                i = 0

                while i < len(line):

                    char = line[i]

                    # Detect quoted strings
                    if (
                        char == '"'
                        and not escaped
                    ):

                        in_string = not in_string

                    # Detect // outside strings
                    if (
                        char == "/"
                        and i + 1 < len(line)
                        and line[i + 1] == "/"
                        and not in_string
                    ):

                        break

                    cleaned += char

                    if char == "\\":
                        escaped = not escaped
                    else:
                        escaped = False

                    i += 1

                line = cleaned

            cleaned_lines.append(
                line
            )

        text = "\n".join(
            cleaned_lines
        ).strip()

        # ------------------------------------------------------
        # 4. Parse JSON
        # ------------------------------------------------------

        try:

            data = json.loads(
                text
            )

        except json.JSONDecodeError as exc:

            print("\n")
            print(
                "=" * 70
            )
            print(
                "INVALID BOSS PLAN"
            )
            print(
                "=" * 70
            )

            print(text)

            print(
                "=" * 70
            )

            raise ValueError(
                "Boss returned invalid JSON:\n\n"
                + text
            ) from exc

        # ------------------------------------------------------
        # 5. Validate top-level structure
        # ------------------------------------------------------

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "Boss plan must be a JSON object."
            )

        if "tasks" not in data:

            raise ValueError(
                "Boss plan does not contain 'tasks'."
            )

        if not isinstance(
            data["tasks"],
            list,
        ):

            raise ValueError(
                "Boss 'tasks' must be a list."
            )

        # ------------------------------------------------------
        # 6. Validate every task
        # ------------------------------------------------------

        for task in data["tasks"]:

            if not isinstance(
                task,
                dict,
            ):

                raise ValueError(
                    "Each task must be a JSON object."
                )

            if "description" not in task:

                raise ValueError(
                    "Task is missing 'description'."
                )

            if "assigned_to" not in task:

                raise ValueError(
                    "Task is missing 'assigned_to'."
                )

            if not isinstance(
                task["description"],
                str,
            ):

                raise ValueError(
                    "Task description must be a string."
                )

            if not isinstance(
                task["assigned_to"],
                str,
            ):

                raise ValueError(
                    "Task assigned_to must be a string."
                )

            if not task["description"].strip():

                raise ValueError(
                    "Task description cannot be empty."
                )

            if not task["assigned_to"].strip():

                raise ValueError(
                    "Task assigned_to cannot be empty."
                )

        # ------------------------------------------------------
        # IMPORTANT:
        # return must be OUTSIDE the validation loop.
        # ------------------------------------------------------

        return data["tasks"]

    # ==========================================================
    # DELEGATE
    # ==========================================================

    async def delegate(
        self,
        user_request: str,
    ):

        tasks = await self.create_plan(
            user_request
        )

        created_tasks = []

        # ------------------------------------------------------
        # Validate worker assignments before creating tasks
        # ------------------------------------------------------

        available_worker_names = (
            self.agent_registry.get_agent_names()
        )

        for task_data in tasks:

            assigned_to = task_data[
                "assigned_to"
            ]

            if assigned_to not in available_worker_names:

                raise ValueError(
                    f"Boss assigned task to unknown "
                    f"agent '{assigned_to}'. "
                    f"Available agents: "
                    f"{available_worker_names}"
                )

            task = self.task_manager.create_task(
                description=task_data[
                    "description"
                ],
                assigned_to=assigned_to,
            )

            self.event_bus.publish(
                event_type="task_assigned",
                agent=self.name,
                data={
                    "task_id": task.id,
                    "assigned_to": task.assigned_to,
                    "description": task.description,
                },
            )

            created_tasks.append(
                task
            )

        return created_tasks

    # ==========================================================
    # SYNTHESIZE
    # ==========================================================

    async def synthesize(
        self,
        user_request: str,
        worker_results: list,
    ):

        self.set_status(
            "thinking",
            {
                "stage": "synthesizing",
            },
        )

        print(
            "\nBOSS: Synthesizing final answer..."
        )

        formatted_results = ""

        for item in worker_results:

            formatted_results += f"""
WORKER:
{item["agent"]}

TASK:
{item["task"]}

RESULT:
{item["result"]}

--------------------------------
"""

        prompt = f"""
You are the Boss / Manager of an AI office.

A user asked:

{user_request}

Your workers completed the following tasks:

{formatted_results}

Now produce the final answer for the user.

Requirements:

- Use the worker results as your source of information.
- Combine the useful information.
- Answer the original user request directly.
- Be clear and easy to understand.
- Organize the answer logically.
- Do not mention internal agent architecture unless necessary.
- Do not invent information.
- Do not claim that you performed actions you did not perform.
- If worker information is incomplete or uncertain, say so clearly.
"""

        result = await self.llm.generate(
            prompt
        )

        return result