from pathlib import Path

import cv2

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
        # Open PDF once
        # -------------------------------------------------

        self.reader = PDFReader(
            str(self.pdf_path)
        )

        # -------------------------------------------------
        # Load OCR once
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
    # DYNAMIC BOM DETECTION
    # =====================================================

    def _find_complete_bom(
        self,
        page_number,
        page_dir,
        width,
        height
    ):
        """
        Dynamically expand the BOM search region until
        the detected table is no longer close to the
        bottom of the rendered crop.

        This prevents long BOMs from being silently
        truncated.

        Returns:

        {
            "bom_path": Path(...),
            "detection": {...},
            "crop_ratio": 0.45
        }
        """

        # -------------------------------------------------
        # Increasing search heights.
        #
        # Short BOMs should succeed immediately.
        # Very long BOMs can grow to 75% of the page.
        # -------------------------------------------------

        crop_ratios = [
            0.15,
            0.25,
            0.35,
            0.45,
            0.60,
            0.75,
        ]

        # -------------------------------------------------
        # If table bottom is inside the bottom 7% of the
        # search image, assume it may be clipped.
        # -------------------------------------------------

        safe_bottom_margin_ratio = 0.07

        last_error = None

        for attempt_number, crop_ratio in enumerate(
            crop_ratios,
            start=1
        ):

            print(
                f"Page {page_number + 1}: "
                f"BOM attempt {attempt_number} "
                f"using {crop_ratio:.0%} page height..."
            )

            # =============================================
            # Attempt-specific directory
            # =============================================

            attempt_dir = (
                page_dir
                / "bom_attempts"
                / f"attempt_{attempt_number:02d}"
            )

            attempt_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            # =============================================
            # Render larger top-left area
            # =============================================

            bom_region = (
                width * 0.01,
                height * 0.01,
                width * 0.20,
                height * crop_ratio
            )

            search_path = (
                attempt_dir
                / "bom_search.png"
            )

            self.reader.render_region(
                page_number=page_number,
                region=bom_region,
                output_path=str(search_path),
                scale=4
            )

            # =============================================
            # Try exact table detection
            # =============================================

            detection_dir = (
                attempt_dir
                / "detection"
            )

            try:

                detection = detect_table(
                    str(search_path),
                    output_dir=str(
                        detection_dir
                    )
                )

            except Exception as error:

                last_error = error

                print(
                    f"Page {page_number + 1}: "
                    f"detection failed at "
                    f"{crop_ratio:.0%}: {error}"
                )

                # Search area may simply be too short.
                # Try the next larger one.
                continue

            # =============================================
            # Read search-image dimensions
            # =============================================

            search_image = cv2.imread(
                str(search_path)
            )

            if search_image is None:

                raise ValueError(
                    f"Could not read rendered BOM search "
                    f"image: {search_path}"
                )

            search_height = (
                search_image.shape[0]
            )

            # =============================================
            # Determine detected table bottom
            # =============================================

            if "table_bottom" in detection:

                table_bottom = int(
                    detection["table_bottom"]
                )

            else:

                # Fallback for older detector versions.
                table_bottom = int(
                    detection["y"]
                    +
                    detection["height"]
                )

            # =============================================
            # Calculate remaining space below table
            # =============================================

            pixels_below_table = (
                search_height
                - table_bottom
            )

            bottom_margin_ratio = (
                pixels_below_table
                / search_height
            )

            print(
                f"Page {page_number + 1}: "
                f"table bottom margin = "
                f"{bottom_margin_ratio:.1%}"
            )

            # =============================================
            # Additional check:
            #
            # Look at final repeated horizontal line.
            #
            # If it's also near the bottom, that's another
            # strong sign that the BOM continues beyond
            # our crop.
            # =============================================

            repeated_lines = detection.get(
                "repeated_horizontal_lines",
                []
            )

            repeated_line_near_bottom = False

            if repeated_lines:

                final_horizontal_line = max(
                    repeated_lines
                )

                final_line_margin = (
                    search_height
                    - final_horizontal_line
                )

                final_line_margin_ratio = (
                    final_line_margin
                    / search_height
                )

                repeated_line_near_bottom = (
                    final_line_margin_ratio
                    < safe_bottom_margin_ratio
                )

                print(
                    f"Page {page_number + 1}: "
                    f"last BOM row-line margin = "
                    f"{final_line_margin_ratio:.1%}"
                )

            # =============================================
            # Is crop probably truncated?
            # =============================================

            table_near_bottom = (
                bottom_margin_ratio
                < safe_bottom_margin_ratio
            )

            probably_clipped = (
                table_near_bottom
                or repeated_line_near_bottom
            )

            # =============================================
            # If it looks clipped, expand and retry.
            # =============================================

            if probably_clipped:

                print(
                    f"Page {page_number + 1}: "
                    "BOM may be clipped. "
                    "Expanding search region..."
                )

                continue

            # =============================================
            # SUCCESS
            # =============================================

            exact_bom_path = (
                detection_dir
                / "bom_detected.png"
            )

            if not exact_bom_path.exists():

                raise FileNotFoundError(
                    f"Detector reported success but "
                    f"bom_detected.png was not created: "
                    f"{exact_bom_path}"
                )

            print(
                f"Page {page_number + 1}: "
                f"complete BOM found using "
                f"{crop_ratio:.0%} page height."
            )

            return {
                "bom_path":
                    exact_bom_path,

                "detection":
                    detection,

                "crop_ratio":
                    crop_ratio,

                "bottom_margin_ratio":
                    bottom_margin_ratio
            }

        # =================================================
        # Every search size failed
        # =================================================

        if last_error is not None:

            raise RuntimeError(
                f"Could not locate a complete BOM after "
                f"expanding search area to "
                f"{crop_ratios[-1]:.0%} of page height. "
                f"Last detector error: {last_error}"
            )

        raise RuntimeError(
            f"BOM still appeared clipped after expanding "
            f"search area to {crop_ratios[-1]:.0%} "
            f"of page height."
        )


    # =====================================================
    # PROCESS ONE PAGE
    # =====================================================

    def process_page(
        self,
        page_number
    ):
        """
        Process one PDF page.

        page_number is zero-based.
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
        # Page-specific output directory
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
        # Page dimensions
        # -------------------------------------------------

        dimensions = (
            self.reader.get_page_dimensions(
                page_number
            )
        )

        width = dimensions["width"]
        height = dimensions["height"]

        # =================================================
        # BOM
        # =================================================

        print(
            f"Page {human_page_number}: "
            "finding complete BOM..."
        )

        bom_result = (
            self._find_complete_bom(
                page_number=page_number,
                page_dir=page_dir,
                width=width,
                height=height
            )
        )

        exact_bom_path = (
            bom_result["bom_path"]
        )

        # -------------------------------------------------
        # Split into cells
        # -------------------------------------------------

        cells_dir = (
            page_dir
            / "cells"
        )

        split_result = split_bom_cells(
            str(exact_bom_path),
            output_dir=str(
                cells_dir
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
        # ASSEMBLY
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
        # COMBINE
        # =================================================

        final_rows = []

        for row in bom_rows:

            final_rows.append(
                {
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
                        row["confidence"],

                    # Useful debugging metadata
                    "bom_crop_ratio":
                        bom_result[
                            "crop_ratio"
                        ]
                }
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

            "bom_crop_ratio":
                bom_result[
                    "crop_ratio"
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

        Errors on individual pages do not terminate
        the whole PDF.
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
                    "!" * 80
                )

                print(
                    f"ERROR ON PAGE "
                    f"{human_page}"
                )

                print(
                    str(error)
                )

                print(
                    "!" * 80
                )

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