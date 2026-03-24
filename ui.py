import streamlit as st
from utils import normalize_annotations_yolo, create_yolo_zip_in_memory

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
            import json
            try:
                creds = json.load(cred_file)
                api_key = creds.get("api_key", api_key)
            except json.JSONDecodeError:
                st.error("Credentials file is not valid JSON. Check the file format and re-upload.")
        st.session_state['api_key'] = api_key

def project_selection_ui(client):
    with st.expander("Select Project to Export From"):
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

        with st.expander("Preview Project Metadata"):
            st.write(selected_project)
    return selected_project

def export_controls_ui(selected_project):
    if 'exported_df' in st.session_state:
        with st.expander("Preview Exported Annotations"):
            st.dataframe(st.session_state['exported_df'].head(10))
        # with st.expander("Select Columns and Download CSV"):
        #     selected_columns = st.multiselect(
        #         "Select columns to export",
        #         st.session_state['exported_df'].columns.tolist(),
        #         default=st.session_state['exported_df'].columns.tolist()
        #     )

        try:
            ontology = selected_project.ontology()
            classes = ontology.tools()
            class_map = {tool.name: idx for idx, tool in enumerate(classes)}
        except Exception as e:
            st.error(f"Could not load project ontology: {e}. YOLO normalization requires a configured ontology.")
            class_map = {}
        if not class_map:
            st.warning("No classes found in ontology — YOLO output will have no class IDs.")

        yolo_norm = st.button("Normalize Annotations for YOLO")

        if yolo_norm:
            df = st.session_state['exported_df']
            df, skip_count = normalize_annotations_yolo(df, class_map)
            if skip_count:
                st.warning(f"{skip_count} annotation(s) were skipped due to errors during YOLO normalization.")
            st.session_state['exported_df'] = df

            yaml_info = {
                'train': 'path/to/train/images',
                'val': 'path/to/val/images',
                'nc': len(class_map.keys()),
                'names': list(class_map.keys())
            }

            try:
                zip_buffer = create_yolo_zip_in_memory(df, yaml_info)
            except KeyError as e:
                st.error(f"Could not create YOLO ZIP: {e}")
                return

            st.download_button(
                label="Download YOLO Annotations ZIP",
                data=zip_buffer,
                file_name=f"{selected_project.name}_yolo_annotations.zip",
                mime="application/zip"
            )


            # Update selected_columns to remove dropped annotation columns
            # selected_columns = [col for col in selected_columns if col in df.columns]

        # if selected_columns:
        #     # Filter again with updated columns
        #     filtered_df = st.session_state['exported_df'][selected_columns]
        #     st.dataframe(filtered_df.head(10))
        #     csv_data = filtered_df.to_csv(index=False)
        #     st.download_button(
        #         label="Download Custom Export CSV",
        #         data=csv_data,
        #         file_name=f"{selected_project.name}_custom_export.csv",
        #         mime="text/csv"
        #     )


        if 'export_url' in st.session_state:
            st.markdown(f"[Download Full Raw Export (NDJSON)]({st.session_state['export_url']})")
