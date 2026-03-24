import streamlit as st
from api import initialize_client, fetch_exported_annotations
from ui import sidebar_ui, project_selection_ui, export_controls_ui

# Page config
st.set_page_config(page_title="Labelbox YOLO Exporter", layout="wide")

# Sidebar UI for API input
sidebar_ui()

if st.session_state.get('api_key'):
    client = initialize_client(st.session_state['api_key'])
    if client:
        with st.sidebar:
            selected_project = project_selection_ui(client)

        if selected_project:
            if st.session_state.get('fetch_triggered'):
                fetch_exported_annotations(
                    selected_project,
                    st.session_state.get('selected_statuses', ['Done'])
                )
            export_controls_ui(selected_project)
else:
    st.info("Connect to Labelbox using your API key in the sidebar to get started.")
