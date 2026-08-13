from pathlib import Path

from extractor.pdfreader import PDFReader
from extractor.table_detector import detect_table
from extractor.cell_splitter import split_bom_cells
from extractor.ocr_reader import OCRReader
from extractor.bom_reader import BOMParser
from extractor.assembly_parser import AssemblyParser


class PDFPartsPipeline:

    def __init__(
        self,
        pdf_path,
        output_root="output"
    ):
        self.pdf_path = Path(pdf_path)

        self.output_root = Path(
            output_root
        )

        self.output_root.mkdir(
            parents=True,
            exist_ok=True
        )

        # -------------------------------------------------
        # Load PDF
        # -------------------------------------------------

        self.reader = PDFReader(
            str(self.pdf_path)
        )

        # -------------------------------------------------
        # Load OCR models ONCE
        #
        # These objects are reused for every page.
        # -------------------------------------------------

        self.ocr_reader = OCRReader(
            min_confidence=0.30
        )

        self.bom_parser = BOMParser(
            ocr_reader=self.ocr_reader,
            low_confidence_threshold=0.90
        )

        self.assembly_parser = AssemblyParser(
            min_confidence=0.30
        )


    # =====================================================
    # PROCESS ONE PAGE
    # =====================================================

    def process_page(
        self,
        page_number
    ):
        """
        Process one zero-based PDF page.

        Returns:

        {
            "page": 1,
            "assembly": "MARCURIUS",
            "rows": [...]
        }
        """

        human_page_number = (
            page_number + 1
        )

        print()
        print("=" * 80)
        print(
            f"PROCESSING PAGE "
            f"{human_page_number}"
        )
        print("=" * 80)

        # -------------------------------------------------
        # Create page-specific output directory
        # -------------------------------------------------

        page_dir = (
            self.output_root
            / f"page_{human_page_number:03d}"
        )

        page_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # -------------------------------------------------
        # Get page size
        # -------------------------------------------------

        dimensions = (
            self.reader.get_page_dimensions(
                page_number
            )
        )

        width = dimensions["width"]
        height = dimensions["height"]

        # =================================================
        # BOM BRANCH
        # =================================================

        print(
            f"Page {human_page_number}: "
            "rendering BOM region..."
        )

        # Approximate upper-left search region.
        #
        # OpenCV determines the exact table inside it.

        bom_region = (
            width * 0.01,
            height * 0.01,
            width * 0.20,
            height * 0.25
        )

        bom_search_path = (
            page_dir
            / "bom_search.png"
        )

        self.reader.render_region(
            page_number=page_number,
            region=bom_region,
            output_path=str(
                bom_search_path
            ),
            scale=4
        )

        # -------------------------------------------------
        # Detect exact BOM
        # -------------------------------------------------

        bom_detector_dir = (
            page_dir
            / "bom_detection"
        )

        detect_table(
            str(bom_search_path),
            output_dir=str(
                bom_detector_dir
            )
        )

        exact_bom_path = (
            bom_detector_dir
            / "bom_detected.png"
        )

        # -------------------------------------------------
        # Split BOM into cells
        # -------------------------------------------------

        cells_dir = (
            page_dir
            / "cells"
        )

        split_result = (
            split_bom_cells(
                str(exact_bom_path),
                output_dir=str(
                    cells_dir
                )
            )
        )

        # -------------------------------------------------
        # OCR + parse BOM
        # -------------------------------------------------

        bom_rows = (
            self.bom_parser.parse(
                cells_dir / "rows"
            )
        )

        print(
            f"Page {human_page_number}: "
            f"{len(bom_rows)} BOM rows found."
        )

        # =================================================
        # ASSEMBLY BRANCH
        # =================================================

        print(
            f"Page {human_page_number}: "
            "extracting assembly..."
        )

        title_region = (
            width * 0.72,
            height * 0.78,
            width,
            height
        )

        title_path = (
            page_dir
            / "title_block.png"
        )

        self.reader.render_region(
            page_number=page_number,
            region=title_region,
            output_path=str(
                title_path
            ),
            scale=4
        )

        assembly_result = (
            self.assembly_parser.extract(
                str(title_path),

                debug_output_path=str(
                    page_dir
                    / "assembly_debug.png"
                )
            )
        )

        assembly = (
            assembly_result[
                "assembly"
            ]
        )

        print(
            f"Page {human_page_number}: "
            f"ASSEMBLY = {assembly}"
        )

        # =================================================
        # ASSOCIATE ASSEMBLY WITH BOM
        # =================================================

        final_rows = []

        for row in bom_rows:

            final_row = {
                "page":
                    human_page_number,

                "assembly":
                    assembly,

                "item":
                    row["item"],

                "part_name":
                    row["part_name"],

                "qty":
                    row["qty"],

                "stock_name":
                    row["stock_name"],

                "weight_kg":
                    row["weight_kg"],

                "rev":
                    row["rev"],

                "warnings":
                    row["warnings"],

                "confidence":
                    row["confidence"]
            }

            final_rows.append(
                final_row
            )

        return {
            "page":
                human_page_number,

            "assembly":
                assembly,

            "assembly_confidence":
                assembly_result[
                    "confidence"
                ],

            "rows":
                final_rows
        }


    # =====================================================
    # PROCESS ENTIRE PDF
    # =====================================================

    def process_all_pages(
        self
    ):
        """
        Process every page.

        A bad page does not kill the entire job.
        Errors are recorded for later review.
        """

        all_rows = []
        errors = []

        page_count = (
            self.reader.get_page_count()
        )

        print()
        print(
            f"PDF contains "
            f"{page_count} pages."
        )

        for page_number in range(
            page_count
        ):

            try:

                result = (
                    self.process_page(
                        page_number
                    )
                )

                all_rows.extend(
                    result["rows"]
                )

            except Exception as error:

                human_page = (
                    page_number + 1
                )

                print()
                print(
                    f"ERROR ON PAGE "
                    f"{human_page}:"
                )

                print(error)

                errors.append(
                    {
                        "page":
                            human_page,

                        "error":
                            str(error)
                    }
                )

        return {
            "rows":
                all_rows,

            "errors":
                errors
        }


    # =====================================================
    # CLEANUP
    # =====================================================

    def close(
        self
    ):
        self.reader.close()