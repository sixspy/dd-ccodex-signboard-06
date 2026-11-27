"""变更历史。"""
from __future__ import annotations

from fastapi import APIRouter, Header

from auth import current_user
from db import connect, rows_to_list

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(
    limit: int = 100,
    entity_kind: str = "",
    authorization: str | None = Header(default=None),
):
    current_user(authorization)
    limit = max(1, min(limit, 300))
    with connect() as conn:
        # 覆盖类历史联查正式覆盖行，回显到期时刻（跨表账实一致）。
        if entity_kind:
            rows = conn.execute(
                """
                SELECT h.*,
                       o.expires_at AS override_expires_at,
                       o.effect AS override_effect,
                       o.active AS override_active
                FROM change_history h
                LEFT JOIN overrides o
                  ON h.entity_kind='override' AND h.entity_id=o.id
                WHERE h.entity_kind=?
                ORDER BY h.id DESC LIMIT ?
                """,
                (entity_kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.*,
                       o.expires_at AS override_expires_at,
                       o.effect AS override_effect,
                       o.active AS override_active
                FROM change_history h
                LEFT JOIN overrides o
                  ON h.entity_kind='override' AND h.entity_id=o.id
                ORDER BY h.id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return {"items": rows_to_list(rows)}
