# GEMINI.md

This file provides guidance to Gemini CLI when working with code in this repository.

## Running the App

```bash
streamlit run main.py
```

Dependencies: `labelbox`, `streamlit`, `pandas`, `numpy`, `pyyaml`, `requests`

## Architecture

This is a Streamlit app that exports Labelbox annotations and converts them to YOLO format.

**Data flow:**
1. User provides Labelbox API key → `api.py` initializes the Labelbox client
2. User selects a project → project metadata fetched via SDK
3. "Fetch Annotations" → `api.py` calls `export_v2`, filters for `DONE` status → Pandas DataFrame
4. "Normalize for YOLO" → `annotation_wrapper.py` converts bounding boxes/polygons/points to YOLO normalized coords → `utils.py` builds ZIP with per-image `.txt` label files + `data.yaml`
5. Download buttons for CSV, YOLO ZIP, or raw NDJSON

**Module responsibilities:**

| File | Purpose |
|------|---------|
| `main.py` | Entry point; orchestrates page layout and session state |
| `api.py` | Labelbox client init, `export_v2` fetch, DONE-status filtering |
| `ui.py` | All Streamlit UI: API key input, project selector, export controls, download buttons |
| `annotation_wrapper.py` | Converts Labelbox annotation dicts (bounding_box, polygon, point) → YOLO format; handles 4 EXIF rotation codes (0°/90°/180°/270°) |
| `utils.py` | Flattens nested JSON exports, unpacks label arrays, builds ZIP archives with `data.yaml` class mapping |
| `components/sidebar.py` | Sidebar UI helpers (overlaps with `ui.py`) |

**Key design notes:**
- `annotation_wrapper.py` normalizes coordinates to `[0, 1]` range relative to image dimensions
- YOLO output format: `<class_id> <x_center> <y_center> <width> <height>` per line
- `data.yaml` is auto-generated with `nc` (class count) and `names` (class list) from annotation metadata
- API credentials can come from direct text input or an uploaded `labelboxAPIkey.json` file

## Gemini Specific Instructions
- Use `streamlit run main.py` to run the application.
- Maintain the YOLO normalization logic in `annotation_wrapper.py`.
- Ensure `data.yaml` generation stays consistent with the class mapping.
