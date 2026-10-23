"""Painel direito: Lista de cards em montagem (deck staging) e exportação para .apkg."""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem,
    QPushButton, QProgressBar, QMessageBox, QHeaderView
)
from libras_anki.gui.workers.deck_builder_worker import DeckBuilderWorker


class DeckView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.staged_cards = []
        self.builder_worker = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Cabeçalho
        title_label = QLabel("📦 Deck em Construção", self)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(title_label)

        # Campos de Configuração do Deck
        deck_name_layout = QHBoxLayout()
        name_label = QLabel("Nome:", self)
        name_label.setFixedWidth(50)
        name_label.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        self.input_deck_name = QLineEdit(self)
        self.input_deck_name.setText("Meu Deck de Libras")
        deck_name_layout.addWidget(name_label)
        deck_name_layout.addWidget(self.input_deck_name)
        layout.addLayout(deck_name_layout)

        output_layout = QHBoxLayout()
        output_label = QLabel("Arquivo:", self)
        output_label.setFixedWidth(50)
        output_label.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        self.input_output_file = QLineEdit(self)
        self.input_output_file.setText("meu_deck_libras.apkg")
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.input_output_file)
        layout.addLayout(output_layout)

        # Tabela de Cards
        self.table_cards = QTableWidget(self)
        self.table_cards.setColumnCount(4)
        self.table_cards.setHorizontalHeaderLabels(["Palavra", "Fonte", "SWU", "Texto"])
        self.table_cards.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cards.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cards.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cards.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_cards.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_cards)

        # Ações na Lista
        actions_layout = QHBoxLayout()
        self.btn_remove = QPushButton("🗑️ Remover", self)
        self.btn_remove.setObjectName("dangerButton")
        self.btn_remove.clicked.connect(self._remove_selected)

        self.btn_clear = QPushButton("Limpar Tudo", self)
        self.btn_clear.clicked.connect(self._clear_all)

        actions_layout.addWidget(self.btn_remove)
        actions_layout.addWidget(self.btn_clear)
        actions_layout.addStretch()

        self.count_label = QLabel("0 cards", self)
        self.count_label.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        actions_layout.addWidget(self.count_label)
        layout.addLayout(actions_layout)

        # Progresso e Exportação
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_progress = QLabel("", self)
        self.status_progress.setStyleSheet("color: #3b82f6; font-size: 11px;")
        self.status_progress.hide()
        layout.addWidget(self.status_progress)

        self.btn_export = QPushButton("🚀 Gerar Deck Anki (.apkg)", self)
        self.btn_export.setObjectName("primaryButton")
        self.btn_export.clicked.connect(self._start_export)
        layout.addWidget(self.btn_export)

    def add_card(self, card_data: dict):
        self.staged_cards.append(card_data)
        row = self.table_cards.rowCount()
        self.table_cards.insertRow(row)

        sw_icon = "Sim" if card_data.get("incluir_signwriting") else "Não"
        preview_text = card_data.get("texto_personalizado", "").replace("\n", " ")[:40]

        item_palavra = QTableWidgetItem(card_data.get("palavra", ""))
        item_fonte = QTableWidgetItem(card_data.get("fonte", ""))
        item_swu = QTableWidgetItem(sw_icon)
        item_swu.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_text = QTableWidgetItem(preview_text)

        self.table_cards.setItem(row, 0, item_palavra)
        self.table_cards.setItem(row, 1, item_fonte)
        self.table_cards.setItem(row, 2, item_swu)
        self.table_cards.setItem(row, 3, item_text)

        self._update_count()

    def _remove_selected(self):
        selected_rows = sorted(set(index.row() for index in self.table_cards.selectedIndexes()), reverse=True)
        if not selected_rows:
            return

        for r in selected_rows:
            self.table_cards.removeRow(r)
            del self.staged_cards[r]

        self._update_count()

    def _clear_all(self):
        if not self.staged_cards:
            return
        confirm = QMessageBox.question(
            self,
            "Limpar Deck",
            "Deseja remover todos os cards da lista?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.table_cards.setRowCount(0)
            self.staged_cards.clear()
            self._update_count()

    def _update_count(self):
        qtd = len(self.staged_cards)
        self.count_label.setText(f"{qtd} card{'s' if qtd != 1 else ''}")

    def _start_export(self):
        if not self.staged_cards:
            QMessageBox.warning(self, "Aviso", "Adicione ao menos um card antes de gerar o deck.")
            return

        deck_name = self.input_deck_name.text().strip() or "Meu Deck Libras"
        output_file = self.input_output_file.text().strip() or "meu_deck.apkg"
        if not output_file.endswith(".apkg"):
            output_file += ".apkg"

        self.btn_export.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_progress.setText("Iniciando conversão e empacotamento...")
        self.status_progress.show()

        self.builder_worker = DeckBuilderWorker(self.staged_cards, deck_name, output_file)
        self.builder_worker.progress_changed.connect(self._on_progress)
        self.builder_worker.finished_build.connect(self._on_finished)
        self.builder_worker.start()

    def _on_progress(self, pct, msg):
        self.progress_bar.setValue(pct)
        self.status_progress.setText(msg)

    def _on_finished(self, success, result_msg):
        self.btn_export.setEnabled(True)
        self.btn_remove.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.progress_bar.hide()
        self.status_progress.hide()

        if success:
            QMessageBox.information(
                self,
                "Sucesso",
                f"Deck Anki criado com sucesso!\n\nArquivo salvo em:\n{result_msg}\n\nAgora você pode importá-lo no Anki!"
            )
        else:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao gerar o deck:\n{result_msg}")
