from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment


def export_to_excel(
    rows,
    errors,
    output_path="output/master_bom.xlsx"
):
    """
    Export extracted BOM records into Excel.

    Creates:

        Master BOM
        Extraction Errors
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # -----------------------------------------------------
    # Flatten BOM rows
    # -----------------------------------------------------

    excel_rows = []
    

    for row in rows:
        

        warnings = row.get(
            "warnings",
            []
        )

        confidence = row.get(
            "confidence",
            {}
        )

        excel_rows.append(
            {
                "Page":
                    row["page"],

                "Assembly":
                    row["assembly"],

                "Item":
                    row["item"],

                "Part Name":
                    row["part_name"],

                "Qty":
                    row["qty"],

                "Stock Name":
                    row["stock_name"],

                "Weight (kg)":
                    row["weight_kg"],

                "Rev":
                    row["rev"],

                "Warnings":
                    " | ".join(
                        warnings
                    ),

                "Item Confidence":
                    confidence.get(
                        "item"
                    ),

                "Part Confidence":
                    confidence.get(
                        "part_name"
                    ),

                "Qty Confidence":
                    confidence.get(
                        "qty"
                    ),

                "Stock Confidence":
                    confidence.get(
                        "stock_name"
                    ),

                "Weight Confidence":
                    confidence.get(
                        "weight_kg"
                    ),
                "BOM Crop %":
                    round(
                        row.get(
                            "bom_crop_ratio",
                            0
                        ) * 100
                    ),                    
            }
            
        )

    bom_df = pd.DataFrame(
        excel_rows
    )

    errors_df = pd.DataFrame(
        errors
    )

    # -----------------------------------------------------
    # Write workbook
    # -----------------------------------------------------

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl"
    ) as writer:

        bom_df.to_excel(
            writer,
            sheet_name="Master BOM",
            index=False
        )

        errors_df.to_excel(
            writer,
            sheet_name="Extraction Errors",
            index=False
        )

    # -----------------------------------------------------
    # Format workbook
    # -----------------------------------------------------

    workbook = load_workbook(
        output_path
    )

    bom_sheet = workbook[
        "Master BOM"
    ]

    # Freeze header.
    bom_sheet.freeze_panes = "A2"

    # Enable filters.
    bom_sheet.auto_filter.ref = (
        bom_sheet.dimensions
    )

    # Bold header.
    for cell in bom_sheet[1]:

        cell.font = Font(
            bold=True
        )

        cell.alignment = Alignment(
            horizontal="center"
        )

    # Column widths.
    widths = {
        "A": 10,
        "B": 24,
        "C": 10,
        "D": 30,
        "E": 10,
        "F": 25,
        "G": 15,
        "H": 10,
        "I": 55,
        "J": 18,
        "K": 18,
        "L": 18,
        "M": 18,
        "N": 20,
    }

    for column, width in (
        widths.items()
    ):

        bom_sheet.column_dimensions[
            column
        ].width = width

    # Format error sheet.
    error_sheet = workbook[
        "Extraction Errors"
    ]

    for cell in error_sheet[1]:

        cell.font = Font(
            bold=True
        )

    error_sheet.column_dimensions[
        "A"
    ].width = 12

    error_sheet.column_dimensions[
        "B"
    ].width = 80

    workbook.save(
        output_path
    )

    print()
    print(
        f"Excel saved to: "
        f"{output_path}"
    )