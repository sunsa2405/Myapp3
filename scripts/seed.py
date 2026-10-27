"""샘플 실험 데이터를 DB에 넣는다.

사용법:
    python scripts/seed.py          # 기존 데이터를 지우고 샘플 데이터로 채움
    python scripts/seed.py --keep   # 기존 데이터를 유지하고 샘플 데이터 추가
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402

# Grade별 기준 물성 (Q=850℃, T=450℃ 기준)
GRADE_BASE = {
    "SCM440": {"hardness": 44.0, "yield_strength": 1250.0, "tensile_strength": 1380.0, "impact_strength": 45.0},
    "S45C": {"hardness": 36.0, "yield_strength": 900.0, "tensile_strength": 1050.0, "impact_strength": 55.0},
    "SNCM439": {"hardness": 47.0, "yield_strength": 1350.0, "tensile_strength": 1480.0, "impact_strength": 60.0},
}
Q_CONDITIONS = [830.0, 850.0, 870.0]
T_CONDITIONS = [450.0, 500.0, 550.0, 600.0, 650.0]


def make_record(grade: str, q: float, t: float, rng: random.Random) -> dict:
    base = GRADE_BASE[grade]
    dt = (t - 450.0) / 50.0  # 소려 온도 단계 (0~4)
    dq = (q - 850.0) / 20.0  # 소입 온도 단계 (-1, 0, 1)

    # 소려 온도가 오르면 경도·강도 감소, 인성 증가.
    # 소입 온도는 850℃ 부근이 최적이고 벗어나면 강도가 약간 떨어진다.
    q_penalty = 1.0 - 0.015 * dq * dq + 0.005 * dq

    def noisy(value: float, pct: float) -> float:
        return value * (1 + rng.gauss(0, pct))

    hardness = noisy(base["hardness"] * (1 - 0.07 * dt) * q_penalty, 0.01)
    tensile = noisy(base["tensile_strength"] * (1 - 0.065 * dt) * q_penalty, 0.012)
    yield_ = min(noisy(base["yield_strength"] * (1 - 0.07 * dt) * q_penalty, 0.015), tensile * 0.97)
    impact = noisy(base["impact_strength"] * (1 + 0.22 * dt) * (1 - 0.04 * abs(dq)), 0.05)

    return {
        "grade": grade,
        "q_condition": q,
        "t_condition": t,
        "hardness": round(hardness, 1),
        "yield_strength": round(yield_),
        "tensile_strength": round(tensile),
        "impact_strength": round(impact, 1),
    }


def build_records(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    records = []
    for grade in GRADE_BASE:
        for q in Q_CONDITIONS:
            for t in T_CONDITIONS:
                repeats = rng.choice([1, 1, 1, 2, 3])  # 일부 조합은 반복 시험
                for _ in range(repeats):
                    record = make_record(grade, q, t, rng)
                    if rng.random() < 0.08:  # 일부 물성은 미측정
                        record[rng.choice(list(db.PROPERTIES))] = None
                    records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="샘플 실험 데이터 생성")
    parser.add_argument("--keep", action="store_true", help="기존 데이터를 지우지 않음")
    args = parser.parse_args()

    db.init_db()
    if not args.keep:
        db.delete_all()
    count = db.add_experiments(build_records())
    summary = db.get_summary()
    print(f"샘플 데이터 {count}건 추가 완료 → DB: {db.get_db_path()}")
    print(f"총 {summary['total']}건, Grade {summary['grades']}개, 조건 조합 {summary['combos']}개")


if __name__ == "__main__":
    main()
