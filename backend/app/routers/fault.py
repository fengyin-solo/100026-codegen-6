"""故障处置接口：维护故障记录，覆盖派发共享、确认故障、开始处置、确认消除等动作。

所有接口都要求 X-Account-Id 请求头：可见内容与可执行动作按受控关系逐行计算，
被拦截的提交返回 ok=False 且不改动记录。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.routers.access import resolve_account
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.fault import FaultService

router = APIRouter(prefix="/api/fault", tags=["故障处置"])

service = FaultService()

LIST_FIELDS = ["故障编号", "故障设备", "故障现象", "发现人员", "发现时间", "严重等级", "处置措施", "故障状态"]
STATUSES = ["待确认", "已确认", "处置中", "已消除", "待观察"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按故障编号检索"),
    status: str | None = Query(default=None, description="待确认、已确认、处置中、已消除、待观察"),
    page: int = 1,
    size: int = 20,
    x_account_id: str | None = Header(default=None),
) -> PageResult[dict]:
    """按受控关系返回故障处置列表：外协账号只见被共享的记录，未共享记录的处置措施脱敏。"""
    viewer = resolve_account(x_account_id)
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(viewer=viewer, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(x_account_id: str | None = Header(default=None)) -> dict[str, Any]:
    """导出故障处置清单：按当前账号的受控关系返回可见数据，不绕过脱敏。"""
    viewer = resolve_account(x_account_id)
    items, total = service.list_entries(viewer=viewer, page=1, size=10000)
    return {"module": "fault", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int, x_account_id: str | None = Header(default=None)) -> dict:
    """读取单条故障记录明细；不存在或未共享时给出可读的错误说明。"""
    viewer = resolve_account(x_account_id)
    entry = service.get_entry(entry_id, viewer)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"故障记录 {entry_id} 不存在、已归档或未共享给当前账号")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, x_account_id: str | None = Header(default=None)) -> ActionResult:
    """登记一条故障记录，缺字段时说明原因而不是静默丢弃。"""
    actor = resolve_account(x_account_id)
    entry, missing = service.create_entry(payload.values, actor)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="故障记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload, x_account_id: str | None = Header(default=None)) -> ActionResult:
    """对单条故障记录执行派发、确认故障、开始处置、确认消除；被拦截时说明原因且记录保持原样。"""
    actor = resolve_account(x_account_id)
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, actor, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
