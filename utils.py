"""
Visualization Utilities for AI Recycle Bin.
Draws bounding boxes and classification tags onto camera frames.
"""

import cv2
import numpy as np

# Color mappings (BGR format for OpenCV)
CLASS_COLORS = {
    "metal": (0, 215, 255),    # Gold / Yellow
    "paper": (50, 205, 50),    # Lime Green
    "plastic": (255, 144, 30), # Dodger Blue
    "trash": (0, 0, 255),      # Red
    "default": (255, 0, 255)   # Magenta
}


def visualize(image: np.ndarray, detection_result) -> np.ndarray:
    """
    Draw bounding boxes and class labels from MediaPipe ObjectDetectorResult.
    
    Args:
        image: BGR numpy image frame
        detection_result: MediaPipe detection result object
        
    Returns:
        Annotated BGR numpy image frame
    """
    if detection_result is None or not hasattr(detection_result, "detections"):
        return image

    annotated = image.copy()
    h, w, _ = annotated.shape

    for detection in detection_result.detections:
        # Get Bounding Box
        bbox = detection.bounding_box
        start_point = bbox.origin_x, bbox.origin_y
        end_point = bbox.origin_x + bbox.width, bbox.origin_y + bbox.height

        # Get Category Label & Score
        category = detection.categories[0]
        category_name = category.category_name.lower().strip()
        probability = round(category.score, 2)
        result_text = f"{category_name.upper()} ({int(probability * 100)}%)"

        # Determine color
        color = CLASS_COLORS.get(category_name, CLASS_COLORS["default"])

        # Draw Bounding Box
        cv2.rectangle(annotated, start_point, end_point, color, 3)

        # Draw Label Background Box
        (text_w, text_h), baseline = cv2.getTextSize(
            result_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
        )
        label_ymin = max(0, start_point[1] - text_h - 10)
        label_ymax = start_point[1]
        
        cv2.rectangle(
            annotated,
            (start_point[0], label_ymin),
            (start_point[0] + text_w + 10, label_ymax),
            color,
            -1
        )

        # Put Label Text
        cv2.putText(
            annotated,
            result_text,
            (start_point[0] + 5, label_ymax - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            cv2.LINE_AA
        )

    return annotated
