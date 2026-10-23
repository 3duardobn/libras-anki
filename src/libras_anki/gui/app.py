"""Janela principal da aplicação gráfica desktop (PyQt6)."""

import os
import sys

# Desativar aceleração de GPU problemática do Chromium no Wayland/Linux para evitar flickering/glitches na janela
if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing --no-sandbox"

from PyQt6.QtCore import Qt, QCoreApplication
# Compartilhar contextos OpenGL antes da criação de QApplication (obrigatório para QtWebEngine)
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

# Importar QtWebEngineWidgets antes da criação de QApplication (requisito do Chromium/Qt)
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QSplitter, QStatusBar
)
from libras_anki import db
from libras_anki.gui.theme import DARK_THEME
from libras_anki.gui.views.search_view import SearchView
from libras_anki.gui.views.preview_view import PreviewView
from libras_anki.gui.views.deck_view import DeckView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Libras Anki Studio — Criador Visual de Decks")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("centralWidget")
        central_widget.setAutoFillBackground(True)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # 1. Painel Esquerdo: Busca
        self.search_view = SearchView(self)
        splitter.addWidget(self.search_view)

        # 2. Painel Central: Preview e Customização
        self.preview_view = PreviewView(self)
        splitter.addWidget(self.preview_view)

        # 3. Painel Direito: Deck em Construção
        self.deck_view = DeckView(self)
        splitter.addWidget(self.deck_view)

        # Proporções dos painéis
        splitter.setSizes([320, 520, 360])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        main_layout.addWidget(splitter)

        # Conexões entre os painéis
        self.search_view.signal_selected.connect(self.preview_view.set_signal)
        self.preview_view.add_to_deck_requested.connect(self._on_card_added)

        # Barra de Status
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Base SQLite local conectada. 100% Offline-first pronto.")

    def _on_card_added(self, card_data):
        self.deck_view.add_card(card_data)
        self.status_bar.showMessage(f"Card '{card_data.get('palavra')}' adicionado ao deck!", 3000)


def main():
    # Inicializa banco local SQLite e dados se necessário
    db.init_db()

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
