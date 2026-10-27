"""실험 결과 저장소 접근 계층.

화면 코드는 이 모듈의 함수만 사용한다. 저장소를 SQLite에서 외부 DB로 바꿀 때는
이 파일만 수정하면 된다.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

# ---------------------------------------------------------------------------
# 컬럼 정의 (화면·검증·그래프에서 공통으로 사용)
# ---------------------------------------------------------------------------

CONDITION_COLUMNS: dict[str, dict[str, str]] = {
    "q_condition": {"label": "Q조건", "unit": "℃"},
    "t_condition": {"label": "T조건", "unit": "℃"},
}

PROPERTIES: dict[str, dict[str, str]] = {
    "hardness": {"label": "경도", "unit": "HRC"},
    "yield_strength": {"label": "항복강도", "unit": "MPa"},
    "tensile_strength": {"label": "인장강도", "unit": "MPa"},
    "impact_strength": {"label": "충격강도", "unit": "J"},
}

REQUIRED_COLUMNS = ["grade", "q_condition", "t_condition"]
DATA_COLUMNS = REQUIRED_COLUMNS + list(PROPERTIES)
ALL_COLUMNS = ["id", *DATA_COLUMNS, "created_at", "updated_at"]

COLUMN_LABELS: dict[str, str] = {
    "id": "ID",
    "grade": "Grade",
    **{k: f"{v['label']} ({v['unit']})" for k, v in CONDITION_COLUMNS.items()},
    **{k: f"{v['label']} ({v['unit']})" for k, v in PROPERTIES.items()},
    "created_at": "등록일시",
    "updated_at": "수정일시",
}

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "experiments.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    grade            TEXT    NOT NULL,
    q_condition      REAL    NOT NULL,
    t_condition      REAL    NOT NULL,
    hardness         REAL,
    yield_strength   REAL,
    tensile_strength REAL,
    impact_strength  REAL,
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_grade_q_t
    ON experiments (grade, q_condition, t_condition);
"""


def get_db_path() -> Path:
    """DB 파일 경로. 환경변수 EXPERIMENT_DB_PATH로 바꿀 수 있다(테스트·검토용)."""
    return Path(os.environ.get("EXPERIMENT_DB_PATH", DEFAULT_DB_PATH))


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """저장할 컬럼만 남기고, 빈 문자열은 None으로 바꾼다."""
    cleaned = {}
    for col in DATA_COLUMNS:
        if col not in data:
            continue
        value = data[col]
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                value = None
        elif value is not None and pd.isna(value):
            value = None
        cleaned[col] = value
    return cleaned


# ---------------------------------------------------------------------------
# 초기화
# ---------------------------------------------------------------------------


