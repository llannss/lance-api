"""Per-account history and the admin activity log.

- /me/recent        GPUs the signed-in account viewed recently
- /me/comparisons   GPU pairs the signed-in account saved from Compare
- /admin/audit      who changed which GPU and when (admins only)

Account routes always use the account from the login token, never an ID
from the request.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import BaseModel, Field, field_validator

from database import (
    AuditRepository,
    ComparisonRepository,
    DatabaseUnavailableError,
    DuplicateComparisonError,
    GPURepository,
    RecentRepository,
    get_audit_repository,
    get_comparison_repository,
    get_recent_repository,
    get_repository,
)
from models import GPU, MAX_ID
from security import get_current_user, require_admin

logger = logging.getLogger("gpu_api.activity")

GpuId = Path(ge=1, le=MAX_ID, description="The ID of the GPU.")
MAX_COMPARISONS = 50


# ==================== RECENTLY VIEWED ====================

recent_router = APIRouter(prefix="/me/recent", tags=["Recently viewed"])


class RecentList(BaseModel):
    count: int
    gpus: list[GPU]


@recent_router.get("", response_model=RecentList)
def list_recent(
    limit: int = Query(10, ge=1, le=20),
    user: dict = Depends(get_current_user),
    recent: RecentRepository = Depends(get_recent_repository),
    gpus: GPURepository = Depends(get_repository),
):
    """GPUs this account viewed most recently, newest first."""
    ids = recent.list_ids(user["id"], limit)
    by_id = {g["id"]: g for g in gpus.get_many(ids)}
    ordered = [by_id[i] for i in ids if i in by_id]
    return {"count": len(ordered), "gpus": ordered}


@recent_router.post("/{gpu_id}", status_code=204)
def record_view(
    gpu_id: int = GpuId,
    user: dict = Depends(get_current_user),
    recent: RecentRepository = Depends(get_recent_repository),
    gpus: GPURepository = Depends(get_repository),
):
    """Note that this account opened a GPU. Only the newest 20 are kept."""
    if gpus.get(gpu_id) is None:
        raise HTTPException(status_code=404, detail="GPU not found.")
    recent.record(user["id"], gpu_id)
    return Response(status_code=204)


@recent_router.delete("", status_code=204)
def clear_recent(
    user: dict = Depends(get_current_user),
    recent: RecentRepository = Depends(get_recent_repository),
):
    """Forget this account's recently viewed GPUs."""
    recent.clear(user["id"])
    return Response(status_code=204)


# ==================== SAVED COMPARISONS ====================

comparisons_router = APIRouter(prefix="/me/comparisons", tags=["Saved comparisons"])


