"""单屏覆盖。

signboard-06 口径（乙）：强制空屏覆盖必须同时写入失效时刻。
- 缺失效时刻的 force_blank 只落影子覆盖草案，正式覆盖册零增；
- 带失效时刻的 force_blank 同事务落正式覆盖行并持久化 expires_at；
- 升正 force_blank 影子须带未来失效时刻，否则拒绝。
其余覆盖效果沿用原路径（可选失效时刻）。
"""
from __future__ import annotations

import time
from fastapi import APIRouter, Header, HTTPException

from audit_svc import write_audit, write_history
from auth import current_user, require_writer
from db import connect, rows_to_list
from locks import acquire, release
from models import OVERRIDE_EFFECT_LABEL
from policies import assert_override_payload
from validators import (
    format_ts,
    parse_expiry,
    require_effect,
    require_positive_int,
)

router = APIRouter(prefix="/api/overrides", tags=["overrides"])


def _enrich(row: dict) -> dict:
    row["effect_label"] = OVERRIDE_EFFECT_LABEL.get(row.get("effect"), row.get("effect"))
    exp = row.get("expires_at")
    row["expires_label"] = format_ts(exp)
    if exp is not None:
        row["expired"] = exp <= time.time()
    else:
        row["expired"] = False
    return row


def _insert_shadow_draft(conn, screen_id, effect, playlist_id, asset_id, note, expires_at, actor) -> int:
    cur = conn.execute(
        "INSERT INTO override_shadows(screen_id,effect,playlist_id,asset_id,note,status,expires_at,created_at,created_by) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (
            screen_id,
            effect,
            playlist_id,
            asset_id,
            note,
            "open",
            expires_at,
            time.time(),
            actor,
        ),
    )
    return cur.lastrowid


