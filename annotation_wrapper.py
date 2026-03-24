from copy import deepcopy
import json
import numpy as np

class AnnotationWrapper:
    def __init__(self, annotation: dict | list):
        self.annotation: dict | list = annotation

    def unpack(self):
        temp = deepcopy(self.annotation)
        annot_type = temp.pop('annotation_type', None)
        if not temp:
            return self
        cls, annot = temp.popitem()  # Expect only one class per annotation dict, e.g., 'nose'

        if annot is None or annot is np.nan:
            self.annotation[cls] = None
            return self

        if annot_type == 'bounding_box':
            box = annot
            x = box.get('x')
            y = box.get('y')
            width = box.get('width')
            height = box.get('height')
            self.annotation[cls] = [x, y, width, height]

        elif annot_type == 'polygon':
            points = annot
            if not points or not isinstance(points, list):
                self.annotation[cls] = None
                return self
            coords = []
            for pt in points:
                if pt.get('x') is None or pt.get('y') is None:
                    continue
                coords.append([pt['x'], pt['y']])
            self.annotation[cls] = coords

        elif annot_type == 'point':
            point = annot
            x = point.get('x')
            y = point.get('y')
            self.annotation[cls] = [x, y]

        return self

    def yolo_format(self, img_width, img_height, rotation_code, class_map):
        annot_type = self.annotation.get('annotation_type')
        annot_classes = self.annotation.copy()
        annot_classes.pop('annotation_type', None)

        if not img_width or not img_height:
            return ""

        if not annot_classes:
            return ""

        cls, annot = next(iter(annot_classes.items()))
        if not isinstance(annot, list):
            return ""

        if annot_type == 'bounding_box':
            if len(annot) != 4:
                return ""
            x, y, width, height = annot
            if None in (x, y, width, height):
                return ""

            # Normalize coordinates
            x_center = (x + width / 2) / img_width
            y_center = (y + height / 2) / img_height
            width_norm = width / img_width
            height_norm = height / img_height

            coords = ""
            if rotation_code == 1:  # No rotation
                coords = f"{x_center:.6f} {y_center:.6f} {width_norm:.6f} {height_norm:.6f}"
            if rotation_code == 3:  # 180 degrees
                coords = f"{1 - x_center:.6f} {1 - y_center:.6f} {width_norm:.6f} {height_norm:.6f}"
            if rotation_code == 6:  # 90 degrees clockwise
                coords = f"{1 - y_center:.6f} {x_center:.6f} {height_norm:.6f} {width_norm:.6f}"
            if rotation_code == 8:  # 90 degrees counter-clockwise
                coords = f"{y_center:.6f} {1 - x_center:.6f} {height_norm:.6f} {width_norm:.6f}"

            class_id = class_map.get(cls)
            if class_id is None:
                return ""
            return f"{class_id} {coords}"

        elif annot_type == 'polygon':
            points = annot
            if not points or not isinstance(points, list):
                return ""

            polygon_coords = ""
            for x, y in points:
                normalized_x = x / img_width
                normalized_y = y / img_height
                coords = f""
                if rotation_code == 1:  # No rotation
                    coords = f"{normalized_x:.6f} {normalized_y:.6f}"
                if rotation_code == 3:  # 180 degrees
                    coords = f"{1 - normalized_x:.6f} {1 - normalized_y:.6f}"
                if rotation_code == 6:  # 90 degrees clockwise
                    coords = f"{1 - normalized_y:.6f} {normalized_x:.6f}"
                if rotation_code == 8:  # 90 degrees counter-clockwise
                    coords = f"{normalized_y:.6f} {1 - normalized_x:.6f}"
                if coords:
                    polygon_coords += f" {coords}"
            class_id = class_map.get(cls)
            if class_id is None:
                return ""
            return f"{class_id}{polygon_coords}"

        elif annot_type == 'point':
            if len(annot) != 2:
                return ""
            x, y = annot
            if None in (x, y):
                return ""
            x_norm = x / img_width
            y_norm = y / img_height
            coords = ""
            if rotation_code == 1:  # No rotation
                coords = f"{x_norm:.6f} {y_norm:.6f}"
            if rotation_code == 3:  # 180 degrees
                coords = f"{1 - x_norm:.6f} {1 - y_norm:.6f}"
            if rotation_code == 6:  # 90 degrees clockwise
                coords = f"{1 - y_norm:.6f} {x_norm:.6f}"
            if rotation_code == 8:  # 90 degrees counter-clockwise
                coords = f"{y_norm:.6f} {1 - x_norm:.6f}"
            class_id = class_map.get(cls)
            if class_id is None:
                return ""
            return f"{class_id} {coords}"

        else:
            raise NotImplementedError(f"YOLO format conversion not implemented for annotation type: {annot_type}")

    def __repr__(self):
        return json.dumps(self.annotation, indent=2)

    def __str__(self):
        return json.dumps(self.annotation)

    def __getitem__(self, key):
        return self.annotation[key]

    def to_dict(self):
        return self.annotation

    @staticmethod
    def wrap_dict(other):
        if isinstance(other, (dict, list)):
            return AnnotationWrapper(other)
        return other

