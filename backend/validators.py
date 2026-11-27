"""字段与业务校验。"""
from __future__ import annotations

import re
import time
from datetime import datetime
from fastapi import HTTPException

from models import (
    ASSET_KINDS,
    ASSET_STATUS,
    OVERRIDE_EFFECT,
    PLAYLIST_STATUS,
    SCREEN_STATUS,
    TRANSITION_KINDS,
    WINDOW_STATUS,
    ZONE_TYPES,
)

CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
HM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def require_code(code: str, label: str = "编码") -> str:
    code = (code or "").strip()
    if not CODE_RE.match(code):
        raise HTTPException(400, f"{label}须为小写字母开头的短码")
    return code


def require_title(title: str, label: str = "标题") -> str:
    title = (title or "").strip()
    if len(title) < 2 or len(title) > 80:
        raise HTTPException(400, f"{label}长度须在 2～80")
    return title


def require_kind(kind: str) -> str:
    if kind not in ASSET_KINDS:
        raise HTTPException(400, "素材种类不合法")
    return kind


def require_asset_status(status: str) -> str:
    if status not in ASSET_STATUS:
        raise HTTPException(400, "素材状态不合法")
    return status


def require_screen_status(status: str) -> str:
    if status not in SCREEN_STATUS:
        raise HTTPException(400, "屏幕状态不合法")
    return status


def require_playlist_status(status: str) -> str:
    if status not in PLAYLIST_STATUS:
        raise HTTPException(400, "清单状态不合法")
    return status


def require_window_status(status: str) -> str:
    if status not in WINDOW_STATUS:
        raise HTTPException(400, "时段窗状态不合法")
    return status


def require_zone_type(zone_type: str) -> str:
    if zone_type not in ZONE_TYPES:
        raise HTTPException(400, "分区类型不合法")
    return zone_type


def require_transition(transition: str) -> str:
    if transition not in TRANSITION_KINDS:
        raise HTTPException(400, "过渡方式不合法")
    return transition


def require_effect(effect: str) -> str:
    if effect not in OVERRIDE_EFFECT:
        raise HTTPException(400, "覆盖效果不合法")
    return effect


def require_hm(hm: str, label: str) -> str:
    hm = (hm or "").strip()
    if not HM_RE.match(hm):
        raise HTTPException(400, f"{label}须为 HH:MM")
    return hm


def require_weekdays(weekdays: str) -> str:
    weekdays = (weekdays or "").strip()
    parts = [p for p in weekdays.split(",") if p]
    if not parts:
        raise HTTPException(400, "星期集合不能为空")
    for p in parts:
        if p not in {"1", "2", "3", "4", "5", "6", "7"}:
            raise HTTPException(400, "星期须为 1～7")
    return ",".join(sorted(set(parts), key=int))


def require_positive_int(value, label: str, lo: int = 1, hi: int = 86400) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{label}须为整数")
    if n < lo or n > hi:
        raise HTTPException(400, f"{label}超出范围")
    return n


def hm_to_min(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


_DT_FORMATS = (
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)


def parse_expiry(value, label: str = "失效时刻", *, allow_past: bool = False) -> float | None:
    """解析失效时刻：空值返回 None；接受 epoch 秒或本地 ISO 时刻。

    非空且不晚于当前时刻（除非 allow_past）一律拒写，避免「永久空屏」。
    """
    if value in (None, ""):
        return None
    ts: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        ts = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            ts = float(text)
        except ValueError:
            for fmt in _DT_FORMATS:
                try:
                    ts = datetime.strptime(text, fmt).timestamp()
                    break
                except ValueError:
                    continue
    if ts is None:
        raise HTTPException(400, f"{label}格式不合法")
    if not allow_past and ts <= time.time():
        raise HTTPException(400, f"{label}须晚于当前时刻")
    return ts


def format_ts(ts: float | None) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def window_covers(start_hm: str, end_hm: str, now_hm: str) -> bool:
    s, e, n = hm_to_min(start_hm), hm_to_min(end_hm), hm_to_min(now_hm)
    if s == e:
        return True
    if s < e:
        return s <= n < e
    return n >= s or n < e
