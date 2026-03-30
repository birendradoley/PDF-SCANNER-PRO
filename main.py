import sys

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QProgressBar, QTabWidget)
from PyQt5.QtGui import QPalette, QColor

class PDFScannerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Set dark theme
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.Highlight, QColor(0, 170, 255))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.setPalette(dark_palette)

        self.setWindowTitle('Modern PDF Scanner')
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel('Drop your PDF files here or click to browse.\nSupports: Word, Excel, PowerPoint')
        layout.addWidget(self.label)

        self.progress_bar = QProgressBar(self)
        layout.addWidget(self.progress_bar)

        self.batch_button = QPushButton('Process Batch', self)
        self.batch_button.clicked.connect(self.process_batch)
        layout.addWidget(self.batch_button)

        self.setDragDropFeatures()

    def setDragDropFeatures(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/pdf'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = event.mimeData().urls()  # Get the dropped file(s)
        for file in files:
            self.label.setText(f'Processing: {file.toLocalFile()}')
            # Add logic for processing files here

    def process_batch(self):
        # Logic to handle batch processing
        self.label.setText('Processing batch...')
        self.progress_bar.setValue(50)  # Example progress update

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFScannerApp()
    window.show()
    sys.exit(app.exec_())