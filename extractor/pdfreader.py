import pymupdf as doc

class PDFReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.doc = doc.open(file_path)

    def get_page_count(self):
        return len(self.doc)

    def get_page(self, page_number):
        return self.doc[page_number]
        
    def get_page_dimensions(self, page_number):
        page = self.get_page(page_number)
        return {
            "width": page.rect.width,
            "height": page.rect.height
        }

    def get_page_text(self, page_number):
        page = self.get_page(page_number)
        return page.get_text()

    def close(self):       
        self.doc.close()
