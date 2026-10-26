import json
import sys
from collections import Counter


def percentile_ranks(values):
    ordered = sorted((value, code) for code, value in values.items())
    ranks = {}
    index = 0
    count = len(ordered)
    while index < count:
        end = index + 1
        while end < count and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        percentile = 0.0 if count == 1 else (average_rank - 1) / (count - 1)
        for _, code in ordered[index:end]:
            ranks[code] = percentile
        index = end
    return ranks


def run(request):
    params = request.get("params") or {}
    top_n = params.get("top_n", 20)
    max_pe = params.get("max_pe")
    max_pb = params.get("max_pb")
    stocks = {row.get("ts_code"): row for row in request["data"]["stocks"] if row.get("ts_code")}
    rows = request["data"]["daily_basic"]
    valid = {}
    exclusions = Counter()
    for row in rows:
        code = row.get("ts_code")
        if not code:
            exclusions["missing_code"] += 1
            continue
        reasons = []
        pe, pb = row.get("pe_ttm"), row.get("pb")
        if pe is None:
            reasons.append("missing_pe")
        elif pe <= 0:
            reasons.append("invalid_pe")
        elif max_pe is not None and pe > max_pe:
            reasons.append("over_max_pe")
        if pb is None:
            reasons.append("missing_pb")
        elif pb <= 0:
            reasons.append("invalid_pb")
        elif max_pb is not None and pb > max_pb:
            reasons.append("over_max_pb")
        if reasons:
            exclusions.update(reasons)
        else:
            valid[code] = (row, pe, pb)

    pe_rank = percentile_ranks({code: item[1] for code, item in valid.items()})
    pb_rank = percentile_ranks({code: item[2] for code, item in valid.items()})
    ranked = []
    for code, (row, pe, pb) in valid.items():
        stock = stocks.get(code, {})
        ranked.append({
            "rank": 0, "ts_code": code, "name": stock.get("name"),
            "industry": stock.get("industry"), "trade_date": row.get("trade_date"),
            "pe_ttm": pe, "pb": pb,
            "valuation_score": round((pe_rank[code] + pb_rank[code]) / 2, 8),
            "source": row.get("source"), "source_record_id": row.get("record_id"),
        })
    ranked.sort(key=lambda item: (item["valuation_score"], item["ts_code"]))
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    meta = request.get("meta", {})
    sources = list(meta.get("sources", []))
    if rows and not any(source.get("dataset") == "daily_basic" for source in sources):
        sources.append({
            "dataset": "daily_basic", "as_of": meta.get("data_as_of"),
            "record_ids": [row.get("record_id") for row in rows if row.get("record_id") is not None],
            "source_names": sorted({row.get("source") or "unknown" for row in rows}),
        })
    missing = list(meta.get("missing", []))
    if not rows and "daily_basic" not in missing:
        missing.append("daily_basic")
    return {
        "protocol": "x2stock.skill.v1", "status": "ok",
        "skill_id": "low-valuation-screener", "version": "1.0.0",
        "as_of": meta.get("data_as_of"),
        "result": {
            "items": ranked[:top_n], "eligible_count": len(ranked),
            "excluded_count": len(rows) - len(valid), "exclusions": dict(sorted(exclusions.items())),
        },
        "provenance": sources, "missing_data": missing,
        "assumptions": [
            "仅使用宿主提供的最新可用日终估值截面。",
            "PE(TTM) 与 PB 均需为正数；百分位在通过过滤的股票截面内计算。",
            "估值分数为 PE 与 PB 百分位的等权均值，低分优先；同分按股票代码升序。",
            "缺少股票主数据时仍返回代码和估值，名称与行业为空。",
        ],
        "risks": [
            "低估值不代表价格必然上涨，财务质量、行业差异和流动性未纳入评分。",
            "筛选结果仅供研究参考，不构成投资建议。",
        ],
    }


def main():
    try:
        request = json.loads(sys.stdin.readline())
        response = run(request)
    except Exception as exc:
        response = {
            "protocol": "x2stock.skill.v1", "status": "error",
            "skill_id": "low-valuation-screener", "version": "1.0.0", "as_of": None,
            "result": {"items": [], "eligible_count": 0, "excluded_count": 0, "exclusions": {}},
            "provenance": [], "missing_data": [], "assumptions": [], "risks": [str(exc)],
        }
    sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