class ComparisonIn(BaseModel):
    gpu_a_id: int = Field(ge=1, le=MAX_ID)
    gpu_b_id: int = Field(ge=1, le=MAX_ID)
    name: str | None = Field(default=None, max_length=80)

    @field_validator("name")
    @classmethod
    def tidy_name(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class Comparison(BaseModel):
    id: int
    gpu_a_id: int
    gpu_b_id: int
    gpu_a_model: str | None = None
    gpu_b_model: str | None = None
    name: str | None = None
    created_at: str


class ComparisonList(BaseModel):
    count: int
    comparisons: list[Comparison]


def _with_models(rows: list[dict], gpus: GPURepository) -> list[dict]:
    ids = sorted({r["gpu_a_id"] for r in rows} | {r["gpu_b_id"] for r in rows})
    models = {g["id"]: g["model"] for g in gpus.get_many(ids)}
    return [
        {**r, "gpu_a_model": models.get(r["gpu_a_id"]), "gpu_b_model": models.get(r["gpu_b_id"])}
        for r in rows
    ]


@comparisons_router.get("", response_model=ComparisonList)
def list_comparisons(
    user: dict = Depends(get_current_user),
    comparisons: ComparisonRepository = Depends(get_comparison_repository),
    gpus: GPURepository = Depends(get_repository),
):
    """This account's saved comparisons, newest first."""
    rows = _with_models(comparisons.list(user["id"]), gpus)
    return {"count": len(rows), "comparisons": rows}


@comparisons_router.post("", response_model=Comparison, status_code=201)
def save_comparison(
    body: ComparisonIn,
    response: Response,
    user: dict = Depends(get_current_user),
    comparisons: ComparisonRepository = Depends(get_comparison_repository),
    gpus: GPURepository = Depends(get_repository),
):
    """Save a pair of GPUs. Saving the same pair again returns the existing one."""
    if body.gpu_a_id == body.gpu_b_id:
        raise HTTPException(status_code=422, detail="Pick two different GPUs.")
    if len(gpus.get_many([body.gpu_a_id, body.gpu_b_id])) != 2:
        raise HTTPException(status_code=404, detail="GPU not found.")

    existing = comparisons.find_pair(user["id"], body.gpu_a_id, body.gpu_b_id)
    if existing:
        response.status_code = 200
        return _with_models([existing], gpus)[0]

    if len(comparisons.list(user["id"])) >= MAX_COMPARISONS:
        raise HTTPException(status_code=409, detail=f"You can save up to {MAX_COMPARISONS} comparisons.")
    try:
        row = comparisons.create(user["id"], body.gpu_a_id, body.gpu_b_id, body.name)
    except DuplicateComparisonError:   # saved in another tab at the same moment
        row = comparisons.find_pair(user["id"], body.gpu_a_id, body.gpu_b_id)
        response.status_code = 200
    return _with_models([row], gpus)[0]


@comparisons_router.delete("/{comparison_id}", status_code=204)
def delete_comparison(
    comparison_id: int = Path(ge=1, le=MAX_ID),
    user: dict = Depends(get_current_user),
    comparisons: ComparisonRepository = Depends(get_comparison_repository),
):
    """Delete one of this account's saved comparisons."""
    if not comparisons.delete(user["id"], comparison_id):
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return Response(status_code=204)


# ==================== ADMIN ACTIVITY LOG ====================

audit_router = APIRouter(prefix="/admin/audit", tags=["Admin"])

AUDITED_FIELDS = (
    "brand", "manufacturer", "model", "series", "architecture", "vram", "memory_type",
    "cuda_cores", "core_count", "core_type", "memory_bus", "memory_bandwidth_gbps", "power",
    "base_clock", "boost_clock", "recommended_psu", "process_node_nm", "pcie_interface",
    "launch_price_usd", "release_date", "description",
)


def diff(before: dict, after: dict) -> dict:
    """{"field": [old, new]} for every GPU field that changed."""
    changes = {}
    for field in AUDITED_FIELDS:
        old, new = before.get(field), after.get(field)
        if str(old) != str(new):
            changes[field] = [old, new]
    return changes


def record(audit: AuditRepository, admin: dict, action: str, gpu: dict | None, changes: dict | None = None) -> None:
    """Write one log entry. A logging failure never undoes the admin's change."""
    try:
        audit.add({
            "admin_id": admin["id"],
            "admin_email": admin["email"],
            "action": action,
            "gpu_id": gpu.get("id") if gpu else None,
            "gpu_model": gpu.get("model") if gpu else None,
            "changes": changes or None,
        })
    except DatabaseUnavailableError:
        logger.error("Could not write the activity log entry for %s", action)


class AuditEntry(BaseModel):
    id: int
    admin_id: int | None = None
    admin_email: str
    action: str
    gpu_id: int | None = None
    gpu_model: str | None = None
    changes: dict | None = None
    created_at: str


class AuditPage(BaseModel):
    total: int
    entries: list[AuditEntry]


@audit_router.get("", response_model=AuditPage, dependencies=[Depends(require_admin)])
def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    audit: AuditRepository = Depends(get_audit_repository),
):
    """Admin changes to the catalog, newest first."""
    entries, total = audit.list(limit, offset)
    return {"total": total, "entries": entries}
