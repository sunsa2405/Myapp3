# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

This is a Streamlit app for steel heat-treatment experiment results: Grade, Q조건 = quenching temp, T조건 = tempering temp, and the properties 경도/항복강도/인장강도/충격강도. It lets users add, edit, and delete results, and plots how the properties change across conditions.

- Requirements: `../PRD.md`.
- Staged build prompts: `../PROMPTS.md`. All four stages are done.
- Latest review report (PRD checklist, fixed bugs, open items): `review/REVIEW.md`.
- All UI text is Korean.

## Commands

Run all commands from `experiment-app/`.

```bash
pip install -r requirements-dev.txt     # streamlit, pandas, plotly, openpyxl, pytest
python scripts/seed.py                  # wipe DB and insert 66 sample rows (--keep to append)
streamlit run app.py                    # http://localhost:8501
pytest                                  # pytest.ini sets testpaths=tests, pythonpath=.
pytest tests/test_db.py::test_update    # single test

# Isolated DB for manual or Playwright review (data/experiments.db stays untouched)
EXPERIMENT_DB_PATH=review/review.db python scripts/seed.py
EXPERIMENT_DB_PATH=review/review.db streamlit run app.py --server.port 8502
```

- There is no linter configured.
- Login is enabled only when `app_password` exists in `.streamlit/secrets.toml` (see `secrets.toml.example`). For a throwaway secrets file, pass `--secrets.files <path>` instead of creating `.streamlit/secrets.toml`.

## Architecture

### Request flow

`app.py` is the only entry point. It runs these steps in order:

1. `st.set_page_config`
2. `db.init_db()`
3. `st.navigation(...)`, hidden until the user is logged in
4. `auth.require_login()`
5. sidebar summary
6. `navigation.run()`

Each page script in `views/` then reads data via `cache.load_experiments()`, which is `st.cache_data` with a 60s ttl over `db.list_experiments()`, and filters it in pandas.

- The page folder is deliberately **not** named `pages/`. Streamlit auto-discovers `pages/`, and a fresh server's first deep-link request (e.g. `/데이터_관리`) would then run the page file directly, bypassing `app.py` and the login check.
- New pages must be registered in `app.py`.
- Page scripts must not call `st.set_page_config`.
- `navigation` is created before `require_login()` so the requested URL survives the login rerun.

### Layers

- **`db.py`: the single storage layer** (SQLite now).
  - Pages never touch SQL. Swapping in an external DB for Streamlit Cloud (PRD §7.2) means editing only this file. This is still open, and required before cloud deploy.
  - It is also the single source of truth for column names, Korean labels, and units: `PROPERTIES`, `CONDITION_COLUMNS`, `COLUMN_LABELS`, `DATA_COLUMNS`. Iterate over these constants instead of hard-coding columns.
  - SQL always uses parameter binding. Column names are interpolated only after being checked against `DATA_COLUMNS`.
- **Write path:** `validators.validate_experiment(data)` returns a list of Korean error messages, then `validators.normalize_experiment(data)` converts values to `float`/`None`, then `db.add_experiment` / `update_experiment` / `add_experiments`. The DB layer also rejects blank required fields as a backstop.
  - Bulk uploads go through `io_utils.prepare_upload()`. It maps Korean, unit-suffixed, or English headers and splits the rows into valid records and error rows.
- **Trend pages:** both pages call `trend_view.render_trend_page(x_col, fixed_col)`, which uses `charts.trend_chart(df, x_col, group_col, group_values, colors)`.
- **Data rules:**
  - Q/T conditions are numeric REAL (℃) so the x-axis sorts.
  - Property columns are nullable (not measured).
  - Rows with the same (grade, q, t) are intentional repeat tests. Charts plot their mean and overlay the individual points.

### Streamlit pitfalls this code works around

Keep these behaviors when changing pages:

- **Write-then-refresh:** after any write, call `after_change()` in `views/1_데이터_관리.py`. It does four things:
  - calls `cache.invalidate()`
  - bumps `st.session_state["data_version"]`, which is part of the form, uploader, and table widget keys so they reset
  - sets a flash message
  - calls `st.rerun()`
- **Stable element count above keyed widgets:**
  - `ui.show_flash()` always creates its container, even when there is no message.
  - A conditional element above the keyed `st.tabs(key="manage_tab")` shifts positions and leaves a duplicate, still-interactive tabs/forms block on screen.
  - The tabs `key` itself is required, or the active tab resets on rerun (e.g. after a file upload).
- **Row selection:** `st.dataframe` selection is positional. The table key includes a hash of the displayed ids, so any change in the displayed rows clears the selection rather than pointing at another row.
- **Upload idempotency:** `uploaded.file_id` is recorded in `st.session_state["registered_uploads"]` before inserting. A fast double-click on "등록" used to insert twice.
- **Tables:** render as `st.dataframe(ui.table_frame(df), column_config=ui.column_config(), ...)`.
  - Never use a pandas Styler. At 10k rows the data page took 9–13s; PRD requires ≤2s.
  - Null cells show Streamlit's grey "None", a known limitation.
- **Downloads:** pass a callable (`lambda: io_utils.to_excel_bytes(df)`) to `st.download_button`, so files are built only on click.
- **Dev server reloads:** a running server does not reliably reload edited helper modules (`db.py`, `charts.py`, `ui.py`, etc.). Restart `streamlit run` after changing non-page modules.

### Theme and chart colors

- **Theme:**
  - `.streamlit/config.toml` defines `[theme.light]` and `[theme.dark]`. The app follows the OS setting or the user's choice.
  - Charts pick the matching palette via `ui.theme_type()` (`st.context.theme.type`).
  - A button whose key starts with `danger_` gets the red style from `ui.DANGER_CSS`.
- **Chart colors:**
  - `charts.PALETTES` is a colorblind-safe order checked with the dataviz validator; keep the order.
  - `charts.color_map(all_values_for_grade, theme)` colors a condition by its position among *all* of the grade's values. A condition keeps its color when the selection changes.
- **Units:** units go in subplot titles, not y-axis titles. Y-titles between subplots overlap the neighbouring tick labels.

## Review / Playwright

The scenarios in `review/e2e/*.js` are re-runnable.

- **Running them:** use the Playwright MCP `browser_run_code_unsafe` tool with `filename`, against the :8502 server above.
- **Resetting data:** `sh review/reset.sh` stops :8502 and re-seeds `review/review.db`.

Lessons from writing them:

- **Waiting:** wait for `[data-testid="stStatusWidget"]` to be hidden after each action. Fixed sleeps catch half-rendered reruns.
- **Locating buttons:** material icons are part of a button's accessible name (e.g. "add 추가"). Locate form submits via `[data-testid="stFormSubmitButton"] button`, and other buttons by regex.
- **Reading chart data:** Plotly 6 ships arrays as binary, so read chart values from `plot._fullData`, not `plot.data`.
- **Screenshot paths:** Playwright may only write screenshots under `C:\Users\User\Desktop\업무자동화\`.
- **Console noise:** 404s for `/<page>/_stcore/health` and `/_stcore/host-config` on deep links are Streamlit noise, not app errors.

## Conventions / assumptions

- **Units:** HRC for hardness, MPa for strength, J for impact, ℃ for conditions. These are assumptions pending the PRD §9 open questions, defined once in `db.py`.
- **Garbled Korean on Windows:** in Git Bash, Korean console output appears garbled (cp949). For Python run from a heredoc containing Korean or backslashes, use `python -X utf8 -`, and prefer the Edit tool for lines with `\n` escapes.
