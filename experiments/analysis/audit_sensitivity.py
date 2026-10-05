"""Read-only inventory of delivered sensitivity CSVs; no model rerun."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "补充资料" / "04_灵敏度分析"
OUT = ROOT / "分析工作区" / "敏感性交付表审计.json"


def main() -> None:
    report = {}
    for path in sorted(SOURCE.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        assert rows
        score_rows = [float(row["score"]) for row in rows if row.get("score") not in (None, "")]
        report[path.name] = {
            "rows": len(rows), "columns": list(rows[0]),
            "duplicate_full_rows": len(rows)-len({tuple(sorted(x.items())) for x in rows}),
            "score_min": min(score_rows) if score_rows else None,
            "score_max": max(score_rows) if score_rows else None,
            "grades": dict(Counter(row["grade"] for row in rows if row.get("grade"))),
            "dominant_modes": dict(Counter(row["dominant_mode"] for row in rows if row.get("dominant_mode"))),
            "stakes": dict(Counter(row["stake"] for row in rows if row.get("stake"))),
        }
    (OUT).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({name: {k: obj[k] for k in ("rows", "duplicate_full_rows", "score_min", "score_max", "grades", "dominant_modes")} for name,obj in report.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
