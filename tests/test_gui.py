"""Testes automatizados da interface gráfica (PyQt6)."""

import os
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Configurar plataforma offscreen para testes de CI/CD sem servidor X11
os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_svg_viewer_widget(qapp):
    from libras_anki.gui.widgets.svg_viewer import SvgViewerWidget
    viewer = SvgViewerWidget()
    viewer.show()
    assert not viewer.placeholder_label.isHidden()
    assert viewer.svg_widget.isHidden()

    sample_svg = b'<svg width="100" height="100"><circle cx="50" cy="50" r="40" /></svg>'
    viewer.load_svg_bytes(sample_svg)
    assert not viewer.svg_widget.isHidden()
    assert viewer.placeholder_label.isHidden()

    viewer.clear()
    assert not viewer.placeholder_label.isHidden()
    assert viewer.svg_widget.isHidden()


def test_video_player_widget(qapp, tmp_path):
    from libras_anki.gui.widgets.video_player import VideoPlayerWidget
    player = VideoPlayerWidget()
    player.show()
    assert player.stack.currentIndex() == 0

    # Sinal sem vídeo
    player.load_signal_video("", "")
    assert player.stack.currentIndex() == 0

    # Sinal com vídeo online
    player.load_signal_video("https://youtube.com/watch?v=123", "")
    assert player.stack.currentIndex() == 1
    assert not player.btn_fetch.isHidden()

    # Sinal com vídeo local
    fake_video = tmp_path / "fake.mp4"
    fake_video.touch()
    player.load_signal_video("", str(fake_video))
    assert player.stack.currentIndex() == 2

    # Toggle loop
    player._toggle_loop(False)
    assert player.is_looping is False
    player._toggle_loop(True)
    assert player.is_looping is True

    player.clear()
    assert player.stack.currentIndex() == 0


def test_search_view(qapp):
    from libras_anki.gui.views.search_view import SearchView
    from libras_anki import db

    db.insert_or_update_sinal(
        fonte="INES",
        palavra="TESTE_BUSCA_GUI",
        descricao="Descricao teste"
    )

    search = SearchView()
    search.search_input.setText("TESTE_BUSCA_GUI")
    search._execute_search()

    assert search.list_results.count() >= 1
    item = search.list_results.item(0)
    data = item.data(Qt.ItemDataRole.UserRole)
    assert data["palavra"] == "TESTE_BUSCA_GUI"


def test_preview_view(qapp, tmp_path):
    from libras_anki.gui.views.preview_view import PreviewView

    fake_svg = tmp_path / "sw_casa.svg"
    fake_svg.write_text('<svg></svg>')

    with patch('os.path.exists', return_value=True):
        preview = PreviewView()
        sinal_mock = {
            "id": 9999,
            "palavra": "CASA",
            "fonte": "INES",
            "descricao": "Edificação para habitação.",
            "video_url": "https://video.mp4",
            "video_file": "",
            "source_link": "https://site.com"
        }

        preview.set_signal(sinal_mock)
        assert preview.title_label.text() == "CASA"
        assert "Edificação para habitação" in preview.text_editor.toPlainText()

        # Personalizar texto
        preview.text_editor.setPlainText("Meu texto exclusivo do card!")

        # Capturar sinal emitido
        captured = []
        preview.add_to_deck_requested.connect(lambda d: captured.append(d))
        preview._on_add_to_deck()

        assert len(captured) == 1
        assert captured[0]["palavra"] == "CASA"
        assert captured[0]["texto_personalizado"] == "Meu texto exclusivo do card!"

        preview.clear()


def test_deck_view(qapp):
    from libras_anki.gui.views.deck_view import DeckView

    deck_view = DeckView()
    assert len(deck_view.staged_cards) == 0

    card_1 = {
        "palavra": "PRETO",
        "fonte": "INES",
        "texto_personalizado": "Cor escura",
        "incluir_signwriting": True,
        "video_url": "https://vid.mp4",
        "video_file": "",
        "source_link": ""
    }
    deck_view.add_card(card_1)
    assert len(deck_view.staged_cards) == 1
    assert deck_view.table_cards.rowCount() == 1
    assert "1 card" in deck_view.count_label.text()

    # Remover
    deck_view.table_cards.selectRow(0)
    deck_view._remove_selected()
    assert len(deck_view.staged_cards) == 0
    assert deck_view.table_cards.rowCount() == 0
    assert "0 cards" in deck_view.count_label.text()


def test_main_window_integration(qapp):
    from libras_anki.gui.app import MainWindow

    with patch('os.path.exists', return_value=True):
        win = MainWindow()

        sinal_mock = {
            "id": 1234,
            "palavra": "AZUL",
            "fonte": "RedeSurdos",
            "descricao": "Cor do céu",
            "video_url": "https://vid.mp4",
            "video_file": "",
            "source_link": ""
        }
        # Simular seleção vinda da busca
        win.search_view.signal_selected.emit(sinal_mock)
        assert win.preview_view.title_label.text() == "AZUL"

        # Simular clique em adicionar card
        win.preview_view.text_editor.setPlainText("Nota de estudo de azul")
        win.preview_view._on_add_to_deck()

        assert len(win.deck_view.staged_cards) == 1
        assert win.deck_view.staged_cards[0]["palavra"] == "AZUL"
        assert win.deck_view.staged_cards[0]["texto_personalizado"] == "Nota de estudo de azul"

        win.preview_view.clear()
        win.close()
