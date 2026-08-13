import pymupdf


class PDFReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.doc = pymupdf.open(file_path)

    def get_page_count(self):
        """
        Return the number of pages in the PDF.
        """

        return len(self.doc)

    def get_page(self, page_number):
        """
        Return a PyMuPDF page object.

        page_number is zero-based:
        0 = first page
        1 = second page
        etc.
        """

        return self.doc[page_number]

    def get_page_dimensions(self, page_number):
        """
        Return page width and height.
        """

        page = self.get_page(page_number)

        return {
            "width": page.rect.width,
            "height": page.rect.height
        }

    def get_page_text(self, page_number):
        """
        Attempt native PDF text extraction.

        This may not work for CAD text that has been
        converted into vector geometry, but it is still
        useful to keep available.
        """

        page = self.get_page(page_number)

        return page.get_text()

    def get_page_words(self, page_number):
        """
        Return words and their coordinates when native
        PDF text is available.
        """

        page = self.get_page(page_number)

        return page.get_text("words")

    def render_region(
        self,
        page_number,
        region,
        output_path,
        scale=2
    ):
        """
        Render a rectangular PDF region as an image.

        region format:

        (
            x0,
            y0,
            x1,
            y1
        )

        scale controls output resolution.
        Higher scale = larger / clearer image.
        """

        page = self.get_page(page_number)

        x0, y0, x1, y1 = region

        rect = pymupdf.Rect(
            x0,
            y0,
            x1,
            y1
        )

        matrix = pymupdf.Matrix(
            scale,
            scale
        )

        pix = page.get_pixmap(
            matrix=matrix,
            clip=rect,
            alpha=False
        )

        pix.save(output_path)

    def close(self):
        """
        Close the PDF document.
        """

        self.doc.close()