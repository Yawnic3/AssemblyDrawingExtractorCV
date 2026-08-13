from pathlib import Path

import cv2
import numpy as np


def _contiguous_runs(values):
    values = [int(v) for v in values]

    if not values:
        return []

    runs = []

    start = values[0]
    previous = values[0]

    for value in values[1:]:

        if value <= previous + 1:
            previous = value

        else:
            runs.append(
                (start, previous)
            )

            start = value
            previous = value

    runs.append(
        (start, previous)
    )

    return runs


def _cluster_horizontal_segments(
    segments,
    tolerance
):
    """
    Group horizontal lines that have roughly the
    same left and right endpoints.

    BOM rows repeatedly span the same width.
    """

    clusters = []

    # Longer lines first
    segments = sorted(
        segments,
        key=lambda s: s[2],
        reverse=True
    )

    for segment in segments:

        x, y, w, h = segment

        right = x + w - 1

        placed = False

        for cluster in clusters:

            median_left = int(
                np.median(
                    [
                        s[0]
                        for s in cluster
                    ]
                )
            )

            median_right = int(
                np.median(
                    [
                        s[0] + s[2] - 1
                        for s in cluster
                    ]
                )
            )

            same_left = (
                abs(
                    x - median_left
                )
                <= tolerance
            )

            same_right = (
                abs(
                    right - median_right
                )
                <= tolerance
            )

            if same_left and same_right:

                cluster.append(
                    segment
                )

                placed = True

                break

        if not placed:

            clusters.append(
                [segment]
            )

    return clusters


def _find_vertical_boundary_span(
    vertical_lines,
    target_x,
    repeated_y_min,
    repeated_y_max,
    search_radius,
    y_tolerance=4
):
    """
    Find the vertical line near target_x that spans
    all detected BOM rows.

    If multiple lines qualify, choose the shortest
    valid line. This helps reject drawing borders
    that extend much farther than the BOM itself.
    """

    height, width = (
        vertical_lines.shape
    )

    candidates = []

    x_start = max(
        0,
        target_x - search_radius
    )

    x_end = min(
        width,
        target_x
        + search_radius
        + 1
    )

    for x in range(
        x_start,
        x_end
    ):

        y_positions = np.where(
            vertical_lines[:, x] > 0
        )[0]

        runs = _contiguous_runs(
            y_positions
        )

        for y0, y1 in runs:

            covers_rows = (
                y0
                <= repeated_y_min
                + y_tolerance
                and
                y1
                >= repeated_y_max
                - y_tolerance
            )

            if not covers_rows:
                continue

            span_length = (
                y1 - y0 + 1
            )

            distance = abs(
                x - target_x
            )

            candidates.append(
                (
                    span_length,
                    distance,
                    x,
                    y0,
                    y1
                )
            )

    if not candidates:
        return None

    # Shortest qualifying vertical span first.
    #
    # Prevents giant drawing-border lines from
    # beating the actual BOM border.

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1]
        )
    )

    _, _, x, y0, y1 = (
        candidates[0]
    )

    return {
        "x": x,
        "y0": y0,
        "y1": y1
    }


