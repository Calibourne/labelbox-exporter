import streamlit as st
import json

def sidebar_ui():
    with st.sidebar:
        st.title("Labelbox Annotation Exporter")
        st.markdown("""
        This app allows you to export annotations from your Labelbox projects.

        **Instructions:**
        1. Enter your Labelbox API key.
        2. Select a project to export annotations from.
        3. Click "Fetch Annotations" to start the export process.
        4. After export, preview and download the annotations as a CSV file.

        **Note:** Only annotations with status "DONE" will be exported.
        """)
        api_key = st.text_input("Enter your Labelbox API Key:", type="password")
        cred_file = st.file_uploader("Or upload a Labelbox credentials JSON file", type=["json"])
        if cred_file is not None:
            creds = json.load(cred_file)
            api_key = creds.get("api_key", api_key)
    return api_key