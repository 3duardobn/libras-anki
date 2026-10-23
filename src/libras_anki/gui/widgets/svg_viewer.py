"""Widget para renderização vetorial de SignWriting (SVG)."""

import os
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtSvgWidgets import QSvgWidget
from libras_anki.utils import sanitize_svg_for_qt


class SvgViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card container amplo com fundo branco, cantos arredondados e borda sutil
        self.card_frame = QFrame(self)
        self.card_frame.setFixedSize(220, 200)
        self.card_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Renderizador vetorial centralizado dentro do card
        self.svg_widget = QSvgWidget(self.card_frame)
        self.svg_widget.setFixedSize(188, 168)
        self.svg_widget.setStyleSheet("background: transparent;")
        card_layout.addWidget(self.svg_widget)

        self.placeholder_label = QLabel("Nenhum SignWriting selecionado", self)
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #71717a; font-style: italic;")
        self.placeholder_label.setWordWrap(True)

        layout.addWidget(self.card_frame)
        layout.addWidget(self.placeholder_label)

        self.clear()

    def load_svg_bytes(self, data: bytes):
        if not data:
            self.clear()
            return
        cleaned_data = sanitize_svg_for_qt(data)
        byte_array = QByteArray(cleaned_data)
        self.svg_widget.load(byte_array)
        self.card_frame.show()
        self.svg_widget.show()
        self.placeholder_label.hide()

    def load_svg_file(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            self.clear()
            return
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.load_svg_bytes(content)
        except Exception:
            self.clear()

    def clear(self):
        self.card_frame.hide()
        self.svg_widget.hide()
        self.placeholder_label.show()


