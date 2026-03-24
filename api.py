import streamlit as st
from labelbox import Client
import requests
import json
# import pandas as pd
from time import perf_counter
# from annotation_wrapper import AnnotationWrapper
from utils import process_exported_data


def initialize_client(api_key):
    if not api_key or not api_key.strip():
        st.error("API key is empty. Enter your key in the sidebar and try again.")
        return None
    try:
        client = Client(api_key)
        st.success("Authenticated with Labelbox.")
        return client
    except Exception as e:
        st.error(f"Authentication failed: {e}. Check that your key is correct and has project access.")
        return None

def _extract_workflow_status(item):
    """Extract workflow_status from the project_details block in the export."""
    for project_data in item.get('projects', {}).values():
        # Try project-level project_details first
        status = project_data.get('project_details', {}).get('workflow_status')
        if status:
            return status
        # Try inside each label
        for label in project_data.get('labels', []):
            status = label.get('project_details', {}).get('workflow_status')
            if status:
                return status
    return 'unknown'


def fetch_exported_annotations(selected_project):
    done_only = st.checkbox("Fetch DONE annotations only", value=True)
    filters = {"action": ["DONE"]} if done_only else {}
    export_button = st.button("Fetch Annotations")

    if export_button:
        with st.spinner("Fetching annotations..."):
            try:
                start_time = perf_counter()
                export_task = selected_project.export_v2(params={"project_details": True}, filters=filters)
                export_task.wait_till_done(timeout_seconds=300)
                end_time = perf_counter()

                if export_task.errors:
                    st.error(f"Export task errors: {export_task.errors} (took {end_time - start_time:.2f}s)")
                    return

                export_url = export_task.result_url
                if not export_url:
                    st.error("Export completed but no download URL was returned. Try fetching again.")
                    return

                st.success(f"Export completed! Took {end_time - start_time:.2f} seconds.")

                try:
                    response = requests.get(export_url, timeout=(10, 120))
                    response.raise_for_status()
                except requests.exceptions.Timeout:
                    st.error("Download timed out. The export file may be very large. Try again or check your network connection.")
                    return
                except requests.exceptions.RequestException as e:
                    st.error(f"Could not download export file: {e}. Check your internet connection and try again.")
                    return

                json_lines = response.text.splitlines()
                parsed_data = []
                bad_lines = 0
                for line in json_lines:
                    if not line.strip():
                        continue
                    try:
                        parsed_data.append(json.loads(line))
                    except json.JSONDecodeError:
                        bad_lines += 1
                if bad_lines:
                    st.warning(f"{bad_lines} line(s) in the export could not be parsed and were skipped.")

                # Debug: inspect first item's projects structure
                if parsed_data:
                    with st.expander("🔍 Debug: first item projects structure"):
                        first = parsed_data[0]
                        for proj_id, proj_data in first.get('projects', {}).items():
                            st.write(f"**project_id:** {proj_id}")
                            st.write(f"project-level keys: {list(proj_data.keys())}")
                            st.write(f"project_details (project-level): {proj_data.get('project_details')}")
                            for i, label in enumerate(proj_data.get('labels', [])):
                                st.write(f"label[{i}] keys: {list(label.keys())}")
                                st.write(f"  project_details (label-level): {label.get('project_details')}")

                # Extract workflow_status per row before normalization (index-aligned)
                workflow_statuses = [_extract_workflow_status(item) for item in parsed_data]

                df = process_exported_data(parsed_data)
                df['workflow_status'] = workflow_statuses

                # Show breakdown by workflow status
                status_counts = df['workflow_status'].value_counts()
                cols = st.columns(max(len(status_counts), 1))
                for col, (status, count) in zip(cols, status_counts.items()):
                    col.metric(status, count)

                # Save to session state
                st.session_state['exported_df'] = df
                st.session_state['export_url'] = export_url

            except Exception as e:
                st.error(f"An error occurred during export: {e}")