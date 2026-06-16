from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.api.errors import conflict, not_found
from app.domain.sessions.schemas import (
    CreateSessionRequest,
    SendMessageRequest,
    SubmitWaitingItemRequest,
)

session_router = APIRouter(prefix="/sessions", tags=["sessions"])

logger = logging.getLogger(__name__)


@session_router.post("", status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> dict:
    service = request.app.state.services.session_service()
    try:
        record = await service.create_session(
            name=body.name,
            workspace_id=body.workspace_id,
            team_id=body.team_id,
        )
        logger.info(
            "route=session.create status=201 session_id=%s team_id=%s workspace_id=%s",
            record.session_id,
            record.team_id,
            record.workspace_id,
        )
    except KeyError as exc:
        detail = str(exc).strip("'")
        if detail == "Team not found":
            logger.info("route=session.create status=404 resource_type=team")
            raise not_found(detail, resource_type="team") from exc
        if detail == "Workspace not found":
            logger.info("route=session.create status=404 resource_type=workspace")
            raise not_found(detail, resource_type="workspace") from exc
        logger.info("route=session.create status=404 resource_type=session")
        raise not_found(detail or "Session dependency not found", resource_type="session") from exc
    return record.model_dump(mode="json")


@session_router.get("")
async def list_sessions(request: Request) -> dict:
    service = request.app.state.services.session_query_service()
    return await service.list_sessions()


@session_router.get("/{session_id}")
async def get_session_detail(session_id: str, request: Request) -> dict:
    service = request.app.state.services.session_query_service()
    await request.app.state.services.runtime_bundle.drain_wakeups_once()
    try:
        payload = await service.get_session_detail(session_id)
        logger.info("route=session.detail status=200 session_id=%s", session_id)
        return payload
    except KeyError as exc:
        logger.info(
            "route=session.detail status=404 resource_type=session session_id=%s",
            session_id,
        )
        raise not_found(
            "Session not found",
            resource_type="session",
            session_id=session_id,
        ) from exc


@session_router.post("/{session_id}/messages", status_code=202)
async def send_message(session_id: str, body: SendMessageRequest, request: Request) -> dict:
    service = request.app.state.services.runtime_service()
    try:
        await service.send_message(session_id, body.content)
        logger.info("route=session.send_message status=202 session_id=%s", session_id)
    except KeyError as exc:
        logger.info(
            "route=session.send_message status=404 resource_type=session session_id=%s",
            session_id,
        )
        raise not_found(
            "Session not found",
            resource_type="session",
            session_id=session_id,
        ) from exc
    except ValueError as exc:
        logger.info(
            "route=session.send_message status=409 resource_type=session session_id=%s",
            session_id,
        )
        raise conflict(str(exc), resource_type="session", session_id=session_id) from exc
    return {"status": "accepted", "session_id": session_id}


@session_router.post("/{session_id}/cancel", status_code=202)
async def cancel_session(session_id: str, request: Request) -> dict:
    service = request.app.state.services.runtime_service()
    try:
        await service.cancel(session_id)
        logger.info("route=session.cancel status=202 session_id=%s", session_id)
    except KeyError as exc:
        logger.info(
            "route=session.cancel status=404 resource_type=session session_id=%s",
            session_id,
        )
        raise not_found(
            "Session not found",
            resource_type="session",
            session_id=session_id,
        ) from exc
    return {"status": "cancelling", "session_id": session_id}


@session_router.post("/{session_id}/waiting/{waiting_id}", status_code=200)
async def submit_waiting_item(
    session_id: str,
    waiting_id: str,
    body: SubmitWaitingItemRequest,
    request: Request,
) -> dict:
    service = request.app.state.services.runtime_service()
    try:
        await service.submit_waiting_item(session_id, waiting_id, body.confirmed)
        logger.info(
            "route=session.waiting.resolve status=200 session_id=%s waiting_id=%s",
            session_id,
            waiting_id,
        )
    except KeyError as exc:
        detail = str(exc).strip("'")
        if detail == waiting_id:
            logger.info(
                (
                    "route=session.waiting.resolve status=404 "
                    "resource_type=waiting_item session_id=%s waiting_id=%s"
                ),
                session_id,
                waiting_id,
            )
            raise not_found(
                "Waiting item not found",
                resource_type="waiting_item",
                session_id=session_id,
                waiting_id=waiting_id,
            ) from exc
        logger.info(
            "route=session.waiting.resolve status=404 resource_type=session session_id=%s",
            session_id,
        )
        raise not_found(
            "Session not found",
            resource_type="session",
            session_id=session_id,
        ) from exc
    return {"status": "resolved", "session_id": session_id, "waiting_id": waiting_id}
