"""Tema e folhas de estilo QSS para a aplicação desktop."""

DARK_THEME = """
QWidget {
    background-color: #18181b;
    color: #f4f4f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

QSplitter::handle {
    background-color: #27272a;
    width: 2px;
}

QGroupBox {
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #a1a1aa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}

QLineEdit, QTextEdit, QComboBox {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    color: #fafafa;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
    background-color: #202024;
}

QPushButton {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton#primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    font-size: 14px;
    padding: 10px 16px;
}

QPushButton#primaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#primaryButton:pressed {
    background-color: #1e40af;
}

QPushButton#secondaryButton {
    background-color: #059669;
    color: #ffffff;
    border: none;
}

QPushButton#secondaryButton:hover {
    background-color: #047857;
}

QPushButton#dangerButton {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
}

QPushButton#dangerButton:hover {
    background-color: #b91c1c;
}

QListWidget, QTableWidget {
    background-color: #1f1f23;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    border-radius: 6px;
    padding: 8px 10px;
    margin-bottom: 3px;
}

QListWidget::item:hover {
    background-color: #27272a;
}

QListWidget::item:selected {
    background-color: #1e3a8a;
    color: #93c5fd;
    font-weight: bold;
}

QHeaderView::section {
    background-color: #27272a;
    color: #a1a1aa;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #3f3f46;
    font-weight: bold;
}

QProgressBar {
    border: 1px solid #3f3f46;
    border-radius: 6px;
    text-align: center;
    background-color: #27272a;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 5px;
}

QScrollBar:vertical {
    border: none;
    background: #18181b;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #3f3f46;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #52525b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #52525b;
    background-color: #27272a;
}

QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

QStatusBar {
    background-color: #09090b;
    color: #a1a1aa;
    border-top: 1px solid #27272a;
}
"""
