"""受控关系接口：账号清单、当前会话快照与换班。

前端登录态用 X-Account-Id 请求头标识；换班后各页面按返回的新关系重算可见内容。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.access import access_book

router = APIRouter(prefix="/api/access", tags=["受控关系"])


def resolve_account(account_id: str | None) -> dict[str, str]:
    """按请求头解析账号；缺失或未知时拒绝，不让请求匿名落到受控数据上。"""
    if not account_id:
        raise HTTPException(status_code=401, detail="缺少 X-Account-Id 请求头，无法确认操作人身份")
    account = access_book.account(account_id)
    if account is None:
        raise HTTPException(status_code=401, detail=f"账号 {account_id} 不在受控名单里")
    return account


@router.get("/accounts", response_model=dict)
def list_accounts() -> dict:
    """账号清单：给前端的身份切换入口用，附带角色说明。"""
    items = [
        {**item, "role_label": access_book.role_label(item["role"])}
        for item in access_book.accounts()
    ]
    return {"items": items, "shift_label": access_book.shift_label()}


@router.get("/session", response_model=dict)
def current_session(x_account_id: str | None = Header(default=None)) -> dict:
    """当前会话快照：账号、当班状态、班次，以及可派发（可共享）的对象清单。"""
    account = resolve_account(x_account_id)
    view = access_book.session_view(account)
    view["shareable"] = [
        {**item, "role_label": access_book.role_label(item["role"])}
        for item in access_book.accounts()
        if item["id"] != account["id"]
    ]
    return view


@router.post("/shift/rotate", response_model=dict)
def rotate_shift(x_account_id: str | None = Header(default=None)) -> dict:
    """换班：当班关系移交下一班，返回新的班次与当班人员，各页面据此重算。"""
    resolve_account(x_account_id)
    label = access_book.rotate_shift()
    duty = access_book.duty_handlers()
    names = [access_book.account(item)["name"] for item in duty if access_book.account(item)]
    return {
        "ok": True,
        "message": f"已换班：{label}，当班处理人员 {('、'.join(names)) or '暂无'}",
        "shift_label": label,
        "duty_handlers": duty,
    }
