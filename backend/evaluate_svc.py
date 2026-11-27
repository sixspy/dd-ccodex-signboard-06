"""在线求值：某屏此刻应播什么。"""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Header, HTTPException

from auth import current_user
from db import connect, rows_to_list
from validators import format_ts, require_hm, require_positive_int, window_covers

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])


@router.post("/screen")
def evaluate_screen(body: dict, authorization: str | None = Header(default=None)):
    current_user(authorization)
    screen_id = require_positive_int(body.get("screen_id"), "屏幕编号")
    now_hm = require_hm(body.get("now_hm") or datetime.now().strftime("%H:%M"), "求值时刻")
    weekday = str(body.get("weekday") or datetime.now().isoweekday())
    now_ts = datetime.now().timestamp()
    with connect() as conn:
        # 同事务联查覆盖与正式发布，保证优先序账实一致（读快照）。
        conn.execute("BEGIN")
        screen = conn.execute("SELECT * FROM screens WHERE id=?", (screen_id,)).fetchone()
        if not screen:
            raise HTTPException(404, "屏幕不存在")
        # 只认正式、激活且未到期的覆盖；未升正影子永不参与求值。
        # force_blank 必须带有效失效时刻（历史遗留 NULL 空屏不得当永久空屏）。
        ov = conn.execute(
            "SELECT * FROM overrides WHERE screen_id=? AND official=1 AND active=1 "
            "AND (expires_at IS NULL OR expires_at > ?) "
            "AND (effect != 'force_blank' OR expires_at > ?) "
            "ORDER BY id DESC LIMIT 1",
            (screen_id, now_ts, now_ts),
        ).fetchone()
        if ov:
            result = {
                "source": "override",
                "effect": ov["effect"],
                "playlist_id": ov["playlist_id"],
                "asset_id": ov["asset_id"],
                "expires_at": ov["expires_at"],
                "expires_label": format_ts(ov["expires_at"]),
                "now_hm": now_hm,
            }
            if ov["effect"] == "force_blank":
                result["play"] = None
            elif ov["effect"] == "force_asset" and ov["asset_id"]:
                asset = conn.execute("SELECT * FROM assets WHERE id=?", (ov["asset_id"],)).fetchone()
                result["play"] = {"kind": "asset", "asset": dict(asset) if asset else None}
            elif ov["effect"] == "force_playlist" and ov["playlist_id"]:
                items = rows_to_list(
                    conn.execute(
                        "SELECT * FROM playlist_items WHERE playlist_id=? ORDER BY seq",
                        (ov["playlist_id"],),
                    ).fetchall()
                )
                result["play"] = {"kind": "playlist", "items": items}
            return result
        pub = conn.execute(
            "SELECT * FROM publications WHERE screen_id=? AND official=1 AND status='published'",
            (screen_id,),
        ).fetchone()
        if not pub:
            return {"source": "empty", "play": None, "now_hm": now_hm, "reason": "无正式发布"}
        window = conn.execute(
            "SELECT * FROM time_windows WHERE id=?",
            (pub["window_id"],),
        ).fetchone()
        if weekday not in set((window["weekdays"] or "").split(",")):
            return {"source": "publication", "play": None, "reason": "非开放星期", "now_hm": now_hm}
        if not window_covers(window["start_hm"], window["end_hm"], now_hm):
            return {"source": "publication", "play": None, "reason": "不在时段窗内", "now_hm": now_hm}
        items = rows_to_list(
            conn.execute(
                """
                SELECT i.*, a.code asset_code, a.title asset_title, a.kind
                FROM playlist_items i JOIN assets a ON a.id=i.asset_id
                WHERE i.playlist_id=? ORDER BY i.seq
                """,
                (pub["playlist_id"],),
            ).fetchall()
        )
        return {
            "source": "publication",
            "version": pub["version"],
            "playlist_id": pub["playlist_id"],
            "window_id": pub["window_id"],
            "play": {"kind": "playlist", "items": items},
            "now_hm": now_hm,
        }
