"""受控访问关系：账号角色、当班班次与故障记录共享关系。

故障处置模块的可见内容与动作权限都按这里的关系即时计算：
- 当班处理人员：可见全部记录与处置措施，拥有派发入口和处置动作；
- 外协账号：只能查看被共享的记录，操作区收起；
- 其他人员：能打开列表，但未共享记录的处置措施会被脱敏。

换班只改当班表，共享关系不因换班失效；下一次读取按新的受控关系重算。
"""
from __future__ import annotations

from typing import Any

ROLE_HANDLER = "handler"    # 处理人员，是否当班看班次表
ROLE_EXTERNAL = "external"  # 外协账号
ROLE_VIEWER = "viewer"      # 其他人员

ROLE_LABELS = {
    ROLE_HANDLER: "处理人员",
    ROLE_EXTERNAL: "外协账号",
    ROLE_VIEWER: "普通人员",
}

ACCOUNTS: list[dict[str, str]] = [
    {"id": "op_chen", "name": "陈当班", "role": ROLE_HANDLER},
    {"id": "op_li", "name": "李接班", "role": ROLE_HANDLER},
    {"id": "ext_wang", "name": "王外协", "role": ROLE_EXTERNAL},
    {"id": "ext_zhao", "name": "赵外协", "role": ROLE_EXTERNAL},
    {"id": "view_sun", "name": "孙巡检", "role": ROLE_VIEWER},
]

# 每个班次对应的当班处理人员：换班后派发入口与操作权限随之移交
SHIFT_PLAN: list[dict[str, Any]] = [
    {"label": "白班 08:00-20:00", "duty": ["op_chen"]},
    {"label": "夜班 20:00-08:00", "duty": ["op_li"]},
]

# 演示用的既有共享关系：故障记录 2 已共享给王外协
SEED_SHARES: dict[int, set[str]] = {2: {"ext_wang"}}


class AccessBook:
    """当班表 + 共享关系簿：所有受控判断的单一数据源。"""

    def __init__(self) -> None:
        self._shift_index = 0
        self._shares: dict[int, set[str]] = {rid: set(ids) for rid, ids in SEED_SHARES.items()}

    # --- 账号 ---
    def account(self, account_id: str) -> dict[str, str] | None:
        for item in ACCOUNTS:
            if item["id"] == account_id:
                return dict(item)
        return None

    def accounts(self) -> list[dict[str, str]]:
        return [dict(item) for item in ACCOUNTS]

    def role_label(self, role: str) -> str:
        return ROLE_LABELS.get(role, role)

    # --- 班次 ---
    def shift_label(self) -> str:
        return str(SHIFT_PLAN[self._shift_index]["label"])

    def duty_handlers(self) -> list[str]:
        return list(SHIFT_PLAN[self._shift_index]["duty"])

    def rotate_shift(self) -> str:
        """换班：当班关系移交到下一班，返回新班次标签。"""
        self._shift_index = (self._shift_index + 1) % len(SHIFT_PLAN)
        return self.shift_label()

    def on_duty(self, account_id: str) -> bool:
        return account_id in SHIFT_PLAN[self._shift_index]["duty"]

    # --- 共享关系 ---
    def share(self, record_id: int, account_id: str) -> None:
        self._shares.setdefault(record_id, set()).add(account_id)

    def shared_accounts(self, record_id: int) -> list[str]:
        return sorted(self._shares.get(record_id, set()))

    def is_shared_with(self, record_id: int, account_id: str) -> bool:
        return account_id in self._shares.get(record_id, set())

    # --- 权限计算 ---
    def is_on_duty_handler(self, account: dict[str, str]) -> bool:
        return account.get("role") == ROLE_HANDLER and self.on_duty(str(account.get("id", "")))

    def permissions(self, account: dict[str, str], record_id: int) -> dict[str, bool]:
        """逐行计算受控关系：能否看处置措施、能否派发、能否处置。"""
        duty_handler = self.is_on_duty_handler(account)
        shared = self.is_shared_with(record_id, str(account.get("id", "")))
        return {
            "can_view_measure": duty_handler or shared,
            "can_dispatch": duty_handler,
            "can_operate": duty_handler,
        }

    def session_view(self, account: dict[str, str]) -> dict[str, Any]:
        """给前端的会话快照：账号、角色、当班状态与班次。"""
        account_id = str(account.get("id", ""))
        return {
            "account": {
                "id": account_id,
                "name": account.get("name", ""),
                "role": account.get("role", ""),
                "role_label": self.role_label(str(account.get("role", ""))),
            },
            "on_duty": self.on_duty(account_id),
            "shift_label": self.shift_label(),
            "duty_handlers": self.duty_handlers(),
        }


access_book = AccessBook()
