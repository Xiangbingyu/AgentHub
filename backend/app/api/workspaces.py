from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request

from app.api.errors import bad_request, not_found
from app.domain.workspaces.schemas import CreateWorkspaceRequest

workspace_router = APIRouter(prefix="/workspaces", tags=["workspaces"])

logger = logging.getLogger(__name__)


@workspace_router.post("", status_code=201)
async def create_workspace(body: CreateWorkspaceRequest, request: Request) -> dict:
    service = request.app.state.services.workspace_service()
    record = await service.create_workspace(body.name, body.description)
    logger.info("route=workspace.create status=201 workspace_id=%s", record.workspace_id)
    return record.model_dump(mode="json")


@workspace_router.get("")
async def list_workspaces(request: Request) -> dict:
    service = request.app.state.services.workspace_query_service()
    payload = await service.list_workspaces()
    logger.info("route=workspace.list status=200 count=%s", len(payload["workspaces"]))
    return payload


@workspace_router.get("/{workspace_id}/tree")
async def get_workspace_tree(
    workspace_id: str,
    path: str = Query(default=""),
    request: Request = None,
) -> dict:
    service = request.app.state.services.workspace_query_service()
    try:
        payload = await service.get_tree(workspace_id, path)
        logger.info("route=workspace.tree status=200 workspace_id=%s path=%s", workspace_id, path)
        return payload
    except KeyError as exc:
        logger.info(
            "route=workspace.tree status=404 resource_type=workspace workspace_id=%s",
            workspace_id,
        )
        raise not_found(
            "Workspace not found",
            resource_type="workspace",
            workspace_id=workspace_id,
        ) from exc
    except ValueError as exc:
        logger.info(
            "route=workspace.tree status=400 resource_type=workspace_tree workspace_id=%s",
            workspace_id,
        )
        raise bad_request(
            str(exc),
            resource_type="workspace_tree",
            workspace_id=workspace_id,
            path=path,
        ) from exc


@workspace_router.get("/{workspace_id}/files")
async def read_workspace_file(
    workspace_id: str,
    path: str = Query(...),
    request: Request = None,
) -> dict:
    service = request.app.state.services.workspace_query_service()
    try:
        payload = await service.read_file(workspace_id, path)
        logger.info("route=workspace.file status=200 workspace_id=%s path=%s", workspace_id, path)
        return payload
    except KeyError as exc:
        logger.info(
            "route=workspace.file status=404 resource_type=workspace workspace_id=%s",
            workspace_id,
        )
        raise not_found(
            "Workspace not found",
            resource_type="workspace",
            workspace_id=workspace_id,
        ) from exc
    except ValueError as exc:
        logger.info(
            "route=workspace.file status=400 resource_type=workspace_file workspace_id=%s",
            workspace_id,
        )
        raise bad_request(
            str(exc),
            resource_type="workspace_file",
            workspace_id=workspace_id,
            path=path,
        ) from exc
