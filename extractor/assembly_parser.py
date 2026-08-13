import re

import cv2
import numpy as np
from paddleocr import PaddleOCR


class AssemblyParser:
    """
    Extract the ASSEMBLY value from the bottom-right
    drawing title block.

    Example:

        ASSEMBLY | MARCURIUS

    returns:

        "MARCURIUS"
    """

    def __init__(
        self,
        min_confidence=0.30
    ):
        self.min_confidence = min_confidence

        print("Loading Assembly OCR model...")

        self.ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
            text_rec_score_thresh=min_confidence
        )

        print("Assembly OCR ready.")


    # =========================================================
    # IMAGE PREPARATION
    # =========================================================

    def _prepare_image(
        self,
        image_path
    ):
        """
        Make faint CAD title-block text easier to read.
        """

        image = cv2.imread(
            str(image_path)
        )

        if image is None:
            raise ValueError(
                f"Could not read image: {image_path}"
            )

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # Strengthen faint CAD text.
        clean = cv2.threshold(
            gray,
            245,
            255,
            cv2.THRESH_BINARY
        )[1]

        # Enlarge title block text.
        clean = cv2.resize(
            clean,
            None,
            fx=2,
            fy=2,
            interpolation=cv2.INTER_CUBIC
        )

        # Add whitespace around outside.
        clean = cv2.copyMakeBorder(
            clean,
            20,
            20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=255
        )

        # Paddle detector requires 3 channels.
        clean = cv2.cvtColor(
            clean,
            cv2.COLOR_GRAY2BGR
        )

        return clean


    # =========================================================
    # OCR RESULT PARSING
    # =========================================================

    def _get_regions(
        self,
        image
    ):
        """
        Return every OCR-detected text region.

        Each region has:

            text
            confidence
            x1
            y1
            x2
            y2
            center_x
            center_y
        """

        results = self.ocr.predict(
            input=image
        )

        regions = []

        for result in results:

            payload = result.json

            if callable(payload):
                payload = payload()

            if (
                isinstance(payload, dict)
                and "res" in payload
            ):
                data = payload["res"]

            else:
                data = payload

            if not isinstance(
                data,
                dict
            ):
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
                []
            )

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

            for index, text in enumerate(
                texts
            ):

                text = str(
                    text
                ).strip()

                if not text:
                    continue

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

                if index >= len(boxes):
                    continue

                box = boxes[index]

                if len(box) < 4:
                    continue

                x1 = int(box[0])
                y1 = int(box[1])
                x2 = int(box[2])
                y2 = int(box[3])

                regions.append(
                    {
                        "text":
                            text,

                        "confidence":
                            confidence,

                        "x1":
                            x1,

                        "y1":
                            y1,

                        "x2":
                            x2,

                        "y2":
                            y2,

                        "center_x":
                            (x1 + x2) / 2,

                        "center_y":
                            (y1 + y2) / 2
                    }
                )

        return regions


    # =========================================================
    # TEXT NORMALIZATION
    # =========================================================

    def _normalize(
        self,
        text
    ):
        """
        Normalize OCR text for matching.
        """

        text = str(
            text
        ).strip().upper()

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text


    # =========================================================
    # FIND ASSEMBLY ANCHOR
    # =========================================================

    def _find_assembly_label(
        self,
        regions
    ):
        """
        Find the OCR region containing the word ASSEMBLY.
        """

        candidates = []

        for region in regions:

            normalized = self._normalize(
                region["text"]
            )

            # Exact match is ideal.
            if normalized == "ASSEMBLY":

                candidates.append(
                    (
                        0,
                        region
                    )
                )

            # Allow minor OCR extras.
            elif "ASSEMBLY" in normalized:

                candidates.append(
                    (
                        1,
                        region
                    )
                )

        if not candidates:

            raise ValueError(
                "Could not find ASSEMBLY label "
                "in title block."
            )

        candidates.sort(
            key=lambda item: (
                item[0],
                -item[1]["confidence"]
            )
        )

        return candidates[0][1]


    # =========================================================
    # FIND VALUE TO THE RIGHT
    # =========================================================

    def _find_value_to_right(
        self,
        label,
        regions
    ):
        """
        Find OCR text immediately to the right of
        the ASSEMBLY label on the same table row.
        """

        candidates = []

        label_height = max(
            1,
            label["y2"] - label["y1"]
        )

        for region in regions:

            if region is label:
                continue

            # Must be to the right.
            if (
                region["center_x"]
                <= label["center_x"]
            ):
                continue

            # ---------------------------------------------
            # Determine vertical alignment.
            # ---------------------------------------------

            vertical_distance = abs(
                region["center_y"]
                - label["center_y"]
            )

            # Allow approximately one text-height
            # difference.
            max_vertical_distance = (
                label_height * 1.25
            )

            if (
                vertical_distance
                > max_vertical_distance
            ):
                continue

            # ---------------------------------------------
            # Horizontal distance
            # ---------------------------------------------

            horizontal_distance = (
                region["x1"]
                - label["x2"]
            )

            # If boxes slightly overlap because of OCR,
            # don't heavily punish it.
            horizontal_distance = max(
                0,
                horizontal_distance
            )

            # ---------------------------------------------
            # Candidate score
            #
            # Prefer:
            # 1. Same row
            # 2. Closest thing to the right
            # 3. Higher confidence
            # ---------------------------------------------

            score = (
                vertical_distance * 3
                +
                horizontal_distance
                -
                region["confidence"] * 20
            )

            candidates.append(
                (
                    score,
                    region
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0]
        )

        return candidates[0][1]


    # =========================================================
    # FALLBACK SEARCH
    # =========================================================

    def _fallback_value(
        self,
        label,
        regions
    ):
        """
        Fallback if OCR doesn't put ASSEMBLY and its
        value perfectly on the same horizontal row.

        Looks for the nearest reasonable text region
        to the right or slightly below/right.
        """

        candidates = []

        for region in regions:

            if region is label:
                continue

            # Ignore text clearly left of ASSEMBLY.
            if (
                region["center_x"]
                < label["center_x"]
            ):
                continue

            dx = abs(
                region["center_x"]
                - label["center_x"]
            )

            dy = abs(
                region["center_y"]
                - label["center_y"]
            )

            # Don't wander too far vertically.
            if dy > 200:
                continue

            distance = (
                dx
                +
                dy * 2
            )

            candidates.append(
                (
                    distance,
                    region
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0]
        )

        return candidates[0][1]


    # =========================================================
    # DEBUG IMAGE
    # =========================================================

    def _save_debug(
        self,
        prepared,
        regions,
        label,
        value,
        output_path
    ):
        """
        Draw all OCR regions.

        Blue  = other OCR text
        Red   = ASSEMBLY label
        Green = chosen assembly value
        """

        debug = prepared.copy()

        for region in regions:

            color = (
                255,
                0,
                0
            )

            thickness = 2

            if region is label:

                color = (
                    0,
                    0,
                    255
                )

                thickness = 4

            elif region is value:

                color = (
                    0,
                    255,
                    0
                )

                thickness = 4

            cv2.rectangle(
                debug,
                (
                    region["x1"],
                    region["y1"]
                ),
                (
                    region["x2"],
                    region["y2"]
                ),
                color,
                thickness
            )

            cv2.putText(
                debug,
                region["text"],
                (
                    region["x1"],
                    max(
                        15,
                        region["y1"] - 5
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA
            )

        cv2.imwrite(
            str(output_path),
            debug
        )


    # =========================================================
    # PUBLIC METHOD
    # =========================================================

    def extract(
        self,
        image_path,
        debug_output_path=None
    ):
        """
        Extract assembly value.

        Returns:

        {
            "assembly": "MARCURIUS",
            "confidence": 0.99,
            "raw_text": "MARCURIUS"
        }
        """

        prepared = self._prepare_image(
            image_path
        )

        regions = self._get_regions(
            prepared
        )

        if not regions:

            raise ValueError(
                "No OCR text detected in "
                "title block."
            )

        # -----------------------------------------------------
        # Find ASSEMBLY label
        # -----------------------------------------------------

        label = self._find_assembly_label(
            regions
        )

        # -----------------------------------------------------
        # Find value next to it
        # -----------------------------------------------------

        value = self._find_value_to_right(
            label,
            regions
        )

        # -----------------------------------------------------
        # Fallback
        # -----------------------------------------------------

        if value is None:

            value = self._fallback_value(
                label,
                regions
            )

        if value is None:

            raise ValueError(
                "ASSEMBLY label was found, "
                "but its value could not be determined."
            )

        # -----------------------------------------------------
        # Normalize final value
        # -----------------------------------------------------

        assembly = self._normalize(
            value["text"]
        )

        # -----------------------------------------------------
        # Debug image
        # -----------------------------------------------------

        if debug_output_path:

            self._save_debug(
                prepared,
                regions,
                label,
                value,
                debug_output_path
            )

        return {
            "assembly":
                assembly,

            "confidence":
                value["confidence"],

            "raw_text":
                value["text"],

            "label_confidence":
                label["confidence"],

            "label":
                label,

            "value_region":
                value
        }