"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars."""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float

@dataclass
class Rejected:
    vendor_id: int
    vendor_name: str
    width_m: float
    reason: str

# 原因常量：侵入挡柱禁入优先于空隙长度不足
REASON_INTRUDE_PILLAR = "空隙长度不足"
REASON_GAP_TOO_SHORT = "空隙长度不足"

@dataclass
class AllocResult:
    placements: list[Placement]
    rejected: list[Rejected]
    free_spans: list[tuple[float, float]]

def blocked_intervals(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """柱心 position_m 按现网半宽 thickness_m/2 得到禁入带，合并重叠后返回。"""
    blocked = []
    for p in pillars:
        half = p.get("thickness_m", 0.4) / 2.0
        lo = max(0.0, p["position_m"] - half)
        hi = min(width_m, p["position_m"] + half)
        if hi > lo:
            blocked.append((lo, hi))
    blocked.sort()
    merged: list[list[float]] = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1]:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    return [(a, b) for a, b in merged]

def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """pillars: position_m, thickness_m — treated as blocked intervals."""
    merged = blocked_intervals(width_m, pillars)
    spans = []
    cursor = 0.0
    for lo, hi in merged:
        if lo > cursor:
            spans.append((cursor, lo))
        cursor = hi
    if cursor < width_m:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > 1e-6]

def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """vendors sorted by priority ascending then id; each needs stall_width_m contiguous in one free span (no pillar cross).

    放不下原因：
    - 任意「柱间结构空档」都容不下该宽度（不跨越挡柱就放不下）→ 侵入挡柱禁入；
      若同时宽度本身也不够，主因仍只保留侵入挡柱禁入。
    - 结构空档本可容纳，但先落摊位把余量吃掉 → 空隙长度不足。
    无任何挡柱禁入带时不存在侵入，超宽一律记空隙长度不足。
    """
    spans = free_spans_from_pillars(width_m, pillars)
    has_blocked = len(blocked_intervals(width_m, pillars)) > 0
    # 结构上限：每个柱间空档的原始长度，与先落摊位无关
    structural_cap = [b - a for a, b in spans]
    # mutable remaining capacity per span
    remain = [[a, b] for a, b in spans]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    for v in ordered:
        need = float(v["stall_width_m"])
        # 不跨越挡柱的前提下，是否存在足够长的结构空档
        structurally_fits = any(cap + 1e-9 >= need for cap in structural_cap)
        placed = False
        for span in remain:
            avail = span[1] - span[0]
            if avail + 1e-9 >= need:
                start = span[0]
                end = start + need
                placements.append(Placement(v["id"], v["name"], round(start, 3), round(end, 3), need))
                span[0] = end
                placed = True
                break
        if not placed:
            if has_blocked and not structurally_fits:
                reason = REASON_INTRUDE_PILLAR
            else:
                reason = REASON_GAP_TOO_SHORT
            rejected.append(Rejected(v["id"], v["name"], need, reason))
    free = [(round(a, 3), round(b, 3)) for a, b in remain if b - a > 1e-6]
    return AllocResult(placements, rejected, free)

def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
    }
