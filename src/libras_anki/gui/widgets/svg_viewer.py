"""Widget para renderização vetorial de SignWriting (SVG)."""

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtSvgWidgets import QSvgWidget


class SvgViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.svg_widget = QSvgWidget(self)
        self.svg_widget.setFixedSize(140, 140)
        self.svg_widget.setStyleSheet("background-color: #ffffff; border-radius: 8px; padding: 6px;")

        self.placeholder_label = QLabel("Nenhum SignWriting selecionado", self)
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #71717a; font-style: italic;")

        layout.addWidget(self.svg_widget)
        layout.addWidget(self.placeholder_label)

        self.clear()

    def load_svg_bytes(self, data: bytes):
        if not data:
            self.clear()
            return
        byte_array = QByteArray(data)
        self.svg_widget.load(byte_array)
        self.svg_widget.show()
        self.placeholder_label.hide()

    def load_svg_file(self, file_path: str):
        if not file_path:
            self.clear()
            return
        self.svg_widget.load(file_path)
        self.svg_widget.show()
        self.placeholder_label.hide()

    def clear(self):
        self.svg_widget.hide()
        self.placeholder_label.show()
