import re

import cv2
import numpy as np
from paddleocr import PaddleOCR


class OCRReader:
    """
    Reads individual BOM cell images using PaddleOCR.

    Example:

        02_part_name.png
                ↓
        OCR detects:
            BOTTOM
            PARTS
                ↓
        "BOTTOM PARTS"
    """

    def __init__(
        self,
        min_confidence=0.30
    ):
        self.min_confidence = min_confidence

        print("Loading PaddleOCR model...")

        self.ocr = PaddleOCR(
            lang="en",

            # We already know engineering drawings
            # are correctly oriented.
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,

            # Force CPU because we installed
            # CPU PaddlePaddle.
            device="cpu",

            # Ignore extremely low-confidence text.
            text_rec_score_thresh=min_confidence
        )

        print("PaddleOCR ready.")


    # =========================================================
    # IMAGE PREPROCESSING
    # =========================================================

    def _prepare_image(
        self,
        image_path
    ):
        """
        Prepare faint CAD text for PaddleOCR.

        Output must be a 3-channel BGR image:
            (height, width, 3)
        """

        image = cv2.imread(
            str(image_path)
        )

        if image is None:
            raise ValueError(
                f"Could not read image: {image_path}"
            )

        # -----------------------------------------------------
        # 1. Convert to grayscale
        # -----------------------------------------------------

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # -----------------------------------------------------
        # 2. Strengthen faint CAD text
        #
        # Text / geometry -> black
        # Background      -> white
        # -----------------------------------------------------

        clean = cv2.threshold(
            gray,
            245,
            255,
            cv2.THRESH_BINARY
        )[1]

        # -----------------------------------------------------
        # 3. Enlarge tiny CAD characters
        # -----------------------------------------------------

        scale = 2

        clean = cv2.resize(
            clean,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

        # -----------------------------------------------------
        # 4. Add whitespace around cell
        # -----------------------------------------------------

        clean = cv2.copyMakeBorder(
            clean,
            20,
            20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=255
        )

        # -----------------------------------------------------
        # 5. IMPORTANT:
        #
        # Paddle's detector expects:
        #
        #     height, width, channels
        #
        # clean is currently:
        #
        #     height, width
        #
        # Convert it back to 3-channel BGR.
        # -----------------------------------------------------

        clean = cv2.cvtColor(
            clean,
            cv2.COLOR_GRAY2BGR
        )

        return clean
    def _extract_result(
        self,
        results
    ):
        """
        Convert PaddleOCR's result object into a simple:

        {
            "text": "...",
            "confidence": 0.98,
            "parts": [...]
        }
        """

        detected = []

        for result in results:

            # PaddleOCR 3.x Result object exposes JSON data.
            payload = result.json

            # Handle implementations where json is callable.
            if callable(payload):
                payload = payload()

            # PaddleOCR generally stores actual OCR fields
            # under "res".
            if (
                isinstance(payload, dict)
                and "res" in payload
            ):
                data = payload["res"]

            else:
                data = payload

            if not isinstance(data, dict):
                continue

            texts = data.get(
                "rec_texts",
                []
            )

            scores = data.get(
                "rec_scores",
                []
            )

            boxes = data.get(
                "rec_boxes",
                None
            )

            # Convert numpy arrays to normal Python objects.
            if isinstance(
                scores,
                np.ndarray
            ):
                scores = scores.tolist()

            if isinstance(
                boxes,
                np.ndarray
            ):
                boxes = boxes.tolist()

            # -------------------------------------------------
            # Read each recognized text region
            # -------------------------------------------------

            for index, text in enumerate(
                texts
            ):

                text = str(text).strip()

                if not text:
                    continue

                # Confidence
                if index < len(scores):
                    confidence = float(
                        scores[index]
                    )

                else:
                    confidence = 0.0

                if (
                    confidence
                    < self.min_confidence
                ):
                    continue

                # Bounding box:
                #
                # [x_min, y_min, x_max, y_max]
                #
                # Used to reconstruct multi-line text
                # in correct reading order.

                if (
                    boxes is not None
                    and index < len(boxes)
                ):

                    box = boxes[index]

                    x = int(box[0])
                    y = int(box[1])

                else:

                    x = index
                    y = 0

                detected.append(
                    {
                        "text": text,
                        "confidence": confidence,
                        "x": x,
                        "y": y
                    }
                )

        # -----------------------------------------------------
        # Sort into natural reading order
        #
        # First top → bottom
        # Then left → right
        # -----------------------------------------------------

        detected.sort(
            key=lambda item: (
                item["y"],
                item["x"]
            )
        )

        if not detected:

            return {
                "text": "",
                "confidence": 0.0,
                "parts": []
            }

        # -----------------------------------------------------
        # Join multi-line cell contents
        #
        # BOTTOM
        # PARTS
        #
        # becomes:
        #
        # BOTTOM PARTS
        # -----------------------------------------------------

        combined_text = " ".join(
            item["text"]
            for item in detected
        )

        average_confidence = sum(
            item["confidence"]
            for item in detected
        ) / len(detected)

        return {
            "text": combined_text,
            "confidence": average_confidence,
            "parts": detected
        }


    # =========================================================
    # FIELD-SPECIFIC CLEANING
    # =========================================================

    def _clean_text(
        self,
        text,
        field=None
    ):
        """
        Normalize OCR output based on what kind of
        BOM column we're processing.
        """

        if text is None:
            return ""

        text = str(text).strip()

        # Collapse repeated whitespace.
        text = re.sub(
            r"\s+",
            " ",
            text
        )

        if not text:
            return ""

        # -----------------------------------------------------
        # ITEM / QTY
        #
        # These should contain integers.
        # -----------------------------------------------------

        if field in (
            "item",
            "qty"
        ):

            replacements = {
                "O": "0",
                "o": "0",
                "I": "1",
                "l": "1",
                "|": "1",
            }

            for old, new in replacements.items():
                text = text.replace(
                    old,
                    new
                )

            # Keep digits only.
            text = re.sub(
                r"[^0-9]",
                "",
                text
            )

            return text

        # -----------------------------------------------------
        # WEIGHT
        #
        # Can potentially contain decimals.
        # -----------------------------------------------------

        if field == "weight_kg":

            replacements = {
                "O": "0",
                "o": "0",
                "I": "1",
                "l": "1",
                "|": "1",
            }

            for old, new in replacements.items():
                text = text.replace(
                    old,
                    new
                )

            text = re.sub(
                r"[^0-9.\-]",
                "",
                text
            )

            return text

        # -----------------------------------------------------
        # TEXT COLUMNS
        # -----------------------------------------------------

        if field in (
            "part_name",
            "stock_name",
            "rev"
        ):
            return text.upper()

        return text


    # =========================================================
    # PUBLIC METHOD
    # =========================================================

    def read_cell(
        self,
        image_path,
        field=None
    ):
        """
        OCR one BOM cell.

        Returns:

        {
            "raw_text": "BOTTOM PARTS",
            "text": "BOTTOM PARTS",
            "confidence": 0.98,
            "parts": [...]
        }
        """

        prepared = self._prepare_image(
            image_path
        )

        results = self.ocr.predict(
            input=prepared
        )

        extracted = self._extract_result(
            results
        )

        cleaned = self._clean_text(
            extracted["text"],
            field
        )

        return {
            "raw_text":
                extracted["text"],

            "text":
                cleaned,

            "confidence":
                extracted["confidence"],

            "parts":
                extracted["parts"]
        }