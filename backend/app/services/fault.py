"""故障处置业务规则：状态流转、字段校验、受控可见性与筛选口径都收在这里。

受控可见性约定：
- 当班处理人员（duty）：可见全部记录与处置措施，可执行处置动作并开放派发入口；
- 外协账号（external）：仅可见被共享给自己的记录，操作区收起，共享记录内可见处置措施；
- 其他人员（viewer）：可见记录但看不到处置措施，不能执行任何动作。

所有写路径都先校验再变更：被拦截的提交不会触碰记录，记录保持原样。
身份按请求传入、逐次重算，换班后无需额外失效处理。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.store import store

MODULE = "fault"
REQUIRED_FIELDS = ["故障编号", "故障设备", "故障现象"]
STATUS_ORDER = ["待确认", "已确认", "处置中", "已消除", "待观察"]
ACTION_RULES = {"确认故障": "已确认", "开始处置": "处置中", "确认消除": "已消除"}
NEGATIVE_ACTIONS = []

MEASURE_FIELD = "处置措施"
DISPATCH_ACTION = "派发"

ROLE_DUTY = "duty"
ROLE_EXTERNAL = "external"
ROLE_VIEWER = "viewer"
ROLE_LABELS = {ROLE_DUTY: "当班处理人员", ROLE_EXTERNAL: "外协账号", ROLE_VIEWER: "其他人员"}

# 可派发的外协账号名单；真实项目里来自账号体系，这里先内置样例。
EXTERNAL_ACCOUNTS = ["王外协", "周检修"]


@dataclass(frozen=True)
class Viewer:
    """一次请求的操作者身份。缺省按最低权限的其他人员处理。"""

    name: str = ""
    role: str = ROLE_VIEWER

    @property
    def is_duty(self) -> bool:
        return self.role == ROLE_DUTY

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, ROLE_LABELS[ROLE_VIEWER])


class FaultService:
    def list_entries(
        self,
        *,
        viewer: Viewer,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [row for row in store.rows(MODULE) if self._visible_to(row, viewer)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("故障编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row, viewer) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int, viewer: Viewer) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._present(entry, viewer)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["shared_with"] = []
        rows.append(entry)
        return entry, []

    def dispatch_targets(self, viewer: Viewer) -> list[str]:
        """派发候选名单仅对当班处理人员开放，其他身份拿到空名单。"""
        return list(EXTERNAL_ACCOUNTS) if viewer.is_duty else []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
        viewer: Viewer,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"故障记录 {entry_id} 不存在或已归档"
        if not viewer.is_duty:
            return None, f"当前身份为{viewer.role_label}，故障处置动作仅当班处理人员可执行，记录保持原样"
        if action == DISPATCH_ACTION:
            return self._dispatch(entry, values, viewer)
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于故障处置可执行范围，记录保持原样"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里，记录保持原样"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._present(entry, viewer), f"故障记录已{action}"

    def _dispatch(
        self,
        entry: dict[str, Any],
        values: dict[str, Any],
        viewer: Viewer,
    ) -> tuple[dict[str, Any] | None, str]:
        """派发即建立共享关系：目标外协账号随后可见该记录及其处置措施。"""
        target = str(values.get("target") or "").strip()
        if not target:
            return None, "派发需要指定外协账号，记录保持原样"
        if target not in EXTERNAL_ACCOUNTS:
            return None, f"账号「{target}」不在外协派发名单里，记录保持原样"
        shared_with = entry.setdefault("shared_with", [])
        if target in shared_with:
            return None, f"故障记录已共享给「{target}」，无需重复派发"
        shared_with.append(target)
        return self._present(entry, viewer), f"故障记录已派发给外协账号「{target}」"

    def _visible_to(self, row: dict[str, Any], viewer: Viewer) -> bool:
        """外协账号只能看到被共享的记录，其余身份可见全部记录。"""
        if viewer.role == ROLE_EXTERNAL:
            return viewer.name in row.get("shared_with", [])
        return True

    def _present(self, row: dict[str, Any], viewer: Viewer) -> dict[str, Any]:
        """按身份裁剪单条记录：隐藏处置措施、收起操作区，并附上权限标记。"""
        item = dict(row)
        shared_with = list(row.get("shared_with", []))
        can_view_measures = viewer.is_duty or (
            viewer.role == ROLE_EXTERNAL and viewer.name in shared_with
        )
        if not can_view_measures:
            item.pop(MEASURE_FIELD, None)
        if viewer.is_duty:
            item["shared_with"] = shared_with
        else:
            item.pop("shared_with", None)
        item["_access"] = {
            "role": viewer.role,
            "roleLabel": viewer.role_label,
            "canOperate": viewer.is_duty,
            "canDispatch": viewer.is_duty,
            "canViewMeasures": can_view_measures,
        }
        return item
