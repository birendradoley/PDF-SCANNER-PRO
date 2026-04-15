import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QSpinBox,
)

from PIL import Image
from pypdf import PdfReader, PdfWriter

try:
    import pytesseract
    from pdf2image import convert_from_path

    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


class PDFScannerPro(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Scanner Pro Premium")
        self.setMinimumSize(980, 680)

        self._set_dark_palette()
        self._build_ui()

    def _set_dark_palette(self) -> None:
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(37, 37, 37))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(22, 22, 22))
        dark_palette.setColor(QPalette.AlternateBase, QColor(37, 37, 37))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.Highlight, QColor(0, 170, 255))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.setPalette(dark_palette)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        header = QLabel("All-in-one PDF toolkit: Create, Merge, Split, OCR")
        header.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_create_tab(), "Create PDF")
        self.tabs.addTab(self._build_merge_tab(), "Merge PDFs")
        self.tabs.addTab(self._build_split_tab(), "Split PDF")
        self.tabs.addTab(self._build_ocr_tab(), "OCR Extract")
        root.addWidget(self.tabs)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Activity log...")
        root.addWidget(self.log)

        self.setCentralWidget(central)

    def _build_create_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("Drop image files into the list or add manually. Exports a single PDF.")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.image_list = QListWidget()
        self.image_list.setAcceptDrops(True)
        self.image_list.setDragDropMode(QListWidget.DropOnly)
        layout.addWidget(self.image_list)

        controls = QHBoxLayout()
        add_images = QPushButton("Add Images")
        add_images.clicked.connect(self.add_images)
        controls.addWidget(add_images)

        clear_images = QPushButton("Clear")
        clear_images.clicked.connect(self.image_list.clear)
        controls.addWidget(clear_images)

        create_btn = QPushButton("Create PDF")
        create_btn.clicked.connect(self.create_pdf_from_images)
        controls.addWidget(create_btn)

        layout.addLayout(controls)
        return tab

    def _build_merge_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.merge_list = QListWidget()
        layout.addWidget(self.merge_list)

        controls = QHBoxLayout()
        add_btn = QPushButton("Add PDFs")
        add_btn.clicked.connect(self.add_merge_pdfs)
        controls.addWidget(add_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.merge_list.clear)
        controls.addWidget(clear_btn)

        merge_btn = QPushButton("Merge")
        merge_btn.clicked.connect(self.merge_pdfs)
        controls.addWidget(merge_btn)
        layout.addLayout(controls)

        return tab

    def _build_split_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        selector = QHBoxLayout()
        self.split_file_label = QLabel("No source PDF selected")
        selector.addWidget(self.split_file_label)
        choose = QPushButton("Choose PDF")
        choose.clicked.connect(self.select_split_pdf)
        selector.addWidget(choose)
        layout.addLayout(selector)

        group = QGroupBox("Split settings")
        form = QFormLayout(group)
        self.split_from = QSpinBox()
        self.split_from.setMinimum(1)
        self.split_to = QSpinBox()
        self.split_to.setMinimum(1)
        form.addRow("From page", self.split_from)
        form.addRow("To page", self.split_to)
        layout.addWidget(group)

        split_btn = QPushButton("Export selected range")
        split_btn.clicked.connect(self.split_pdf)
        layout.addWidget(split_btn)

        self.split_source: str | None = None
        return tab

    def _build_ocr_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        status = "OCR ready" if OCR_AVAILABLE else "OCR dependencies unavailable"
        self.ocr_status = QLabel(status)
        layout.addWidget(self.ocr_status)

        controls = QHBoxLayout()
        load = QPushButton("Load PDF/Image")
        load.clicked.connect(self.select_ocr_file)
        controls.addWidget(load)

        run = QPushButton("Run OCR")
        run.clicked.connect(self.run_ocr)
        controls.addWidget(run)

        export = QPushButton("Save Text")
        export.clicked.connect(self.save_ocr_text)
        controls.addWidget(export)
        layout.addLayout(controls)

        self.ocr_file = QLabel("No file loaded")
        layout.addWidget(self.ocr_file)

        self.ocr_output = QTextEdit()
        self.ocr_output.setPlaceholderText("Extracted text appears here...")
        layout.addWidget(self.ocr_output)

        self.ocr_source: str | None = None
        return tab

    def add_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)",
        )
        for path in paths:
            self.image_list.addItem(path)
        self._log(f"Added {len(paths)} image(s) to Create PDF queue.")

    def create_pdf_from_images(self) -> None:
        if self.image_list.count() == 0:
            self._warn("No images", "Add image files first.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "output.pdf", "PDF (*.pdf)")
        if not save_path:
            return

        image_paths = [self.image_list.item(i).text() for i in range(self.image_list.count())]
        converted = []
        for index, path in enumerate(image_paths, start=1):
            img = Image.open(path).convert("RGB")
            converted.append(img)
            self._set_progress(index, len(image_paths))

        first, rest = converted[0], converted[1:]
        first.save(save_path, save_all=True, append_images=rest)
        self._set_progress(0, 1)
        self._log(f"Created PDF: {save_path}")
        self._info("Success", "PDF created successfully.")

    def add_merge_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF Files (*.pdf)")
        for path in paths:
            self.merge_list.addItem(path)
        self._log(f"Added {len(paths)} PDF(s) for merge.")

    def merge_pdfs(self) -> None:
        if self.merge_list.count() < 2:
            self._warn("Not enough files", "Choose at least two PDFs to merge.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save merged PDF", "merged.pdf", "PDF (*.pdf)")
        if not save_path:
            return

        writer = PdfWriter()
        total = self.merge_list.count()
        for i in range(total):
            reader = PdfReader(self.merge_list.item(i).text())
            for page in reader.pages:
                writer.add_page(page)
            self._set_progress(i + 1, total)

        with open(save_path, "wb") as fp:
            writer.write(fp)

        self._set_progress(0, 1)
        self._log(f"Merged {total} PDFs into: {save_path}")
        self._info("Success", "PDF files merged successfully.")

    def select_split_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        self.split_source = path
        self.split_file_label.setText(Path(path).name)

        try:
            pages = len(PdfReader(path).pages)
            self.split_from.setMaximum(pages)
            self.split_to.setMaximum(pages)
            self.split_to.setValue(pages)
            self._log(f"Loaded split source ({pages} pages): {path}")
        except Exception as exc:
            self._warn("Invalid PDF", str(exc))

    def split_pdf(self) -> None:
        if not self.split_source:
            self._warn("No source", "Choose a source PDF first.")
            return

        start_page = self.split_from.value()
        end_page = self.split_to.value()
        if end_page < start_page:
            self._warn("Invalid range", "To page must be greater than or equal to From page.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save split PDF", "split.pdf", "PDF (*.pdf)")
        if not save_path:
            return

        reader = PdfReader(self.split_source)
        writer = PdfWriter()
        for p in range(start_page - 1, end_page):
            writer.add_page(reader.pages[p])
        with open(save_path, "wb") as fp:
            writer.write(fp)

        self._log(f"Split PDF saved: {save_path} (pages {start_page}-{end_page})")
        self._info("Success", "Split PDF exported.")

    def select_ocr_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select source",
            "",
            "Supported Files (*.pdf *.png *.jpg *.jpeg *.bmp *.tiff)",
        )
        if path:
            self.ocr_source = path
            self.ocr_file.setText(path)

    def run_ocr(self) -> None:
        if not OCR_AVAILABLE:
            self._warn(
                "OCR unavailable",
                "Install system OCR dependencies (Tesseract and Poppler) and retry.",
            )
            return

        if not self.ocr_source:
            self._warn("No file", "Choose a PDF or image first.")
            return

        source = self.ocr_source.lower()
        extracted_chunks = []

        if source.endswith(".pdf"):
            pages = convert_from_path(self.ocr_source)
            for idx, page in enumerate(pages, start=1):
                extracted_chunks.append(pytesseract.image_to_string(page))
                self._set_progress(idx, len(pages))
        else:
            image = Image.open(self.ocr_source)
            extracted_chunks.append(pytesseract.image_to_string(image))
            self._set_progress(1, 1)

        text = "\n\n".join(extracted_chunks).strip()
        self.ocr_output.setText(text)
        self._set_progress(0, 1)
        self._log(f"OCR extraction completed for: {self.ocr_source}")

    def save_ocr_text(self) -> None:
        if not self.ocr_output.toPlainText().strip():
            self._warn("No text", "Run OCR first.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save text", "output.txt", "Text Files (*.txt)")
        if not save_path:
            return

        with open(save_path, "w", encoding="utf-8") as fp:
            fp.write(self.ocr_output.toPlainText())
        self._log(f"OCR text exported to: {save_path}")

    def _set_progress(self, current: int, total: int) -> None:
        self.progress.setValue(int((current / max(total, 1)) * 100))

    def _log(self, message: str) -> None:
        self.log.append(message)

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
        self._log(f"Warning - {title}: {message}")

    def _info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)
        self._log(f"Info - {title}: {message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFScannerPro()
    window.show()
    sys.exit(app.exec_())
