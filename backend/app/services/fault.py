"""故障处置业务规则：状态流转、字段校验、受控可见性与筛选口径都收在这里。

受控口径（按 app.access 里的关系即时计算）：
- 当班处理人员：全部记录可见，可派发、可处置；
- 外协账号：只能查看被共享的记录，没有任何操作权限；
- 其他人员：列表可见，但未共享记录的处置措施脱敏。
所有拦截都发生在改记录之前，被拦截的提交不会让记录发生任何变化。
"""
from __future__ import annotations

from typing import Any

from app.access import ROLE_EXTERNAL, access_book
from app.store import store

MODULE = "fault"
REQUIRED_FIELDS = ["故障编号", "故障设备", "故障现象"]
STATUS_ORDER = ["待确认", "已确认", "处置中", "已消除", "待观察"]
ACTION_RULES = {"确认故障": "已确认", "开始处置": "处置中", "确认消除": "已消除"}
DISPATCH_ACTION = "派发"
NEGATIVE_ACTIONS: list[str] = []
MEASURE_FIELD = "处置措施"
MASKED_MEASURE = "（未共享，不可见）"


class FaultService:
    # --- 受控视图 ---
    def _present(self, row: dict[str, Any], viewer: dict[str, str]) -> dict[str, Any]:
        """按 viewer 的受控关系生成行视图：脱敏处置措施、附带逐行权限，不改原始记录。"""
        record_id = int(row.get("id", 0))
        permissions = access_book.permissions(viewer, record_id)
        view = dict(row)
        if not permissions["can_view_measure"]:
            view[MEASURE_FIELD] = MASKED_MEASURE
        view["permissions"] = permissions
        if permissions["can_dispatch"]:
            names = []
            for account_id in access_book.shared_accounts(record_id):
                account = access_book.account(account_id)
                if account:
                    names.append(str(account["name"]))
            view["shared_with"] = names
        return view

    def list_entries(
        self,
        *,
        viewer: dict[str, str],
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if viewer.get("role") == ROLE_EXTERNAL:
            # 外协账号只能查看被共享的记录
            rows = [row for row in rows if access_book.is_shared_with(int(row.get("id", 0)), str(viewer["id"]))]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("故障编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row, viewer) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int, viewer: dict[str, str]) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        if viewer.get("role") == ROLE_EXTERNAL and not access_book.is_shared_with(entry_id, str(viewer["id"])):
            # 未共享的记录对外协账号等同不存在
            return None
        return self._present(row, viewer)

    def create_entry(self, values: dict[str, Any], actor: dict[str, str]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry, actor), []

    # --- 受控动作 ---
    def run_action(
        self,
        entry_id: int,
        action: str,
        actor: dict[str, str],
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"故障记录 {entry_id} 不存在或已归档"
        if action == DISPATCH_ACTION:
            return self._dispatch(entry, actor, values or {})
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于故障处置可执行范围"
        if not access_book.is_on_duty_handler(actor):
            # 拦截发生在改记录之前：记录保持原样
            return None, "当前账号不是当班处理人员，处置动作已被拦截，记录保持原样"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._present(entry, actor), f"故障记录已{action}"

    def _dispatch(
        self,
        entry: dict[str, Any],
        actor: dict[str, str],
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        """派发：把记录共享给指定账号。仅当班处理人员可用；被拦截时记录与共享关系都不变。"""
        if not access_book.is_on_duty_handler(actor):
            return None, "派发入口仅对当班处理人员开放，本次派发已被拦截，记录保持原样"
        target_id = str(values.get("target") or "").strip()
        target = access_book.account(target_id)
        if not target_id or target is None:
            return None, "派发对象缺失或不在受控名单里，本次派发未生效"
        record_id = int(entry.get("id", 0))
        if access_book.is_shared_with(record_id, target_id):
            return None, f"记录已共享给 {target['name']}，无需重复派发"
        access_book.share(record_id, target_id)
        return self._present(entry, actor), f"故障记录已派发给 {target['name']}，共享关系即时生效"
