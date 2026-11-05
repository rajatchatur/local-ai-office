import json
import os
from fastapi import Query
from backend.agents.boss_agent import _coder_result_context

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
# CONFIGURATION
# ========================================================

def _request_timeout() -> float:

    raw = os.getenv(
        "LOCAL_AI_OFFICE_REQUEST_TIMEOUT",
        "900",
    )

    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid LOCAL_AI_OFFICE_REQUEST_TIMEOUT: {raw!r}"
        ) from exc

    if value <= 0:
        raise RuntimeError(
            "LOCAL_AI_OFFICE_REQUEST_TIMEOUT must be positive."
        )

    return value


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


    application.track_task(

        run_boss(

            request.message,

            request_id,
        ),

        name=f"run_boss:{request_id}",
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


        _coder_result_context.set(None)

        request_timeout = _request_timeout()

        result = await asyncio.wait_for(
            application.boss.run(message),
            timeout=request_timeout,
        )

        coder_result = _coder_result_context.get()
        artifact_input = (
            coder_result if coder_result is not None else result
        )

        artifact = await persist_coder_artifact(
            request_id,
            artifact_input,
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


    except asyncio.TimeoutError:

        error = (
            f"Request timed out after "
            f"{request_timeout} seconds."
        )

        application.event_bus.publish(

            event_type="request_failed",

            agent="boss",

            data={

                "request_id":
                    request_id,

                "error":
                    error,
            },
        )

        print(
            f"\nREQUEST TIMED OUT: {request_id}"
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
    coder_result,
):
    if isinstance(coder_result, str):
        try:
            project = json.loads(coder_result)
        except (json.JSONDecodeError, TypeError):
            return None
    elif isinstance(coder_result, dict):
        project = coder_result
    else:
        return None

    if not isinstance(project, dict):
        return None

    project_name = project.get("project_name")
    files = project.get("files")

    if not project_name or not isinstance(files, list):
        return None
    artifact = application.artifact_manager.create_project(
        project_name=project_name,
        files=files,
        request_id=request_id,
    )
    artifact["status"] = project.get("status", "unknown")

    execution = project.get("execution") or {}
    if not isinstance(execution, dict):
        execution = {}

    artifact["execution_summary"] = {
        "return_code": execution.get("return_code"),
        "stdout": execution.get("stdout", ""),
        "stderr": execution.get("stderr", ""),
        "skipped": bool(execution.get("skipped", False)),
        "reason": execution.get("reason"),
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