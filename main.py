import streamlit as st
from api import initialize_client, fetch_exported_annotations
from ui import sidebar_ui, project_selection_ui, export_controls_ui

# Sidebar UI for API input and instructions
sidebar_ui()

# Initialize global df variable
df = None

if st.session_state.get('api_key'):
    client = initialize_client(st.session_state['api_key'])
    if client:
        # Project selection UI and project metadata preview
        selected_project = project_selection_ui(client)

        if selected_project:
            # Export fetching controls and data processing
            fetch_exported_annotations(selected_project)

            # Display export and download controls
            export_controls_ui(selected_project)