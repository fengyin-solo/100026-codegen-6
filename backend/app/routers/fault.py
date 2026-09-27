"""故障处置接口：维护故障记录，覆盖确认故障、开始处置、确认消除与派发共享。

可见性按请求头里的操作者身份逐次重算：换班或切换身份后，下一批请求自然按新的
受控关系出数。缺省或未知身份一律按最低权限的其他人员处理。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.fault import ROLE_LABELS, ROLE_VIEWER, FaultService, Viewer

router = APIRouter(prefix="/api/fault", tags=["故障处置"])

service = FaultService()

LIST_FIELDS = ["故障编号", "故障设备", "故障现象", "发现人员", "发现时间", "严重等级", "处置措施", "故障状态"]
STATUSES = ["待确认", "已确认", "处置中", "已消除", "待观察"]


def current_viewer(x_operator_name: str | None, x_operator_role: str | None) -> Viewer:
    """从请求头还原操作者身份；角色缺失或不在名单里时按其他人员处理。

    姓名按 URL 编码传输（HTTP 头只保证 ASCII 可靠），这里解码还原。
    """
    role = (x_operator_role or "").strip()
    if role not in ROLE_LABELS:
        role = ROLE_VIEWER
    name = unquote((x_operator_name or "").strip())
    return Viewer(name=name, role=role)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按故障编号检索"),
    status: str | None = Query(default=None, description="待确认、已确认、处置中、已消除、待观察"),
    page: int = 1,
    size: int = 20,
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
) -> PageResult[dict]:
    """按故障编号与状态过滤故障处置列表；外协账号只会看到被共享的记录。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    viewer = current_viewer(x_operator_name, x_operator_role)
    items, total = service.list_entries(viewer=viewer, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/dispatch-targets")
def dispatch_targets(
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
) -> dict[str, Any]:
    """派发候选外协账号：仅当班处理人员可见，其他身份拿到空名单。"""
    viewer = current_viewer(x_operator_name, x_operator_role)
    return {"targets": service.dispatch_targets(viewer)}


@router.get("/export")
def export_entries(
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
) -> dict[str, Any]:
    """导出故障处置清单：内容按当前身份的受控可见范围裁剪。"""
    viewer = current_viewer(x_operator_name, x_operator_role)
    items, total = service.list_entries(viewer=viewer, page=1, size=10000)
    return {"module": "fault", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(
    entry_id: int,
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
) -> dict:
    """读取单条故障记录明细；未建立共享关系时处置措施会被隐藏。"""
    viewer = current_viewer(x_operator_name, x_operator_role)
    entry = service.get_entry(entry_id, viewer)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"故障记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条故障记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="故障记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
) -> ActionResult:
    """对单条故障记录执行确认故障、开始处置、确认消除、派发；被拦截时记录保持原样。"""
    viewer = current_viewer(x_operator_name, x_operator_role)
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values, viewer)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
