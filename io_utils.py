"""CSV/Excel 업로드 해석과 다운로드 파일 생성 (PRD F1-8, F1-9)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import pandas as pd

from db import COLUMN_LABELS, CONDITION_COLUMNS, DATA_COLUMNS, PROPERTIES, REQUIRED_COLUMNS
from validators import normalize_experiment, validate_experiment


def _norm(name: Any) -> str:
    """열 이름 비교용: 공백·괄호·밑줄·℃를 없애고 소문자로."""
    return re.sub(r"[\s_()\[\]℃]", "", str(name)).lower()


def _build_aliases() -> dict[str, str]:
    aliases = {_norm(col): col for col in DATA_COLUMNS}
    aliases[_norm("Grade")] = "grade"
    aliases[_norm("강종")] = "grade"
    for col, meta in {**CONDITION_COLUMNS, **PROPERTIES}.items():
        aliases[_norm(meta["label"])] = col
        aliases[_norm(COLUMN_LABELS[col])] = col
    return aliases


_ALIASES = _build_aliases()


@dataclass
class UploadResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    errors: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["행", "오류"]))
    mapping: dict[str, str] = field(default_factory=dict)  # 파일 열 이름 → 내부 컬럼
    ignored: list[str] = field(default_factory=list)  # 인식하지 못한 열
    missing_required: list[str] = field(default_factory=list)  # 없는 필수 컬럼


def map_columns(columns: list[Any]) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    ignored: list[str] = []
    for col in columns:
        target = _ALIASES.get(_norm(col))
        if target and target not in mapping.values():
            mapping[col] = target
        else:
            ignored.append(str(col))
    return mapping, ignored


def read_upload(filename: str, content: bytes) -> pd.DataFrame:
    """업로드 파일을 DataFrame으로 읽는다. 값은 검증 전이므로 문자열/원본 그대로 둔다."""
    if filename.lower().endswith(".xlsx"):
        return pd.read_excel(BytesIO(content), dtype=object)
    # 한글 Excel에서 저장한 CSV는 cp949인 경우가 많다.
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(BytesIO(content), dtype=str, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 알 수 없습니다. UTF-8 또는 CP949(EUC-KR)로 저장해주세요.")


def prepare_upload(df: pd.DataFrame) -> UploadResult:
    """열 이름을 매핑하고 행마다 검증해서 등록 가능한 행과 오류 행으로 나눈다."""
    mapping, ignored = map_columns(list(df.columns))
    result = UploadResult(mapping=mapping, ignored=ignored)
    result.missing_required = [c for c in REQUIRED_COLUMNS if c not in mapping.values()]
    if result.missing_required:
        return result

    renamed = df[list(mapping)].rename(columns=mapping)
    errors = []
    for i, row in enumerate(renamed.to_dict("records")):
        if all(pd.isna(v) or str(v).strip() == "" for v in row.values()):
            continue  # 완전히 빈 행은 건너뜀
        row_errors = validate_experiment(row)
        if row_errors:
            errors.append({"행": i + 2, "오류": " / ".join(row_errors)})  # 1행은 헤더
        else:
            result.records.append(normalize_experiment(row))
    result.errors = pd.DataFrame(errors, columns=["행", "오류"])
    return result


def export_frame(df: pd.DataFrame) -> pd.DataFrame:
    """내려받기용 표: 다시 업로드할 수 있도록 데이터 열만, 한국어 열 이름으로."""
    return df.reindex(columns=DATA_COLUMNS).rename(columns=COLUMN_LABELS)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    # utf-8-sig(BOM)여야 Excel에서 열었을 때 한글이 깨지지 않는다.
    return export_frame(df).to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    export_frame(df).to_excel(buffer, index=False, sheet_name="실험결과")
    return buffer.getvalue()
