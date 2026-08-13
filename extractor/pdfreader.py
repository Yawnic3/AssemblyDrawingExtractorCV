import pymupdf as doc

class PDFReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.doc = doc.open(file_path)

