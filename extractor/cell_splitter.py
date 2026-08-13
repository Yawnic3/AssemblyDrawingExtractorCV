from pathlib import Path

import cv2
import numpy as np


COLUMN_NAMES = [
    "item",
    "part_name",
    "qty",
    "stock_name",
    "weight_kg",
    "rev",
]


def _group_positions(positions, max_gap=2):
    """
    Collapse adjacent detected line pixels into one coordinate.

    Example:
        [10, 11, 12, 50, 51]

    becomes:
        [11, 50]
    """

    positions = [int(p) for p in positions]

    if not positions:
        return []

    groups = [[positions[0]]]

    for position in positions[1:]:

        if position - groups[-1][-1] <= max_gap:
            groups[-1].append(position)

        else:
            groups.append([position])

    return [
        int(
            round(
                float(
                    np.mean(group)
                )
            )
        )
        for group in groups
    ]


def _crop_inside_lines(
    image,
    x1,
    y1,
    x2,
    y2,
    padding=6
):
    """
    Crop inside a table cell.

    Padding removes the actual grid lines from the
    resulting cell image, which will make OCR easier.
    """

    height, width = image.shape[:2]

    left = max(
        0,
        x1 + padding
    )

    top = max(
        0,
        y1 + padding
    )

    right = min(
        width,
        x2 - padding
    )

    bottom = min(
        height,
        y2 - padding
    )

    if right <= left or bottom <= top:

        raise ValueError(
            f"Invalid crop after padding: "
            f"({x1}, {y1}, {x2}, {y2})"
        )

    return image[
        top:bottom,
        left:right
    ]


