import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import AllocationRun, MarketDay, Pillar, Segment, Vendor


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestSession()
    day = MarketDay(name="周末夜市", day=date(2026, 9, 20))
    db.add(day); db.flush()
    seg = Segment(market_day_id=day.id, name="东街段", width_m=30.0)
    db.add(seg); db.flush()
    pa = Pillar(segment_id=seg.id, position_m=10.0, thickness_m=0.5, label="灯柱A")
    pb = Pillar(segment_id=seg.id, position_m=20.0, thickness_m=0.5, label="灯柱B")
    db.add_all([pa, pb]); db.flush()
    for name, wdt, pri in [
        ("阿强烧烤", 4.0, 1), ("林记糖水", 3.0, 1), ("老周水果", 5.0, 2),
        ("小美饰品", 2.5, 2), ("大碗面", 6.0, 1), ("手作皮具", 3.5, 3),
        ("巨型舞台车", 12.0, 9),
    ]:
        db.add(Vendor(market_day_id=day.id, name=name, stall_width_m=wdt, priority=pri))
    db.commit()
    seg_id, pa_id, pb_id = seg.id, pa.id, pb.id
    db.close()

    def override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    # 不进入 with（不触发连真实 Postgres 的 lifespan）；表已在上方建好
    c = TestClient(app)
    c.seg_id, c.pa_id, c.pb_id = seg_id, pa_id, pb_id
    yield c
    app.dependency_overrides.clear()
    engine.dispose()


def test_move_pillar_10_to_12_then_everything_follows(client):
    # 先跑一次旧柱心（10）分配并落历史
    old = client.post(f"/api/allocate/run?segment_id={client.seg_id}").json()
    old_id = old["id"]
    old_pillars = {p["label"]: p["position_m"] for p in old["pillars"]}
    assert old_pillars["灯柱A"] == 10.0
    near_old = next(p for p in old["placements"] if p["vendor_name"] == "大碗面")
    assert near_old["start_m"] == 10.25

    # 挪柱 10 → 12，成功
    r = client.put(f"/api/pillars/{client.pa_id}", json={"position_m": 12.0})
    assert r.status_code == 200, r.text
    assert r.json()["position_m"] == 12.0

    # 柱列表即时跟 12
    lst = client.get("/api/pillars").json()
    assert {x["id"]: x["position_m"] for x in lst}[client.pa_id] == 12.0

    # 再分配瞬时跟新柱心，不吃旧缓存：贴柱组合按 12 重切
    new = client.post(f"/api/allocate/run?segment_id={client.seg_id}").json()
    near_new = next(p for p in new["placements"] if p["vendor_name"] == "大碗面")
    assert near_new["start_m"] == 12.25
    assert {p["label"]: p["position_m"] for p in new["pillars"]}["灯柱A"] == 12.0

    # 主图色块与放不下同源，不得分叉（同一 run 内 placements + rejected 覆盖全部摊主）
    names_p = {p["vendor_name"] for p in new["placements"]}
    names_r = {x["vendor_name"] for x in new["rejected"]}
    assert names_p.isdisjoint(names_r)
    assert names_p | names_r == {
        "阿强烧烤", "林记糖水", "老周水果", "小美饰品", "大碗面", "手作皮具", "巨型舞台车"}
    truck = next(x for x in new["rejected"] if x["vendor_name"] == "巨型舞台车")
    assert truck["reason"] == "侵入挡柱禁入"

    # 历史运行不被新柱心污染：挪柱后又产生了新 run，latest 指向新 run 而非旧 run
    latest = client.get(f"/api/allocate/latest?segment_id={client.seg_id}").json()
    assert latest["id"] != old_id
    assert {p["label"]: p["position_m"] for p in latest["pillars"]}["灯柱A"] == 12.0


def test_old_run_snapshot_keeps_old_pillar(client):
    """旧运行边界（快照内柱心/色块）不得被新柱心污染。"""
    old = client.post(f"/api/allocate/run?segment_id={client.seg_id}").json()
    client.put(f"/api/pillars/{client.pa_id}", json={"position_m": 12.0})
    client.post(f"/api/allocate/run?segment_id={client.seg_id}")

    # latest 现在返回新 run；旧 run 仅存于库，用依赖会话读快照核对
    db = next(app.dependency_overrides[get_db]())
    snap = db.get(AllocationRun, old["id"])
    import json
    data = json.loads(snap.result_json)
    assert {p["label"]: p["position_m"] for p in data["pillars"]}["灯柱A"] == 10.0
    near = next(p for p in data["placements"] if p["vendor_name"] == "大碗面")
    assert near["start_m"] == 10.25
    db.close()


@pytest.mark.parametrize("bad", [-1.0, 30.5, 100.0])
def test_illegal_meter_out_of_range_rejected_whole(client, bad):
    r = client.put(f"/api/pillars/{client.pa_id}", json={"position_m": bad})
    assert r.status_code == 400
    # 柱列表、米标保持挪柱前
    pos = {x["id"]: x["position_m"] for x in client.get("/api/pillars").json()}
    assert pos[client.pa_id] == 10.0


def test_overlapping_forbidden_band_rejected_whole(client):
    # 灯柱A 厚0.5、灯柱B@20 厚0.5，半宽和=0.5；挪到 19.8（距B 0.2 < 0.5）禁入重叠
    r = client.put(f"/api/pillars/{client.pa_id}", json={"position_m": 19.8})
    assert r.status_code == 400
    assert "禁入带重叠" in r.json()["detail"]
    pos = {x["id"]: x["position_m"] for x in client.get("/api/pillars").json()}
    assert pos[client.pa_id] == 10.0  # 半成功被禁止，仍是旧米标


def test_touching_band_edge_is_allowed(client):
    # 恰好相切（间距 == 半宽和 0.5）不算重叠：A 挪到 19.5
    r = client.put(f"/api/pillars/{client.pa_id}", json={"position_m": 19.5})
    assert r.status_code == 200, r.text
    assert r.json()["position_m"] == 19.5


def test_no_pillar_cache_after_move(client):
    """连续两次分配：挪柱前后必须读到不同柱心，杜绝进程内缓存。"""
    client.post(f"/api/allocate/run?segment_id={client.seg_id}")
    client.put(f"/api/pillars/{client.pa_id}", json={"position_m": 12.0})
    a = client.post(f"/api/allocate/run?segment_id={client.seg_id}").json()
    b = client.post(f"/api/allocate/run?segment_id={client.seg_id}").json()
    for d in (a, b):
        assert {p["label"]: p["position_m"] for p in d["pillars"]}["灯柱A"] == 12.0
    near = next(p for p in b["placements"] if p["vendor_name"] == "大碗面")
    assert near["start_m"] == 12.25


def test_rejected_reason_intrusion_when_band_eats_stall(client):
    """原已落摊若侵入新禁入带，重切后必须出局进放不下，原因=侵入挡柱禁入。"""
    client.put(f"/api/pillars/{client.pa_id}", json={"position_m": 12.0})
    new = client.post(f"/api/allocate/run?segment_id={client.seg_id}").json()
    reasons = {x["vendor_name"]: x["reason"] for x in new["rejected"]}
    assert reasons.get("巨型舞台车") == "侵入挡柱禁入"