def init_db() -> None:
    """테이블이 없으면 만든다. 앱 시작 시 호출한다."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


# ---------------------------------------------------------------------------
# 조회
# ---------------------------------------------------------------------------


def list_experiments(filters: dict[str, Any] | None = None) -> pd.DataFrame:
    """실험 결과를 DataFrame으로 반환한다.

    filters 예: {"grade": ["SCM440"], "q_condition": [850.0], "t_condition": [550.0]}
    값은 단일 값 또는 리스트를 받을 수 있고, 비어 있으면 무시한다.
    """
    where, params = [], []
    for col, value in (filters or {}).items():
        if col not in DATA_COLUMNS:
            raise ValueError(f"알 수 없는 필터 컬럼: {col}")
        values = value if isinstance(value, (list, tuple, set)) else [value]
        values = [v for v in values if v is not None]
        if not values:
            continue
        where.append(f"{col} IN ({', '.join('?' * len(values))})")
        params.extend(values)

    sql = f"SELECT {', '.join(ALL_COLUMNS)} FROM experiments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY grade, q_condition, t_condition, id"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    df = pd.DataFrame([dict(r) for r in rows], columns=ALL_COLUMNS)
    numeric = [c for c in DATA_COLUMNS if c != "grade"]
    df[numeric] = df[numeric].astype("float64")
    return df


def get_experiment(experiment_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {', '.join(ALL_COLUMNS)} FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
    return dict(row) if row else None


def list_grades() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT grade FROM experiments ORDER BY grade"
        ).fetchall()
    return [r["grade"] for r in rows]


def _list_conditions(column: str, grade: str) -> list[float]:
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM experiments WHERE grade = ? ORDER BY {column}",
            (grade,),
        ).fetchall()
    return [r[column] for r in rows]


def list_q_conditions(grade: str) -> list[float]:
    return _list_conditions("q_condition", grade)


def list_t_conditions(grade: str) -> list[float]:
    return _list_conditions("t_condition", grade)


def get_summary(recent_days: int = 7) -> dict[str, Any]:
    """홈 화면·사이드바 요약 정보. recent는 최근 recent_days일 안에 등록된 건수."""
    since = (datetime.now() - timedelta(days=recent_days)).isoformat(timespec="seconds")
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)                                          AS total,
                   COUNT(DISTINCT grade)                             AS grades,
                   COUNT(DISTINCT grade || '|' || q_condition || '|' || t_condition) AS combos,
                   COUNT(CASE WHEN created_at >= ? THEN 1 END)       AS recent,
                   MAX(updated_at)                                   AS last_updated
            FROM experiments
            """,
            (since,),
        ).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# 추가 / 수정 / 삭제
# ---------------------------------------------------------------------------


def add_experiment(data: dict[str, Any]) -> int:
    """실험 결과를 추가하고 새 id를 반환한다. 검증은 호출 전에 validators로 한다."""
    record = _clean(data)
    missing = [c for c in REQUIRED_COLUMNS if record.get(c) is None]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {', '.join(missing)}")
    now = _now()
    record["created_at"] = now
    record["updated_at"] = now
    cols = list(record)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO experiments ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [record[c] for c in cols],
        )
        return int(cur.lastrowid)


def add_experiments(records: list[dict[str, Any]]) -> int:
    """여러 건을 한 트랜잭션으로 추가하고 추가한 건수를 반환한다."""
    now = _now()
    with _connect() as conn:
        for data in records:
            record = _clean(data)
            record["created_at"] = now
            record["updated_at"] = now
            cols = list(record)
            conn.execute(
                f"INSERT INTO experiments ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})",
                [record[c] for c in cols],
            )
    return len(records)


def update_experiment(experiment_id: int, data: dict[str, Any]) -> bool:
    """실험 결과를 수정한다. 대상이 없으면 False를 반환한다."""
    record = _clean(data)
    for col in REQUIRED_COLUMNS:
        if col in record and record[col] is None:
            raise ValueError(f"필수 컬럼은 비울 수 없습니다: {col}")
    if not record:
        return get_experiment(experiment_id) is not None
    record["updated_at"] = _now()
    assignments = ", ".join(f"{c} = ?" for c in record)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE experiments SET {assignments} WHERE id = ?",
            [*record.values(), experiment_id],
        )
        return cur.rowcount > 0


def delete_experiment(experiment_id: int) -> bool:
    """실험 결과를 삭제한다. 대상이 없으면 False를 반환한다."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        return cur.rowcount > 0


def delete_experiments(experiment_ids: list[int]) -> int:
    """여러 건을 한 트랜잭션으로 삭제하고 실제 삭제한 건수를 반환한다."""
    if not experiment_ids:
        return 0
    with _connect() as conn:
        cur = conn.execute(
            f"DELETE FROM experiments WHERE id IN ({', '.join('?' * len(experiment_ids))})",
            list(experiment_ids),
        )
        return cur.rowcount


def delete_all() -> None:
    """모든 실험 결과를 삭제한다(샘플 데이터 재생성용)."""
    with _connect() as conn:
        conn.execute("DELETE FROM experiments")
