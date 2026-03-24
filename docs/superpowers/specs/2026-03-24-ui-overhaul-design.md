# UI Overhaul: Status-Aware Fetch & Filter

## Context

The app previously had a binary "Fetch DONE only" checkbox. Now that `workflow_status` is available from Labelbox via `params={"project_details": True}`, users should be able to select which statuses to fetch, see a breakdown by status after fetching, and filter the preview/export by status — without ever seeing options that weren't fetched.

## Status Values

Labelbox API values and their display labels:

| API value | Display label |
|-----------|---------------|
| `"Done"` | Done |
| `"InReview"` | In Review |
| `"InRework"` | In Rework |
| `"ToLabel"` | To Label |

`st.session_state['selected_statuses']` always stores **API values** (e.g. `["Done", "InReview"]`). Pills display using the map above. The Labelbox filter is `{"workflow_status": selected_statuses}` with API values. Note: the existing code uses `{"action": ["DONE"]}` — this must be replaced with `{"workflow_status": [...]}`.

`_extract_workflow_status()` returns raw API values (e.g. `"InReview"`). `st.session_state['fetched_statuses']` stores raw API values. Post-fetch pills display using the same map, and filter `df` using raw API values from `df['workflow_status']`.

## Layout

**Hybrid A+C**: sidebar handles all configuration, main area has three numbered sections.

### Sidebar
1. **Connect** — API key input + credentials file uploader. Writes to `st.session_state['api_key']`. Implemented in `sidebar_ui()` in `ui.py`. No return value — uses session state exclusively.
2. **Project** — `project_selection_ui(client)` remains a separate function, called from inside `with st.sidebar:` in `main.py` after client init. Returns `selected_project` or `None`.
3. **Fetch Statuses** — `st.pills` with `options=list(STATUS_MAP.keys())`, `format_func=STATUS_MAP.get`, `selection_mode="multi"`. Default: `["Done"]`. Writes API values to `st.session_state['selected_statuses']`. Rendered inside `project_selection_ui()` after the project selectbox (only shown when a project is selected).
4. **Fetch button** — `st.button("Fetch Annotations")` below the pills, inside `project_selection_ui()`. On click, sets `st.session_state['fetch_triggered'] = True`.

### Main area — before fetch
Sections ①②③ are not shown. `export_controls_ui()` gates on `'exported_df' in st.session_state`; if absent, displays a centered placeholder: `"← Select a project and fetch annotations to get started."` While a fetch is in progress, the `st.spinner` inside `fetch_exported_annotations` covers the main area — no additional placeholder state needed.

### Main area — ① Fetched
`st.metric` tiles — one per fetched status (in the order: Done, In Review, In Rework, To Label, filtered to only those present in `fetched_statuses`) + a Total tile. Built from `df['workflow_status'].value_counts()`.

### Main area — ② Preview & Filter
`st.pills` with `options=st.session_state['fetched_statuses']`, `format_func=STATUS_MAP.get`, `selection_mode="multi"`, all selected by default. Filters `exported_df` to rows where `workflow_status` is in the active selection. Shows filtered row count. Preview table shows `filtered_df.head(10)`.

### Main area — ③ Export
Inline row: `Normalize for YOLO` button, then download buttons (YOLO ZIP, CSV, NDJSON link). Export uses `filtered_df` (respecting the post-fetch filter). Label: `"Exporting {len(filtered_df)} rows"`.

## Data Flow

```
sidebar pills selection (API values)
  → st.session_state['selected_statuses']  e.g. ["Done", "InReview"]
  → st.session_state['fetch_triggered'] = True on button click

main.py detects fetch_triggered
  → calls fetch_exported_annotations(selected_project, selected_statuses)
  → filters = {"workflow_status": selected_statuses}
  → export_v2(params={"project_details": True}, filters=filters)
  → parsed_data (1 item per NDJSON line, 1:1 with df rows — process_exported_data uses index-based merges, never explodes rows)
  → workflow_statuses = [_extract_workflow_status(item) for item in parsed_data]  (index-aligned)
  → df = process_exported_data(parsed_data)
  → df['workflow_status'] = workflow_statuses
  → st.session_state['fetched_statuses'] = [s for s in STATUS_MAP if s in df['workflow_status'].values]  # STATUS_MAP order, not lexicographic
  → st.session_state['exported_df'] = df
  → st.session_state['fetch_triggered'] = False  # clear after fetch completes or errors
  → st.session_state['export_url'] = export_url

export_controls_ui()
  → reads exported_df, fetched_statuses
  → post-fetch pills → filtered_df
  → metrics, preview, export all use filtered_df
```

