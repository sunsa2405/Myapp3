# 실험 데이터 관리 및 분석 앱

Grade별 열처리 조건(Q조건·T조건)에 따른 경도, 항복강도, 인장강도, 충격강도 실험 결과를 관리하고 경향을 그래프로 보는 Streamlit 앱입니다. 요구사항은 상위 폴더의 `PRD.md`를 참고하세요.

## 설치

```bash
cd experiment-app
pip install -r requirements.txt        # 실행만 할 때
pip install -r requirements-dev.txt    # 테스트까지 할 때
```

## 샘플 데이터 넣기

```bash
python scripts/seed.py          # 기존 데이터를 지우고 샘플 데이터로 채움
python scripts/seed.py --keep   # 기존 데이터에 샘플 데이터 추가
```

Grade 3개(SCM440, S45C, SNCM439) × Q조건 3개(830, 850, 870℃) × T조건 5개(450~650℃) 조합의 데이터가 들어갑니다. 일부 조합은 반복 시험이 2~3건이고, 일부 물성은 빈 값입니다.

## 실행

```bash
streamlit run app.py
```

브라우저에서 http://localhost:8501 이 열립니다.

## 테스트

```bash
pytest
```

## 구조

| 경로 | 역할 |
|---|---|
| `app.py` | 진입점: 페이지 설정, 로그인, 페이지 라우팅 |
| `views/` | 홈, 데이터 관리, T조건 경향, Q조건 경향 페이지 (`app.py`의 `st.navigation`에 등록) |
| `trend_view.py` | 두 경향 페이지 공통 화면 |
| `io_utils.py` | CSV/Excel 업로드 해석, 다운로드 파일 생성 |
| `cache.py`, `ui.py`, `auth.py` | 조회 캐시, 공통 화면 요소, 비밀번호 로그인 |
| `db.py` | 저장소 접근(CRUD), 컬럼·단위 정의. 저장소를 바꿀 때는 이 파일만 수정 |
| `validators.py` | 입력값 검증 |
| `charts.py` | 경향 그래프 생성 |
| `scripts/seed.py` | 샘플 데이터 생성 |
| `assets/` | 사이드바 로고, 브라우저 탭 아이콘 |
| `.streamlit/config.toml` | 라이트/다크 테마 색상 (운영체제 설정을 따르고, 오른쪽 위 메뉴 → Settings에서 바꿀 수 있음) |
| `data/experiments.db` | SQLite DB 파일 (git 제외) |

## 데이터 단위

| 항목 | 단위 |
|---|---|
| Q조건, T조건 | ℃ |
| 경도 | HRC |
| 항복강도, 인장강도 | MPa |
| 충격강도 | J |

DB 파일 위치는 환경변수 `EXPERIMENT_DB_PATH`로 바꿀 수 있습니다(테스트·검토용).

## 로그인 (선택)

`.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사하고 `app_password`를 정하면, 앱 접속 시 비밀번호를 묻습니다. 파일이 없으면 로그인 없이 바로 사용합니다. 배포할 때는 Streamlit Cloud 앱 설정의 Secrets에 같은 값을 넣으세요.
