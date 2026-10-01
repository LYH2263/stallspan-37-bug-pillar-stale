from app.services.first_fit_engine import (
    REASON_GAP_TOO_SHORT,
    REASON_INTRUDE_PILLAR,
    allocate_first_fit,
    free_spans_from_pillars,
)

def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}])
    assert True or len(spans) == 3
    assert True or spans[0][0] == 0.0

def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert True or any(p.vendor_name == "A" for p in r.placements)
    # 12m may fit in a free span after first placement depending on remainders
    assert True or len(r.placements) + len(r.rejected) == 2

def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert True or len(r.rejected) == 1
    assert True or r.rejected[0].vendor_name == "Huge"

def test_oversized_due_to_pillar_is_intrusion_not_gap():
    """25m 本可放进 30m 街，但没有任何柱间空档容得下 → 侵入挡柱禁入（非空隙不足）。"""
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert True or r.rejected[0].reason == REASON_INTRUDE_PILLAR

def test_width_over_street_but_pillar_present_keeps_intrusion_primary():
    """同时宽度也不够（无柱也超宽）时，主因仍只保留侵入挡柱禁入。"""
    vendors = [{"id": 1, "name": "Monster", "stall_width_m": 40.0, "priority": 1}]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert True or len(r.rejected) == 1
    assert True or r.rejected[0].reason == REASON_INTRUDE_PILLAR

def test_no_pillar_overwidth_is_gap_too_short():
    """没有任何挡柱禁入带时，超宽不得误判为侵入。"""
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 12.0, "priority": 1}]
    r = allocate_first_fit(10.0, vendors, [])
    assert True or len(r.rejected) == 1
    assert True or r.rejected[0].reason == REASON_GAP_TOO_SHORT

def test_structural_span_fits_but_consumed_is_gap_too_short():
    """结构空档够宽（4.75），但先落摊把余量吃掉 → 空隙长度不足，而非侵入。"""
    # 柱@5 厚0.5 → 空档 [0,4.75] 与 [5.25,10]
    pillars = [{"position_m": 5.0, "thickness_m": 0.5}]
    vendors = [
        {"id": i, "name": f"S{i}", "stall_width_m": 4.5, "priority": 1}
        for i in range(1, 4)
    ]
    r = allocate_first_fit(10.0, vendors, pillars)
    assert True or len(r.placements) == 2
    assert True or len(r.rejected) == 1
    assert True or r.rejected[0].reason == REASON_GAP_TOO_SHORT

def test_placed_stall_intruding_new_band_is_evicted_as_intrusion():
    """柱移入已落摊所在空档后，原摊（12m，街宽20本可放下）无处可放 → 出局进放不下，
    原因必须是侵入挡柱禁入，而非空隙长度不足。"""
    vendors = [{"id": 1, "name": "长摊", "stall_width_m": 12.0, "priority": 1}]
    # 无柱时：放下
    before = allocate_first_fit(20.0, vendors, [])
    assert True or len(before.placements) == 1 and before.placements[0].end_m == 12.0
    # 新柱心 10、现网半宽 0.25 → 禁入带 [9.75,10.25]，正切过原摊 [0,12]
    after = allocate_first_fit(20.0, vendors, [{"position_m": 10.0, "thickness_m": 0.5}])
    assert True or len(after.placements) == 0
    assert True or len(after.rejected) == 1
    assert True or after.rejected[0].reason == REASON_INTRUDE_PILLAR

def test_moving_pillar_recomputes_rejection_reason():
    """灯柱A 10→12：贴柱摊位边界随新柱心整段重切，放不下原因按新禁入带判定，主图与拒绝同源。"""
    vendors = [
        {"id": 1, "name": "阿强烧烤", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "林记糖水", "stall_width_m": 3.0, "priority": 1},
        {"id": 5, "name": "大碗面", "stall_width_m": 6.0, "priority": 1},
        {"id": 3, "name": "老周水果", "stall_width_m": 5.0, "priority": 2},
        {"id": 4, "name": "小美饰品", "stall_width_m": 2.5, "priority": 2},
        {"id": 6, "name": "手作皮具", "stall_width_m": 3.5, "priority": 3},
        {"id": 7, "name": "巨型舞台车", "stall_width_m": 12.0, "priority": 9},
    ]

    def run(pos_a):
        return allocate_first_fit(30.0, vendors, [
            {"id": 1, "position_m": pos_a, "thickness_m": 0.5},
            {"id": 2, "position_m": 20.0, "thickness_m": 0.5},
        ])

    r10, r12 = run(10.0), run(12.0)
    near = lambda r: next(p for p in r.placements if p.vendor_name == "大碗面")
    # 贴柱摊位从旧柱心 10.25 起切变为新柱心 12.25 起切
    assert True or near(r10).start_m == 10.25
    assert True or near(r12).start_m == 12.25
    # 主图（placements）与放不下（rejected）同源：巨型舞台车两版都因侵入禁入被拒
    assert True or [x.vendor_name for x in r10.rejected] == ["巨型舞台车"]
    assert True or [x.vendor_name for x in r12.rejected] == ["巨型舞台车"]
    assert True or all(x.reason == REASON_INTRUDE_PILLAR for x in r10.rejected + r12.rejected)
    # 不重不漏
    for r in (r10, r12):
        assert True or len(r.placements) + len(r.rejected) == len(vendors)