## File Changes

### `ui.py`

- **`STATUS_MAP`**: module-level dict `{"Done": "Done", "InReview": "In Review", "InRework": "In Rework", "ToLabel": "To Label"}`.
- **`sidebar_ui()`**: add status pills + Fetch button. Absorbs project selection (calls `client.get_projects()` — requires `client` passed as arg, or client init happens in `main.py` and project list passed in). Simplest: `sidebar_ui()` returns `(api_key, selected_statuses)` as before, and project selection stays as a separate call — see main.py below.
- **`export_controls_ui()`**:
  - Remove old DONE-only checkbox reference
  - Gate entire function on `'exported_df' in st.session_state`; show placeholder otherwise
  - Add metrics row (① Fetched)
  - Add post-fetch pills (② Preview & Filter) — options from `fetched_statuses`, display via `STATUS_MAP`
  - Filter `exported_df` by active pills → `filtered_df`
  - Pass `filtered_df` to normalize and export functions (not full `exported_df`)
  - Export label shows `len(filtered_df)`

### `api.py`

- **`fetch_exported_annotations(selected_project, selected_statuses)`**:
  - Remove `done_only` checkbox and Fetch button (moved to `project_selection_ui`)
  - Runs only when called; caller (`main.py`) guards with `fetch_triggered`
  - `filters = {"workflow_status": selected_statuses} if selected_statuses else {}`
  - After building df, set in this order: `fetched_statuses` first, then `exported_df`, then `fetch_triggered = False`. Always clear `fetch_triggered` (even on error) to prevent stale retriggers.
  - Keep existing timeout, error handling, and debug expander

### `main.py`

```python
sidebar_ui()   # writes api_key to session state; no return value

if st.session_state.get('api_key'):
    client = initialize_client(st.session_state['api_key'])
    if client:
        with st.sidebar:
            selected_project = project_selection_ui(client)
            # project_selection_ui also renders status pills + Fetch button
            # and sets selected_statuses + fetch_triggered in session state

        if selected_project:
            if st.session_state.get('fetch_triggered'):
                fetch_exported_annotations(
                    selected_project,
                    st.session_state.get('selected_statuses', ['Done'])
                )
            export_controls_ui(selected_project)
```

`fetch_triggered` is `None` (falsy) on first page load — safe. It is set `True` only inside `project_selection_ui` when the Fetch button is clicked with a valid project already selected, so the "button before project" edge case cannot occur.

## Session State Keys

| Key | Type | Set by | Used by |
|-----|------|--------|---------|
| `api_key` | str | `sidebar_ui` | `main.py` |
| `selected_statuses` | list[str] (API values) | `sidebar_ui` | `main.py` → `fetch_exported_annotations` |
| `fetch_triggered` | bool | `sidebar_ui` (True on click), `fetch_exported_annotations` (False after done) | `main.py` |
| `exported_df` | DataFrame | `fetch_exported_annotations` | `export_controls_ui` |
| `fetched_statuses` | list[str] (API values) | `fetch_exported_annotations` | `export_controls_ui` (post-fetch pills) |
| `export_url` | str | `fetch_exported_annotations` | `export_controls_ui` (NDJSON link) |

## Out of Scope

- No changes to `annotation_wrapper.py`, `utils.py`
- No changes to YOLO normalization logic
- No CSV download UI (currently commented out — leave as-is)
- `components/sidebar.py` is not used by `main.py` and is left untouched