def split_bom_cells(
    image_path,
    output_dir="output/cells",
    threshold=245
):
    """
    Split a detected BOM into individual cells.

    Expected structure:

        Bill of Material

        # | Part Name | Qty | Stock Name | Wt (kg) | Rev

        Row 1
        Row 2
        Row 3
        ...

    This function automatically determines:

        - column boundaries
        - row boundaries
        - title row
        - header row
        - number of data rows

    Returns structured information containing the
    generated cell image paths.
    """

    # ---------------------------------------------------------
    # Output directory
    # ---------------------------------------------------------

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # ---------------------------------------------------------
    # 1. Load detected BOM image
    # ---------------------------------------------------------

    image = cv2.imread(
        str(image_path)
    )

    if image is None:

        raise ValueError(
            f"Could not read image: {image_path}"
        )

    original = image.copy()

    # ---------------------------------------------------------
    # 2. Grayscale
    # ---------------------------------------------------------

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # ---------------------------------------------------------
    # 3. Threshold faint CAD lines
    #
    # White background -> black
    # CAD geometry/text -> white
    # ---------------------------------------------------------

    binary = cv2.threshold(
        gray,
        threshold,
        255,
        cv2.THRESH_BINARY_INV
    )[1]

    height, width = binary.shape

    # ---------------------------------------------------------
    # 4. Detect horizontal lines
    # ---------------------------------------------------------

    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (
            max(
                20,
                width // 30
            ),
            1
        )
    )

    horizontal_lines = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        horizontal_kernel
    )

    cv2.imwrite(
        str(
            output_dir /
            "_horizontal_lines.png"
        ),
        horizontal_lines
    )

    # ---------------------------------------------------------
    # 5. Detect vertical lines
    # ---------------------------------------------------------

    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (
            1,
            max(
                20,
                height // 20
            )
        )
    )

    vertical_lines = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        vertical_kernel
    )

    cv2.imwrite(
        str(
            output_dir /
            "_vertical_lines.png"
        ),
        vertical_lines
    )

    # ---------------------------------------------------------
    # 6. Find horizontal boundaries
    #
    # A real BOM horizontal line spans most of the
    # table width.
    # ---------------------------------------------------------

    row_strength = (
        horizontal_lines > 0
    ).sum(
        axis=1
    )

    horizontal_candidates = np.where(
        row_strength
        >= width * 0.70
    )[0]

    y_lines = _group_positions(
        horizontal_candidates,
        max_gap=2
    )

    # ---------------------------------------------------------
    # 7. Find vertical boundaries
    #
    # We expect:
    #
    # | # | Part | Qty | Stock | Weight | Rev |
    #
    # Six columns means seven boundaries.
    # ---------------------------------------------------------

    col_strength = (
        vertical_lines > 0
    ).sum(
        axis=0
    )

    vertical_candidates = np.where(
        col_strength
        >= height * 0.55
    )[0]

    x_lines = _group_positions(
        vertical_candidates,
        max_gap=2
    )

    # ---------------------------------------------------------
    # 8. Validate table structure
    # ---------------------------------------------------------

    if len(x_lines) != 7:

        raise ValueError(
            "Expected 7 vertical boundaries "
            "for 6 BOM columns, but detected "
            f"{len(x_lines)}: {x_lines}"
        )

    # Need at minimum:
    #
    # table top
    # title bottom
    # header bottom
    # first row bottom

    if len(y_lines) < 4:

        raise ValueError(
            "Not enough horizontal boundaries "
            "were detected. "
            f"Detected {len(y_lines)}: "
            f"{y_lines}"
        )

    # ---------------------------------------------------------
    # 9. Debug image
    #
    # RED  = column boundaries
    # BLUE = row boundaries
    # ---------------------------------------------------------

    debug = original.copy()

    for x in x_lines:

        cv2.line(
            debug,
            (
                x,
                0
            ),
            (
                x,
                height - 1
            ),
            (
                0,
                0,
                255
            ),
            2
        )

    for y in y_lines:

        cv2.line(
            debug,
            (
                0,
                y
            ),
            (
                width - 1,
                y
            ),
            (
                255,
                0,
                0
            ),
            2
        )

    cv2.imwrite(
        str(
            output_dir /
            "_detected_grid.png"
        ),
        debug
    )

    # ---------------------------------------------------------
    # 10. Extract title
    #
    # The title is one merged cell:
    #
    #           Bill of Material
    # ---------------------------------------------------------

    title_crop = _crop_inside_lines(
        original,

        x_lines[0],
        y_lines[0],

        x_lines[-1],
        y_lines[1],

        padding=6
    )

    title_path = (
        output_dir /
        "title.png"
    )

    cv2.imwrite(
        str(title_path),
        title_crop
    )

    # ---------------------------------------------------------
    # 11. Extract column headers
    # ---------------------------------------------------------

    header_dir = (
        output_dir /
        "header"
    )

    header_dir.mkdir(
        exist_ok=True
    )

    header_paths = {}

    for column_index, column_name in enumerate(
        COLUMN_NAMES
    ):

        x1 = x_lines[
            column_index
        ]

        x2 = x_lines[
            column_index + 1
        ]

        header_crop = _crop_inside_lines(
            original,

            x1,
            y_lines[1],

            x2,
            y_lines[2],

            padding=5
        )

        path = (
            header_dir /
            f"{column_index + 1:02d}_{column_name}.png"
        )

        cv2.imwrite(
            str(path),
            header_crop
        )

        header_paths[
            column_name
        ] = str(path)

    # ---------------------------------------------------------
    # 12. Extract data rows
    #
    # After the header, each consecutive pair of
    # horizontal lines represents one BOM data row.
    # ---------------------------------------------------------

    rows_dir = (
        output_dir /
        "rows"
    )

    rows_dir.mkdir(
        exist_ok=True
    )

    rows = []

    number_of_data_rows = (
        len(y_lines) - 3
    )

    for row_index in range(
        number_of_data_rows
    ):

        row_top = y_lines[
            row_index + 2
        ]

        row_bottom = y_lines[
            row_index + 3
        ]

        row_number = (
            row_index + 1
        )

        # Example:
        #
        # output/cells/rows/row_001/

        row_dir = (
            rows_dir /
            f"row_{row_number:03d}"
        )

        row_dir.mkdir(
            exist_ok=True
        )

        row_cells = {}

        # -----------------------------------------------------
        # Extract each of the six columns
        # -----------------------------------------------------

        for column_index, column_name in enumerate(
            COLUMN_NAMES
        ):

            x1 = x_lines[
                column_index
            ]

            x2 = x_lines[
                column_index + 1
            ]

            cell_crop = _crop_inside_lines(
                original,

                x1,
                row_top,

                x2,
                row_bottom,

                padding=6
            )

            cell_path = (
                row_dir /
                f"{column_index + 1:02d}_{column_name}.png"
            )

            cv2.imwrite(
                str(cell_path),
                cell_crop
            )

            row_cells[
                column_name
            ] = str(
                cell_path
            )

        rows.append(
            {
                "row_number":
                    row_number,

                "top":
                    row_top,

                "bottom":
                    row_bottom,

                "cells":
                    row_cells
            }
        )

    # ---------------------------------------------------------
    # 13. Return structured data
    # ---------------------------------------------------------

    result = {

        "title":
            str(title_path),

        "header":
            header_paths,

        "rows":
            rows,

        "x_lines":
            x_lines,

        "y_lines":
            y_lines,

        "column_names":
            COLUMN_NAMES,

        "data_row_count":
            number_of_data_rows
    }

    print(
        "\nCell splitting complete."
    )

    print(
        "Detected columns:",
        len(x_lines) - 1
    )

    print(
        "Detected data rows:",
        number_of_data_rows
    )

    print(
        "X boundaries:",
        x_lines
    )

    print(
        "Y boundaries:",
        y_lines
    )

    return result