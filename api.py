import streamlit as st
from labelbox import Client
import requests
import json
from time import perf_counter
from utils import process_exported_data

# Map should match ui.py for consistency in ordering
STATUS_ORDER = ["Done", "InReview", "InRework", "ToLabel"]

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
        status = project_data.get('project_details', {}).get('workflow_status')
        if status:
            return status
        for label in project_data.get('labels', []):
            status = label.get('project_details', {}).get('workflow_status')
            if status:
                return status
    return 'unknown'

def fetch_exported_annotations(selected_project, selected_statuses):
    # Labelbox workflow_status filter only supports a single string, not a list.
    # If exactly one status is selected, we use it as a filter.
    # Otherwise, we fetch all and filter locally to support multi-status selection.
    api_filter_value = None
    if selected_statuses and len(selected_statuses) == 1:
        api_filter_value = selected_statuses[0]
    
    filters = {"workflow_status": api_filter_value} if api_filter_value else {}

    with st.spinner("Fetching annotations..."):
        try:
            start_time = perf_counter()
            export_task = selected_project.export_v2(params={"project_details": True}, filters=filters)
            export_task.wait_till_done(timeout_seconds=300)
            end_time = perf_counter()

            if export_task.errors:
                st.error(f"Export task errors: {export_task.errors} (took {end_time - start_time:.2f}s)")
                st.session_state['fetch_triggered'] = False
                return

            export_url = export_task.result_url
            if not export_url:
                st.error("Export completed but no download URL was returned. Try fetching again.")
                st.session_state['fetch_triggered'] = False
                return

            st.success(f"Export completed! Took {end_time - start_time:.2f} seconds.")

            try:
                response = requests.get(export_url, timeout=(10, 120))
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                st.error(f"Could not download export file: {e}.")
                st.session_state['fetch_triggered'] = False
                return

            json_lines = response.text.splitlines()
            parsed_data = []
            for line in json_lines:
                if not line.strip():
                    continue
                try:
                    parsed_data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

            # Extract workflow_status per row (index-aligned)
            workflow_statuses = [_extract_workflow_status(item) for item in parsed_data]

            # If we fetched all because multiple statuses were selected, filter locally now
            if not api_filter_value and selected_statuses:
                filtered_indices = [i for i, status in enumerate(workflow_statuses) if status in selected_statuses]
                parsed_data = [parsed_data[i] for i in filtered_indices]
                workflow_statuses = [workflow_statuses[i] for i in filtered_indices]

            if not parsed_data:
                st.warning("No annotations found matching the selected statuses.")
                st.session_state['fetch_triggered'] = False
                return

            df = process_exported_data(parsed_data)
            df['workflow_status'] = workflow_statuses

            # Save to session state in correct order
            unique_statuses = df['workflow_status'].unique()
            st.session_state['fetched_statuses'] = [s for s in STATUS_ORDER if s in unique_statuses]
            st.session_state['exported_df'] = df
            st.session_state['export_url'] = export_url
            st.session_state['fetch_triggered'] = False

        except Exception as e:
            st.error(f"An error occurred during export: {e}")
            st.session_state['fetch_triggered'] = False
