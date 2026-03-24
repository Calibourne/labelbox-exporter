import streamlit as st
from utils import normalize_annotations_yolo, create_yolo_zip_in_memory

STATUS_MAP = {
    "Done": "Done",
    "InReview": "In Review",
    "InRework": "In Rework",
    "ToLabel": "To Label"
}

def sidebar_ui():
    with st.sidebar:
        st.title("Labelbox Annotation Exporter")
        st.header("1. Connect")
        api_key = st.text_input("Enter your Labelbox API Key:", value=st.session_state.get('api_key', ""), type="password")
        cred_file = st.file_uploader("Or upload a Labelbox credentials JSON file", type=["json"])
        if cred_file is not None:
            import json
            try:
                creds = json.load(cred_file)
                api_key = creds.get("api_key", api_key)
            except json.JSONDecodeError:
                st.error("Credentials file is not valid JSON. Check the file format and re-upload.")
        st.session_state['api_key'] = api_key

def project_selection_ui(client):
    st.header("2. Project")
    try:
        projects = list(client.get_projects())
    except Exception as e:
        st.error(f"Could not fetch projects: {e}. Check your API key permissions and network connection.")
        return None
    if not projects:
        st.warning("No projects found for this API key.")
        return None
    project_names = [proj.name for proj in projects]
    selected_project_name = st.selectbox("Select a project to export:", project_names)
    matches = [proj for proj in projects if proj.name == selected_project_name]
    if not matches:
        st.error(f"Project '{selected_project_name}' not found. Refresh the page to reload the project list.")
        return None
    selected_project = matches[0]

    st.header("3. Fetch Statuses")
    selected_statuses = st.pills(
        "Select statuses to fetch:",
        options=list(STATUS_MAP.keys()),
        format_func=STATUS_MAP.get,
        selection_mode="multi",
        default=["Done"]
    )
    st.session_state['selected_statuses'] = selected_statuses

    if st.button("Fetch Annotations", use_container_width=True):
        st.session_state['fetch_triggered'] = True
    
    return selected_project

def export_controls_ui(selected_project):
    if 'exported_df' not in st.session_state:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.info("← Select a project and fetch annotations to get started.")
        return

    df = st.session_state['exported_df']
    fetched_statuses = st.session_state.get('fetched_statuses', [])

    st.header("① Fetched")
    status_counts = df['workflow_status'].value_counts()
    
    # Filter STATUS_MAP order to only those present in fetched_statuses
    display_statuses = [s for s in STATUS_MAP if s in fetched_statuses]
    
    cols = st.columns(len(display_statuses) + 1)
    for i, status in enumerate(display_statuses):
        cols[i].metric(STATUS_MAP[status], status_counts.get(status, 0))
    cols[-1].metric("Total", len(df))

    st.header("② Preview & Filter")
    active_filters = st.pills(
        "Filter by status:",
        options=fetched_statuses,
        format_func=STATUS_MAP.get,
        selection_mode="multi",
        default=fetched_statuses
    )
    
    filtered_df = df[df['workflow_status'].isin(active_filters)]
    st.write(f"Showing {len(filtered_df)} rows")
    st.dataframe(filtered_df.head(10), use_container_width=True)

    st.header("③ Export")
    st.write(f"Exporting {len(filtered_df)} rows")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        yolo_norm = st.button("Normalize for YOLO", use_container_width=True)

    if yolo_norm:
        try:
            ontology = selected_project.ontology()
            classes = ontology.tools()
            class_map = {tool.name: idx for idx, tool in enumerate(classes)}
        except Exception as e:
            st.error(f"Could not load project ontology: {e}.")
            class_map = {}
        
        # We work on a copy of filtered_df for normalization to avoid setting with copy warnings
        norm_df, skip_count = normalize_annotations_yolo(filtered_df.copy(), class_map)
        if skip_count:
            st.warning(f"{skip_count} annotation(s) were skipped due to errors during YOLO normalization.")
        
        yaml_info = {
            'nc': len(class_map.keys()),
            'names': list(class_map.keys())
        }

        try:
            zip_buffer = create_yolo_zip_in_memory(norm_df, yaml_info)
            with col2:
                st.download_button(
                    label="Download YOLO ZIP",
                    data=zip_buffer,
                    file_name=f"{selected_project.name}_yolo.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Could not create YOLO ZIP: {e}")

    if 'export_url' in st.session_state:
        st.markdown(f"[Download Raw NDJSON]({st.session_state['export_url']})")