def detect_table(
    image_path,
    output_dir="output"
):
    """
    Detect the exact Bill of Material table.

    Pipeline:

    1. Convert image to grayscale
    2. Threshold faint CAD geometry
    3. Extract horizontal lines
    4. Extract vertical lines
    5. Find repeated horizontal BOM rows
    6. Determine left/right table boundaries
    7. Determine top/bottom using BOTH vertical edges
    8. Crop exact BOM from original image
    """

    # -------------------------------------------------
    # Output directory
    # -------------------------------------------------

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # -------------------------------------------------
    # 1. Read image
    # -------------------------------------------------

    image = cv2.imread(
        str(image_path)
    )

    if image is None:

        raise ValueError(
            f"Could not read image: {image_path}"
        )

    original = image.copy()

    # -------------------------------------------------
    # 2. Grayscale
    # -------------------------------------------------

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    cv2.imwrite(
        str(
            output_dir
            / "01_gray.png"
        ),
        gray
    )

    # -------------------------------------------------
    # 3. Threshold
    #
    # Faint CAD geometry -> white
    # Background        -> black
    # -------------------------------------------------

    binary = cv2.threshold(
        gray,
        245,
        255,
        cv2.THRESH_BINARY_INV
    )[1]

    cv2.imwrite(
        str(
            output_dir
            / "02_binary.png"
        ),
        binary
    )

    height, width = (
        binary.shape
    )

    # -------------------------------------------------
    # 4. Horizontal lines
    # -------------------------------------------------

    horizontal_kernel = (
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (
                max(
                    20,
                    width // 30
                ),
                1
            )
        )
    )

    horizontal_lines = (
        cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            horizontal_kernel
        )
    )

    cv2.imwrite(
        str(
            output_dir
            / "03_horizontal.png"
        ),
        horizontal_lines
    )

    # -------------------------------------------------
    # 5. Vertical lines
    # -------------------------------------------------

    vertical_kernel = (
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (
                1,
                max(
                    20,
                    height // 20
                )
            )
        )
    )

    vertical_lines = (
        cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            vertical_kernel
        )
    )

    cv2.imwrite(
        str(
            output_dir
            / "04_vertical.png"
        ),
        vertical_lines
    )

    # -------------------------------------------------
    # 6. Combined grid for debugging
    # -------------------------------------------------

    grid = cv2.bitwise_or(
        horizontal_lines,
        vertical_lines
    )

    cv2.imwrite(
        str(
            output_dir
            / "05_grid.png"
        ),
        grid
    )

    # -------------------------------------------------
    # 7. Find horizontal line segments
    # -------------------------------------------------

    contours, _ = (
        cv2.findContours(
            horizontal_lines,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
    )

    minimum_line_length = max(
        80,
        int(
            width * 0.15
        )
    )

    maximum_line_thickness = max(
        25,
        height // 20
    )

    horizontal_segments = []

    for contour in contours:

        x, y, w, h = (
            cv2.boundingRect(
                contour
            )
        )

        # Ignore short garbage
        if w < minimum_line_length:
            continue

        # Ignore giant/thick objects
        if h > maximum_line_thickness:
            continue

        horizontal_segments.append(
            (
                x,
                y,
                w,
                h
            )
        )

    if not horizontal_segments:

        raise ValueError(
            "No horizontal table lines "
            "were detected."
        )

    # -------------------------------------------------
    # 8. Group lines sharing the same endpoints
    # -------------------------------------------------

    endpoint_tolerance = max(
        6,
        width // 250
    )

    clusters = (
        _cluster_horizontal_segments(
            horizontal_segments,
            endpoint_tolerance
        )
    )

    # A BOM should have several repeated rows.
    #
    # A sheet border generally does not have this
    # repeated same-width structure.

    valid_clusters = [
        cluster
        for cluster in clusters
        if len(cluster) >= 4
    ]

    if not valid_clusters:

        raise ValueError(
            "Could not find a repeated "
            "horizontal-line pattern "
            "for the BOM."
        )

    # Prefer:
    #
    # 1. Most repeated lines
    # 2. Widest group if tied

    valid_clusters.sort(
        key=lambda cluster: (
            len(cluster),

            float(
                np.median(
                    [
                        segment[2]
                        for segment
                        in cluster
                    ]
                )
            )
        ),
        reverse=True
    )

    table_cluster = (
        valid_clusters[0]
    )

    # -------------------------------------------------
    # 9. Estimate BOM left/right edges
    # -------------------------------------------------

    table_left = int(
        round(
            float(
                np.median(
                    [
                        segment[0]
                        for segment
                        in table_cluster
                    ]
                )
            )
        )
    )

    table_right = int(
        round(
            float(
                np.median(
                    [
                        segment[0]
                        + segment[2]
                        - 1

                        for segment
                        in table_cluster
                    ]
                )
            )
        )
    )

    # -------------------------------------------------
    # Horizontal BOM row positions
    # -------------------------------------------------

    repeated_line_ys = sorted(

        int(
            round(
                segment[1]
                +
                (
                    segment[3] - 1
                )
                / 2
            )
        )

        for segment
        in table_cluster
    )

    repeated_y_min = min(
        repeated_line_ys
    )

    repeated_y_max = max(
        repeated_line_ys
    )

    # -------------------------------------------------
    # 10. Locate actual vertical BOM boundaries
    # -------------------------------------------------

    search_radius = max(
        8,
        width // 200
    )

    left_boundary = (
        _find_vertical_boundary_span(
            vertical_lines,
            table_left,
            repeated_y_min,
            repeated_y_max,
            search_radius
        )
    )

    right_boundary = (
        _find_vertical_boundary_span(
            vertical_lines,
            table_right,
            repeated_y_min,
            repeated_y_max,
            search_radius
        )
    )

    boundaries = [

        boundary

        for boundary
        in (
            left_boundary,
            right_boundary
        )

        if boundary is not None
    ]

    # -------------------------------------------------
    # 11. Determine exact table top/bottom
    #
    # IMPORTANT FIX:
    #
    # Use the INTERSECTION of the two vertical
    # boundary spans.
    #
    # On your drawing:
    #
    # LEFT border:
    # starts at BOM top
    # continues way down into sheet grid
    #
    # RIGHT border:
    # starts at BOM top
    # stops at BOM bottom
    #
    # Therefore:
    #
    # top    = MAX(start positions)
    # bottom = MIN(end positions)
    #
    # This gives us only the area shared by both
    # actual BOM edges.
    # -------------------------------------------------

    if len(boundaries) == 2:

        table_top = max(
            boundary["y0"]
            for boundary
            in boundaries
        )

        table_bottom = min(
            boundary["y1"]
            for boundary
            in boundaries
        )

    elif len(boundaries) == 1:

        table_top = (
            boundaries[0]["y0"]
        )

        table_bottom = (
            boundaries[0]["y1"]
        )

    else:

        # Fallback if vertical boundaries fail.
        #
        # Estimate title-row height from spacing
        # between repeated horizontal lines.

        gaps = np.diff(
            repeated_line_ys
        )

        if len(gaps) > 0:

            estimated_title_height = int(
                np.median(
                    gaps
                )
            )

        else:

            estimated_title_height = 50

        table_top = max(
            0,
            repeated_y_min
            - estimated_title_height
        )

        table_bottom = (
            repeated_y_max
        )

    # -------------------------------------------------
    # Use exact vertical X coordinates
    # -------------------------------------------------

    if left_boundary is not None:

        table_left = (
            left_boundary["x"]
        )

    if right_boundary is not None:

        table_right = (
            right_boundary["x"]
        )

    # -------------------------------------------------
    # Safety check
    # -------------------------------------------------

    if table_bottom <= table_top:

        raise ValueError(
            "Detected invalid BOM "
            "vertical bounds."
        )

    # -------------------------------------------------
    # 12. Add tiny padding
    # -------------------------------------------------

    padding = 8

    x1 = max(
        0,
        table_left - padding
    )

    y1 = max(
        0,
        table_top - padding
    )

    x2 = min(
        width,
        table_right
        + 1
        + padding
    )

    y2 = min(
        height,
        table_bottom
        + 1
        + padding
    )

    # -------------------------------------------------
    # 13. Crop ORIGINAL image
    # -------------------------------------------------

    cropped_table = original[
        y1:y2,
        x1:x2
    ]

    cv2.imwrite(
        str(
            output_dir
            / "bom_detected.png"
        ),
        cropped_table
    )

    # -------------------------------------------------
    # 14. Draw green debug rectangle
    # -------------------------------------------------

    final_debug = (
        original.copy()
    )

    cv2.rectangle(
        final_debug,
        (
            x1,
            y1
        ),
        (
            x2 - 1,
            y2 - 1
        ),
        (
            0,
            255,
            0
        ),
        4
    )

    cv2.imwrite(
        str(
            output_dir
            / "06_final_region.png"
        ),
        final_debug
    )

    # -------------------------------------------------
    # 15. Return dimensions
    # -------------------------------------------------

    result = {

        "x": x1,

        "y": y1,

        "width":
            x2 - x1,

        "height":
            y2 - y1,

        "table_left":
            table_left,

        "table_right":
            table_right,

        "table_top":
            table_top,

        "table_bottom":
            table_bottom,

        "repeated_horizontal_lines":
            repeated_line_ys,

        "repeated_line_count":
            len(
                table_cluster
            )
    }

    print(
        "\nDetected BOM:"
    )

    print(
        "x =",
        result["x"]
    )

    print(
        "y =",
        result["y"]
    )

    print(
        "width =",
        result["width"]
    )

    print(
        "height =",
        result["height"]
    )

    print(
        "repeated horizontal lines =",
        result[
            "repeated_line_count"
        ]
    )

    return result