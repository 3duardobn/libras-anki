"""Painel central: Visualização do sinal, player de vídeo, SignWriting e edição de texto do card."""

import os
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QCheckBox, QGroupBox, QScrollArea
)
from libras_anki.gui.widgets.video_player import VideoPlayerWidget
from libras_anki.gui.widgets.svg_viewer import SvgViewerWidget
from libras_anki import db
from libras_anki.dicionario import download_signwriting_svg, FONTES
from libras_anki.utils import get_output_dir


class SvgDownloadWorker(QThread):
    finished_svg = pyqtSignal(bool, str)

    def __init__(self, swu, dest_path):
        super().__init__()
        self.swu = swu
        self.dest_path = dest_path

    def run(self):
        try:
            ok = download_signwriting_svg(self.swu, self.dest_path)
            self.finished_svg.emit(ok, self.dest_path if ok else "")
        except Exception:
            self.finished_svg.emit(False, "")


class PreviewView(QWidget):
    add_to_deck_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_signal = None
        self.current_sw_info = None
        self.current_svg_path = ""
        self.svg_worker = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Cabeçalho do Sinal
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Nenhum sinal selecionado", self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        self.source_badge = QLabel("", self)
        self.source_badge.setStyleSheet("background-color: #27272a; color: #3b82f6; padding: 4px 8px; border-radius: 6px; font-weight: bold;")
        self.source_badge.hide()

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.source_badge)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 1. Player de Vídeo
        video_group = QGroupBox("Vídeo do Sinal", self)
        video_layout = QVBoxLayout(video_group)
        self.player_widget = VideoPlayerWidget(self)
        video_layout.addWidget(self.player_widget)
        layout.addWidget(video_group)

        # 2. SignWriting (SWU)
        sw_group = QGroupBox("SignWriting (Escrita do Sinal)", self)
        sw_layout = QVBoxLayout(sw_group)

        self.cb_include_sw = QCheckBox("Incluir SignWriting neste card", self)
        self.cb_include_sw.setChecked(True)
        sw_layout.addWidget(self.cb_include_sw)

        sw_display_layout = QHBoxLayout()
        self.svg_viewer = SvgViewerWidget(self)
        sw_display_layout.addWidget(self.svg_viewer)

        self.sw_info_label = QLabel("Carregando SignWriting...", self)
        self.sw_info_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        self.sw_info_label.setWordWrap(True)
        sw_display_layout.addWidget(self.sw_info_label, 1)

        sw_layout.addLayout(sw_display_layout)
        layout.addWidget(sw_group)

        # 3. Campo Único de Texto Personalizado
        text_group = QGroupBox("Texto do Card (Personalizável)", self)
        text_layout = QVBoxLayout(text_group)

        hint_label = QLabel("Edite livremente o que irá aparecer no verso do seu card:", self)
        hint_label.setStyleSheet("color: #71717a; font-size: 11px;")
        text_layout.addWidget(hint_label)

        self.text_editor = QTextEdit(self)
        self.text_editor.setMinimumHeight(100)
        self.text_editor.setPlaceholderText("Escreva a definição, frases de exemplo, mnemônicas ou notas de estudo...")
        text_layout.addWidget(self.text_editor)
        layout.addWidget(text_group)

        # 4. Botão de Adicionar ao Deck
        self.btn_add_deck = QPushButton("➕ Adicionar Card ao Deck", self)
        self.btn_add_deck.setObjectName("primaryButton")
        self.btn_add_deck.setEnabled(False)
        self.btn_add_deck.clicked.connect(self._on_add_to_deck)
        layout.addWidget(self.btn_add_deck)

        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def set_signal(self, signal_dict: dict):
        self.current_signal = signal_dict
        self.btn_add_deck.setEnabled(True)

        palavra = signal_dict.get('palavra', '')
        fonte = signal_dict.get('fonte', '')
        fonte_nome = FONTES.get(fonte, fonte)

        self.title_label.setText(palavra)
        self.source_badge.setText(fonte_nome)
        self.source_badge.show()

        # 1. Carregar Vídeo
        v_url = signal_dict.get('video_url', '')
        v_file = signal_dict.get('video_file', '')
        base_name = f"{fonte.lower()}_{db.normalize_word(palavra)}"
        self.player_widget.load_signal_video(v_url, v_file, base_name)

        # 2. Carregar SignWriting Local
        base_w = signal_dict.get('base_palavra') or db.normalize_word(palavra)
        self.current_sw_info = db.lookup_signwriting(base_w)
        self.current_svg_path = ""

        if self.current_sw_info and self.current_sw_info.get("swu"):
            swu = self.current_sw_info["swu"]
            self.cb_include_sw.setEnabled(True)
            self.cb_include_sw.setChecked(True)
            self.sw_info_label.setText(f"SignWriting disponível para: '{self.current_sw_info.get('title', palavra)}'")

            output_dir = get_output_dir(None)
            clean_name = db.get_base_palavra(db.normalize_word(palavra))
            dest_svg = os.path.join(output_dir, "media", f"sw_{clean_name}.svg")

            if os.path.exists(dest_svg):
                self.current_svg_path = dest_svg
                self.svg_viewer.load_svg_file(dest_svg)
            else:
                # Baixar em background ou carregar
                self.svg_viewer.clear()
                self.sw_info_label.setText("Baixando desenho vetorial de SignWriting...")
                if self.svg_worker and self.svg_worker.isRunning():
                    self.svg_worker.wait()
                self.svg_worker = SvgDownloadWorker(swu, dest_svg)
                self.svg_worker.finished_svg.connect(self._on_svg_downloaded)
                self.svg_worker.start()
        else:
            self.cb_include_sw.setChecked(False)
            self.cb_include_sw.setEnabled(False)
            self.svg_viewer.clear()
            self.sw_info_label.setText("Sem grafia SignWriting cadastrada na base local.")

        # 3. Preencher Texto Padrão (100% editável)
        texto_padrao = []
        desc = signal_dict.get('descricao', '').strip()
        if desc:
            texto_padrao.append(desc)
        if signal_dict.get('libras'):
            texto_padrao.append(f"\nGlosas Libras: {signal_dict['libras']}")
        if signal_dict.get('exemplo'):
            texto_padrao.append(f"\nExemplo: {signal_dict['exemplo']}")

        self.text_editor.setPlainText("\n".join(texto_padrao))

    def _on_svg_downloaded(self, success, file_path):
        if success and os.path.exists(file_path):
            self.current_svg_path = file_path
            self.svg_viewer.load_svg_file(file_path)
            self.sw_info_label.setText("SignWriting vetorial carregado com sucesso!")
        else:
            self.svg_viewer.clear()
            self.sw_info_label.setText("Não foi possível renderizar o SignWriting.")

    def _on_add_to_deck(self):
        if not self.current_signal:
            return

        card_data = {
            "signal": self.current_signal,
            "palavra": self.current_signal.get("palavra", ""),
            "fonte": self.current_signal.get("fonte", ""),
            "texto_personalizado": self.text_editor.toPlainText().strip(),
            "incluir_signwriting": self.cb_include_sw.isChecked() and bool(self.current_sw_info),
            "sw_info": self.current_sw_info,
            "svg_path": self.current_svg_path,
            "video_url": self.current_signal.get("video_url", ""),
            "video_file": self.current_signal.get("video_file", ""),
            "source_link": self.current_signal.get("source_link", "")
        }
        self.add_to_deck_requested.emit(card_data)

    def clear(self):
        if self.svg_worker and self.svg_worker.isRunning():
            self.svg_worker.wait()
        self.current_signal = None
        self.current_sw_info = None
        self.current_svg_path = ""
        self.title_label.setText("Nenhum sinal selecionado")
        self.source_badge.hide()
        self.player_widget.clear()
        self.svg_viewer.clear()
        self.text_editor.clear()
        self.btn_add_deck.setEnabled(False)
