from pathlib import Path


class BOMParser:
    """
    Converts OCR'd BOM cell images into structured,
    validated Python records.
    """

    def __init__(
        self,
        ocr_reader,
        low_confidence_threshold=0.90
    ):
        self.ocr = ocr_reader
        self.low_confidence_threshold = (
            low_confidence_threshold
        )


    # =========================================================
    # TYPE CONVERSION
    # =========================================================

    def _to_int(
        self,
        value
    ):
        """
        Convert OCR text to integer.

        Returns None if conversion fails.
        """

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return int(value)

        except ValueError:
            return None


    def _to_number(
        self,
        value
    ):
        """
        Convert OCR weight text into int/float.

        Examples:

            "378"   -> 378
            "12.5"  -> 12.5
            ""      -> None
        """

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:

            number = float(value)

            # Keep whole numbers as ints.
            if number.is_integer():
                return int(number)

            return number

        except ValueError:
            return None


    # =========================================================
    # OCR ONE ROW
    # =========================================================

    def _read_row(
        self,
        row_dir
    ):
        """
        OCR every cell in a row directory.

        Expected files:

            01_item.png
            02_part_name.png
            03_qty.png
            04_stock_name.png
            05_weight_kg.png
            06_rev.png
        """

        field_files = {
            "item":
                row_dir / "01_item.png",

            "part_name":
                row_dir / "02_part_name.png",

            "qty":
                row_dir / "03_qty.png",

            "stock_name":
                row_dir / "04_stock_name.png",

            "weight_kg":
                row_dir / "05_weight_kg.png",

            "rev":
                row_dir / "06_rev.png",
        }

        raw_results = {}

        for field, path in field_files.items():

            if not path.exists():

                raise FileNotFoundError(
                    f"Missing BOM cell: {path}"
                )

            result = self.ocr.read_cell(
                path,
                field=field
            )

            raw_results[field] = result

        return raw_results


    # =========================================================
    # VALIDATION
    # =========================================================

    def _validate_row(
        self,
        row_number,
        raw
    ):
        """
        Convert OCR strings to final values and generate
        warnings for anything suspicious.
        """

        warnings = []

        # -----------------------------------------------------
        # Item
        # -----------------------------------------------------

        item = self._to_int(
            raw["item"]["text"]
        )

        item_confidence = (
            raw["item"]["confidence"]
        )

        if item is None:

            warnings.append(
                "Could not parse item number."
            )

        elif (
            item_confidence
            < self.low_confidence_threshold
        ):

            warnings.append(
                f"Low item confidence: "
                f"{item_confidence:.3f}"
            )

        # -----------------------------------------------------
        # Part name
        # -----------------------------------------------------

        part_name = (
            raw["part_name"]["text"]
            .strip()
        )

        if not part_name:

            warnings.append(
                "Part name is empty."
            )

        # -----------------------------------------------------
        # Qty
        # -----------------------------------------------------

        qty = self._to_int(
            raw["qty"]["text"]
        )

        if qty is None:

            warnings.append(
                "Could not parse quantity."
            )

        elif qty < 0:

            warnings.append(
                f"Invalid quantity: {qty}"
            )

        # -----------------------------------------------------
        # Stock name
        # -----------------------------------------------------

        stock_name = (
            raw["stock_name"]["text"]
            .strip()
        )

        # -----------------------------------------------------
        # Weight
        # -----------------------------------------------------

        weight_kg = self._to_number(
            raw["weight_kg"]["text"]
        )

        if (
            raw["weight_kg"]["text"]
            and
            weight_kg is None
        ):

            warnings.append(
                "Could not parse weight."
            )

        # -----------------------------------------------------
        # Revision
        #
        # Empty revision is perfectly valid.
        # -----------------------------------------------------

        rev = (
            raw["rev"]["text"]
            .strip()
        )

        return {
            "row_number":
                row_number,

            "item":
                item,

            "part_name":
                part_name,

            "qty":
                qty,

            "stock_name":
                stock_name,

            "weight_kg":
                weight_kg,

            "rev":
                rev,

            "confidence": {
                field:
                    raw[field]["confidence"]

                for field in raw
            },

            "raw_ocr": {
                field:
                    raw[field]["raw_text"]

                for field in raw
            },

            "warnings":
                warnings
        }


    # =========================================================
    # ITEM-SEQUENCE RECOVERY
    # =========================================================

    def _recover_item_numbers(
        self,
        rows
    ):
        """
        Recover a bad OCR item number ONLY when a very clear
        sequential pattern has already been established.

        Example:

            1
            2
            3
            4
            5
            6
            7
            00  <- OCR error

        becomes:

            8

        We record the correction instead of silently changing it.
        """

        if len(rows) < 2:
            return

        # -----------------------------------------------------
        # Determine whether the good rows establish:
        #
        # item number == physical row number
        # -----------------------------------------------------

        good_matches = 0
        good_rows = 0

        for row in rows:

            item = row["item"]

            confidence = (
                row["confidence"]["item"]
            )

            if (
                item is None
                or confidence
                < self.low_confidence_threshold
            ):
                continue

            good_rows += 1

            if item == row["row_number"]:
                good_matches += 1

        # We only use sequence recovery when essentially
        # every trustworthy row proves the sequence.

        sequence_is_established = (
            good_rows >= 2
            and
            good_matches == good_rows
        )

        if not sequence_is_established:
            return

        # -----------------------------------------------------
        # Correct suspicious item cells
        # -----------------------------------------------------

        for row in rows:

            expected_item = (
                row["row_number"]
            )

            current_item = (
                row["item"]
            )

            confidence = (
                row["confidence"]["item"]
            )

            suspicious = (
                current_item != expected_item
                and
                confidence
                < self.low_confidence_threshold
            )

            if not suspicious:
                continue

            original = current_item

            row["item"] = (
                expected_item
            )

            row["warnings"].append(
                f"Item OCR corrected from "
                f"{original!r} to "
                f"{expected_item} using "
                f"established row sequence."
            )


    # =========================================================
    # PUBLIC METHOD
    # =========================================================

    def parse(
        self,
        rows_directory
    ):
        """
        Parse every BOM row.

        Returns:

        [
            {
                "item": 1,
                "part_name": "BOTTOM PARTS",
                "qty": 1,
                ...
            },
            ...
        ]
        """

        rows_directory = Path(
            rows_directory
        )

        if not rows_directory.exists():

            raise FileNotFoundError(
                f"Rows directory not found: "
                f"{rows_directory}"
            )

        row_dirs = sorted(
            rows_directory.glob(
                "row_*"
            )
        )

        if not row_dirs:

            raise ValueError(
                "No BOM rows were found."
            )

        parsed_rows = []

        # -----------------------------------------------------
        # OCR + validate
        # -----------------------------------------------------

        for row_number, row_dir in enumerate(
            row_dirs,
            start=1
        ):

            raw = self._read_row(
                row_dir
            )

            parsed = self._validate_row(
                row_number,
                raw
            )

            parsed_rows.append(
                parsed
            )

        # -----------------------------------------------------
        # Recover obvious item-number OCR errors
        # -----------------------------------------------------

        self._recover_item_numbers(
            parsed_rows
        )

        return parsed_rows