@router.get("")
def list_overrides(authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        rows = rows_to_list(
            conn.execute(
                """
                SELECT o.*, s.code screen_code
                FROM overrides o JOIN screens s ON s.id=o.screen_id
                WHERE o.official=1
                ORDER BY o.id DESC
                """
            ).fetchall()
        )
    return {"items": [_enrich(r) for r in rows]}


@router.get("/shadows")
def list_shadows(authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        rows = rows_to_list(conn.execute("SELECT * FROM override_shadows ORDER BY id DESC").fetchall())
    return {"items": [_enrich(r) for r in rows]}


def _prepare_expiry(effect: str, raw) -> float | None:
    """force_blank 必须带未来失效时刻；其它效果可选。"""
    if effect == "force_blank":
        return parse_expiry(raw, "空屏失效时刻", allow_past=False)
    return parse_expiry(raw, "失效时刻", allow_past=True)


@router.post("/official")
def override_official(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    screen_id = require_positive_int(body.get("screen_id"), "屏幕编号")
    effect = require_effect(body.get("effect"))
    playlist_id = body.get("playlist_id")
    asset_id = body.get("asset_id")
    assert_override_payload(effect, playlist_id, asset_id)
    expires_at = _prepare_expiry(effect, body.get("expires_at"))

    # 乙：强制空屏缺失效时刻只许影子草案，正式覆盖表零改。
    if effect == "force_blank" and expires_at is None:
        with connect() as conn:
            if not conn.execute("SELECT id FROM screens WHERE id=?", (screen_id,)).fetchone():
                raise HTTPException(404, "屏幕不存在")
            sid = _insert_shadow_draft(
                conn,
                screen_id,
                effect,
                playlist_id,
                asset_id,
                body.get("note") or "",
                None,
                user["username"],
            )
            conn.commit()
        write_history("override_shadow", sid, "create", "强制空屏缺失效时刻，转影子草案", user["username"])
        write_audit(user["username"], "override.shadow_draft", {"id": sid, "reason": "blank_without_expiry"})
        return {"id": sid, "path": "shadow", "expires_at": None}

    lock_key = f"override:{screen_id}"
    acquire(lock_key, user["username"])
    try:
        with connect() as conn:
            if not conn.execute("SELECT id FROM screens WHERE id=?", (screen_id,)).fetchone():
                raise HTTPException(404, "屏幕不存在")
            conn.execute(
                "UPDATE overrides SET active=0 WHERE screen_id=? AND official=1",
                (screen_id,),
            )
            cur = conn.execute(
                "INSERT INTO overrides(screen_id,effect,playlist_id,asset_id,note,official,active,expires_at,created_at,created_by) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    screen_id,
                    effect,
                    playlist_id,
                    asset_id,
                    body.get("note") or "",
                    1,
                    1,
                    expires_at,
                    time.time(),
                    user["username"],
                ),
            )
            oid = cur.lastrowid
            conn.commit()
        detail = effect
        if expires_at is not None:
            detail = f"{effect} 到期 {format_ts(expires_at)}"
        write_history("override", oid, "official", detail, user["username"])
        write_audit(
            user["username"],
            "override.official",
            {"id": oid, "expires_at": expires_at},
        )
        return {"id": oid, "path": "official", "expires_at": expires_at}
    finally:
        release(lock_key, user["username"])


@router.post("/shadow")
def override_shadow(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    screen_id = require_positive_int(body.get("screen_id"), "屏幕编号")
    effect = require_effect(body.get("effect"))
    playlist_id = body.get("playlist_id")
    asset_id = body.get("asset_id")
    assert_override_payload(effect, playlist_id, asset_id)
    expires_at = parse_expiry(body.get("expires_at"), "失效时刻", allow_past=True)
    with connect() as conn:
        if not conn.execute("SELECT id FROM screens WHERE id=?", (screen_id,)).fetchone():
            raise HTTPException(404, "屏幕不存在")
        sid = _insert_shadow_draft(
            conn,
            screen_id,
            effect,
            playlist_id,
            asset_id,
            body.get("note") or "",
            expires_at,
            user["username"],
        )
        conn.commit()
    return {"id": sid, "path": "shadow", "expires_at": expires_at}


@router.post("/shadow/{shadow_id}/promote")
def promote_override(shadow_id: int, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    with connect() as conn:
        sh = conn.execute("SELECT * FROM override_shadows WHERE id=?", (shadow_id,)).fetchone()
        if not sh or sh["status"] != "open":
            raise HTTPException(409, "影子不可升正")
        screen_id = sh["screen_id"]
        effect = sh["effect"]
        expires_at = sh["expires_at"] if "expires_at" in sh.keys() else None
    # 乙：空屏影子升正须带未来失效时刻。
    if effect == "force_blank":
        if expires_at is None or expires_at <= time.time():
            raise HTTPException(400, "强制空屏升正须带未来失效时刻")
    lock_key = f"override:{screen_id}"
    acquire(lock_key, user["username"])
    try:
        with connect() as conn:
            sh = conn.execute("SELECT * FROM override_shadows WHERE id=?", (shadow_id,)).fetchone()
            if not sh or sh["status"] != "open":
                raise HTTPException(409, "影子不可升正")
            if sh["effect"] == "force_blank":
                exp_chk = sh["expires_at"] if "expires_at" in sh.keys() else None
                if exp_chk is None or exp_chk <= time.time():
                    raise HTTPException(400, "强制空屏升正须带未来失效时刻")
            conn.execute(
                "UPDATE overrides SET active=0 WHERE screen_id=? AND official=1",
                (screen_id,),
            )
            cur = conn.execute(
                "INSERT INTO overrides(screen_id,effect,playlist_id,asset_id,note,official,active,expires_at,created_at,created_by) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    sh["screen_id"],
                    sh["effect"],
                    sh["playlist_id"],
                    sh["asset_id"],
                    sh["note"],
                    1,
                    1,
                    sh["expires_at"] if "expires_at" in sh.keys() else None,
                    time.time(),
                    user["username"],
                ),
            )
            oid = cur.lastrowid
            conn.execute("UPDATE override_shadows SET status='promoted' WHERE id=?", (shadow_id,))
            conn.commit()
        exp = sh["expires_at"] if "expires_at" in sh.keys() else None
        detail = sh["effect"]
        if exp is not None:
            detail = f"{sh['effect']} 到期 {format_ts(exp)}"
        write_history("override", oid, "promote_shadow", detail, user["username"])
        return {"id": oid, "path": "shadow_promote", "expires_at": exp}
    finally:
        release(lock_key, user["username"])
