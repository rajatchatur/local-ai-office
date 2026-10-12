import json
from fastapi import Query

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from pydantic import BaseModel

import asyncio
import uuid

from backend.core.application import application


router = APIRouter()


# ========================================================
# MODELS
# ========================================================

class ChatRequest(BaseModel):

    message: str


class ChatResponse(BaseModel):

    request_id: str

    status: str


class CreateAgentRequest(BaseModel):

    name: str

    role: str

    instructions: str = ""


# ========================================================
# HEALTH
# ========================================================

@router.get("/health")
async def health():

    return {
        "status": "healthy"
    }


# ========================================================
# AGENTS
# ========================================================

@router.get("/agents")
async def agents():

    return {

        "agents":
            application.agent_registry
            .get_agent_info()

    }


# ========================================================
# ADD AGENT
# ========================================================

@router.post("/agents")
async def add_agent(
    request: CreateAgentRequest,
):

    name = request.name.strip().lower()

    role = request.role.strip()

    instructions = request.instructions.strip()


    if not name:

        raise HTTPException(
            status_code=400,
            detail="Agent name is required.",
        )


    if name == "boss":

        raise HTTPException(
            status_code=400,
            detail="Boss is reserved.",
        )


    if application.agent_registry.has_agent(
        name
    ):

        raise HTTPException(
            status_code=409,
            detail=f"Agent '{name}' already exists.",
        )


    try:

        agent = application.add_agent(
            name=name,
            role=role,
            instructions=instructions,
        )


        return {
            "status": "created",
            "agent": agent.get_info(),
        }


    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ========================================================
# REMOVE AGENT
# ========================================================

@router.delete("/agents/{agent_name}")
async def remove_agent(
    agent_name: str,
):

    try:

        application.remove_agent(
            agent_name
        )


        return {
            "status": "removed",
            "agent": agent_name,
        }


    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ========================================================
# CHAT WITH BOSS
# ========================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
):

    request_id = str(
        uuid.uuid4()
    )


    print("\n")
    print("=" * 70)
    print("NEW USER REQUEST")
    print("=" * 70)
    print(request.message)
    print(
        f"REQUEST ID: {request_id}"
    )
    print("=" * 70)


    asyncio.create_task(

        run_boss(

            request.message,

            request_id,
        )
    )


    return ChatResponse(

        request_id=request_id,

        status="started",
    )


# ========================================================
# RUN BOSS
# ========================================================

async def run_boss(
    message: str,
    request_id: str,
):

    try:

        application.event_bus.publish(

            event_type="request_started",

            agent="boss",

            data={

                "request_id":
                    request_id,

                "message":
                    message,
            },
        )


        result = await application.boss.run(
            message
        )

        artifact = await persist_coder_artifact(
                                                    request_id
                                                )

        application.event_bus.publish(
                                        event_type="request_completed",
                                        agent="boss",
                                        data={
                                            "request_id": request_id,
                                            "response": result,
                                            "artifact": artifact,
                                        },
                                    )


    except Exception as exc:

        application.event_bus.publish(

            event_type="request_failed",

            agent="boss",

            data={

                "request_id":
                    request_id,

                "error":
                    str(exc),
            },
        )


        print(
            f"\nREQUEST FAILED: {request_id}"
        )

        print(exc)
async def persist_coder_artifact(
    request_id: str,
):

    coder_tasks = [
        task
        for task
        in application.task_manager.get_all_tasks()
        if (
            task.assigned_to == "coder"
            and task.status == "completed"
            and task.result
        )
    ]

    if not coder_tasks:
        return None

    task = coder_tasks[-1]

    try:

        project = json.loads(
            task.result
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):

        return None

    if not isinstance(
        project,
        dict,
    ):
        return None

    project_name = project.get(
        "project_name"
    )

    files = project.get(
        "files"
    )

    if (
        not project_name
        or not isinstance(files, list)
    ):
        return None

    artifact = (
        application
        .artifact_manager
        .create_project(
            project_name=project_name,
            files=files,
            request_id=request_id,
        )
    )
    artifact["status"] = project.get("status", "unknown")

    execution = project.get("execution") or {}
    artifact["execution_summary"] = {
        "return_code": execution.get("return_code"),
        "stdout": execution.get("stdout", ""),
        "stderr": execution.get("stderr", ""),
    }
    
    application.event_bus.publish(
        event_type="artifact_created",
        agent="coder",
        data=artifact,
    )

    return artifact
@router.get(
    "/projects/{request_id}"
)
async def get_project(
    request_id: str,
    project: str = Query(...),
):

    try:

        return application.artifact_manager.get_project(
            request_id=request_id,
            project_name=project,
        )

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get(
    "/projects/{request_id}/file"
)
async def get_project_file(
    request_id: str,
    project: str = Query(...),
    path: str = Query(...),
):

    try:

        content = (
            application
            .artifact_manager
            .read_file(
                request_id=request_id,
                project_name=project,
                file_path=path,
            )
        )

        return {
            "request_id": request_id,
            "project_name": project,
            "path": path,
            "content": content,
        }

    except FileNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )