# 楼宇数字标牌编排（signboard）

**所属领域：应用开发 · 子方向：全栈开发**

全栈产品：素材入库 → 屏幕台账 → 播放清单 → 时段窗 → 发布上屏 → 紧急撤屏 → 单屏覆盖 → 变更历史 → 在线求值。

## 骨架一句话

楼宇屏幕按清单与时段窗编排内容，发布须版本落库才能上屏，紧急撤屏与变更历史同源。

## H3 切口候选（写路径互斥 · 须择一）

1. **发布上屏**：同事务写入正式播放配置并升版本锁旧版，或只写影子发布草案、升正时原子落正式区（正式区升正前零改）。
2. **紧急撤屏**：同事务立即写正式空屏并记变更，或影子撤屏草案确认后原子撤屏。
3. **单屏覆盖**：同事务写正式覆盖条目，或影子覆盖草案升正。

正确性口径只能走甲乙中的一种且两边不得混用。

## signboard-06「强制空屏覆盖须带失效时刻」

单屏覆盖本迭代只做强制空屏时效案，采用乙路径，覆盖正式册零增口径：

- **缺失效时刻**：`POST /api/overrides/official` 遇 `effect=force_blank` 且 `expires_at` 为空，
  整笔转写**影子覆盖草案**（`path=shadow`），正式覆盖册零增；影子空屏缺时刻禁止升正。
- **带未来失效时刻**：同事务落正式覆盖行并持久化 `expires_at`；求值优先空屏，且仅在其未到期时生效。
- **求值**：只认正式、激活且未到期的覆盖；未升正影子永不参与求值（不会被当成永久空屏）。
- **历史**：正式覆盖变更历史含「到期 …」，`/api/history` 联查回显 `override_expires_at`。
- **互斥**：撤屏与覆盖写入争用同一把 `override:<screen_id>` 锁；争用失败方仅写争用痕
  （`/api/audit/contention`），不产生覆盖/撤屏副作用，争用说明独立成行不塞进取舍句。

红测：`tests/feat_blank_ttl_write.py`（甲）、`tests/feat_blank_ttl_eval.py`（乙）、
`tests/feat_blank_ttl_race.py`（争用，标记 `race_blank_ttl`）。

## 一键起环境

```bash
docker compose up -d --build
```

浏览器：http://localhost:11730

- `admin` / `admin123`（管理员）
- `writer` / `writer123`（编排员）
- `viewer` / `viewer123`（只读）

## 本地开发

```powershell
cd projects/18-signboard
$env:PYTHONPATH="backend"
python -m uvicorn app:app --app-dir backend --reload --port 8030
python -m pytest
python scripts/count_loc.py
```

## 空桩

- 远程推屏桥（`remote_push`）
- 媒资中台桥接（`media_bridge`）

接口固定返回 501，题面可点名。
