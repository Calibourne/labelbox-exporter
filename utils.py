import pandas as pd
from annotation_wrapper import AnnotationWrapper
import io
import zipfile
import os
import yaml

def process_exported_data(parsed_data):
    if not parsed_data:
        raise ValueError("No annotation data was returned. The project may be empty or have no DONE annotations.")
    df = pd.json_normalize(parsed_data)
    if df.empty or len(df.columns) == 0:
        raise ValueError("Exported data is empty after parsing.")

    # Simplify column names
    simple_cols = [col.split('.')[-1] for col in df.columns]
    if len(set(simple_cols)) == len(simple_cols):
        df.columns = simple_cols
    else:
        import streamlit as st
        st.warning("Detected duplicate column names; keeping original names.")

    # Drop less useful columns
    drop_columns = [col for col in df.columns if col.endswith('_at') or col.endswith('_by')] + ['id', df.columns[-1]]
    keep_columns = ['width', 'height', 'duration', 'exif_rotation']

    for col in df.columns[:-2]:
        if col not in keep_columns:
            try:
                if df[col].nunique() <= 1:
                    drop_columns.append(col)
            except TypeError:
                pass  # columns containing lists/dicts can't be hashed — keep them

    # Unpack nested 'labels' column if present
    if 'labels' in df.columns:
        df = df.merge(df['labels'].apply(pd.Series), left_index=True, right_index=True).rename(columns={0: 'labels_unwrapped'})
        df = df.merge(df['labels_unwrapped'].apply(pd.Series), left_index=True, right_index=True)
        df = df.merge(df['annotations'].apply(pd.Series), left_index=True, right_index=True)
        df = df.merge(df['objects'].apply(pd.Series), left_index=True, right_index=True)

        drop_columns += ['labels', 'labels_unwrapped', 'annotations', 'objects', 'id_x', 'id_y']
        drop_columns += ['version', 'label_kind', 'classifications', 'relationships']

        # Process annotation columns indexed numerically
        cols = pd.Series(df.columns)
        annot_cols = cols[cols.apply(lambda x: isinstance(x, int))].to_list()

        annot_types = ['point', 'bounding_box', 'polygon']
        for i, annot in enumerate(annot_cols):
            annot_info = df[annot].apply(pd.Series)
            annot_type = pd.Series(annot_info.columns)
            type_list = annot_type[annot_type.isin(annot_types)].to_list()
            if not type_list:
                continue
            annot_type = type_list[0]
            annot_info = annot_info[['value', annot_type]].rename(columns={annot_type: f'{annot_type}_{i}', 'value': f'value_{i}'})
            annot_info[f'annotation_{i}'] = annot_info.apply(
                lambda row: {'annotation_type': annot_type, row[f'value_{i}']: row[f'{annot_type}_{i}']}, axis=1
            ).apply(AnnotationWrapper.wrap_dict)
            annot_info = annot_info[[f'annotation_{i}']]
            df = df.merge(annot_info, left_index=True, right_index=True)
            drop_columns.append(annot)

    df.drop(columns=drop_columns, inplace=True, errors='ignore')

    # Unpack AnnotationWrapper instances
    columns_with_dicts = [col for col in df.columns if df[col].apply(lambda x: isinstance(x, AnnotationWrapper)).any()]
    for col in columns_with_dicts:
        df[col] = df[col].apply(lambda x: x.unpack())

    return df


def normalize_annotations_yolo(df, class_map):
    skip_count = 0

    def safe_normalize(row, col):
        nonlocal skip_count
        try:
            val = row[col]
            return val.yolo_format(row['width'], row['height'], row.get('exif_rotation', 1), class_map)
        except Exception:
            skip_count += 1
            return ""

    for col in df.columns:
        if col.startswith('annotation_'):
            df[col] = df.apply(lambda row: safe_normalize(row, col), axis=1)

    annot_cols = [col for col in df.columns if col.startswith('annotation_')]
    if annot_cols:
        df['annotations_yolo'] = df[annot_cols].apply(
            lambda row: '\n'.join([str(ann) for ann in row if ann]), axis=1
        )
        df.drop(columns=annot_cols, inplace=True, errors='ignore')

    return df, skip_count

def create_yolo_zip_in_memory(df, yaml_info, image_id_col='external_id', anno_col='annotations_yolo'):
    # yaml_info: dictionary with keys 'train', 'val', 'nc', 'names', etc.
    if image_id_col not in df.columns:
        raise KeyError(f"Column '{image_id_col}' not found in export data. Cannot create label filenames.")

    # Create a BytesIO buffer
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zipf:
        # Add label files from DataFrame rows
        for _, row in df.iterrows():
            # Get image id without extension, use as label filename
            image_id = os.path.splitext(row[image_id_col])[0]
            label_filename = f"labels/{image_id}.txt"
            
            # Get YOLO annotations string (already multiple lines)
            annotations = row.get(anno_col, "")
            if not annotations or not isinstance(annotations, str):
                annotations = ""

            zipf.writestr(label_filename, annotations)

        # Create YAML content in-memory for YOLO config file
        yaml_content = yaml.dump(yaml_info)
        zipf.writestr("data.yaml", yaml_content)

    # Make sure to seek to start so data can be read from beginning
    zip_buffer.seek(0)
    return zip_buffer
