"""写入短锁，防并发双写。"""
from __future__ import annotations

import time
from fastapi import APIRouter, Header, HTTPException

from auth import current_user, require_writer
from db import connect

router = APIRouter(prefix="/api/locks", tags=["locks"])


def _write_contention(conn, lock_key: str, holder: str, requester: str) -> None:
    """争用痕独立成行；争用说明不塞进取舍句（note 留空）。"""
    conn.execute(
        "INSERT INTO lock_contention(lock_key,holder,requester,reason,note,created_at) VALUES(?,?,?,?,?,?)",
        (lock_key, holder, requester, "资源锁定中", "", time.time()),
    )


def acquire(lock_key: str, holder: str, ttl_sec: int = 20) -> None:
    now = time.time()
    with connect() as conn:
        # 立即写事务：并发下 check-then-insert 不会两边都通过。
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT holder, expires_at FROM write_locks WHERE lock_key=?",
            (lock_key,),
        ).fetchone()
        if row and row["expires_at"] > now and row["holder"] != holder:
            _write_contention(conn, lock_key, row["holder"], holder)
            conn.commit()
            raise HTTPException(409, f"资源锁定中：{row['holder']}")
        conn.execute(
            "INSERT INTO write_locks(lock_key,holder,expires_at) VALUES(?,?,?) "
            "ON CONFLICT(lock_key) DO UPDATE SET holder=excluded.holder, expires_at=excluded.expires_at",
            (lock_key, holder, now + ttl_sec),
        )
        conn.commit()


def acquire_many(keys: list[str], holder: str, ttl_sec: int = 20) -> list[str]:
    """按序取多把锁；失败时回滚已取锁（失败方仅留争用痕）。"""
    held: list[str] = []
    try:
        for key in keys:
            acquire(key, holder, ttl_sec)
            held.append(key)
    except HTTPException:
        for key in reversed(held):
            release(key, holder)
        raise
    return held


def release(lock_key: str, holder: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM write_locks WHERE lock_key=? AND holder=?",
            (lock_key, holder),
        )
        conn.commit()


@router.post("/acquire")
def api_acquire(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    key = (body.get("lock_key") or "").strip()
    if not key:
        raise HTTPException(400, "缺少 lock_key")
    acquire(key, user["username"], int(body.get("ttl_sec") or 20))
    return {"ok": True, "lock_key": key, "holder": user["username"]}


@router.post("/release")
def api_release(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    key = (body.get("lock_key") or "").strip()
    release(key, user["username"])
    return {"ok": True}
