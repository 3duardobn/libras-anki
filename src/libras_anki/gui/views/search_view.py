"""Painel esquerdo: Busca rápida de sinais no banco SQLite local e filtros de fontes."""

from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QLabel
)
from libras_anki import db
from libras_anki.dicionario import FONTES


class SearchView(QWidget):
    signal_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._setup_timer()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Cabeçalho
        title_label = QLabel("🔍 Busca de Sinais (Local)", self)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(title_label)

        # Filtro de Fonte
        fontes_layout = QHBoxLayout()
        fontes_label = QLabel("Fonte:", self)
        fontes_label.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        self.combo_fonte = QComboBox(self)
        self.combo_fonte.addItem("Todas as Fontes", "Ambos")
        for k, v in FONTES.items():
            self.combo_fonte.addItem(f"{k} - {v}", k)
        self.combo_fonte.currentIndexChanged.connect(self._trigger_search)
        fontes_layout.addWidget(fontes_label)
        fontes_layout.addWidget(self.combo_fonte, 1)
        layout.addLayout(fontes_layout)

        # Campo de Busca
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Digite uma palavra (ex: azul, casa, professor)...")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._execute_search)
        layout.addWidget(self.search_input)

        # Contador de Resultados
        self.status_label = QLabel("Pronto para pesquisar.", self)
        self.status_label.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Lista de Resultados
        self.list_results = QListWidget(self)
        self.list_results.itemSelectionChanged.connect(self._on_item_selected)
        layout.addWidget(self.list_results)

    def _setup_timer(self):
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(250)
        self.debounce_timer.timeout.connect(self._execute_search)

    def _on_text_changed(self):
        self.debounce_timer.start()

    def _trigger_search(self):
        self._execute_search()

    def _execute_search(self):
        query = self.search_input.text().strip()
        fonte = self.combo_fonte.currentData()

        self.list_results.clear()

        conn = db.get_db_connection()
        try:
            cursor = conn.cursor()
            params = []
            sql = "SELECT id, fonte, palavra, normalized_palavra, base_palavra, descricao, libras, exemplo, video_url, video_file, source_link, tags FROM sinais WHERE 1=1"

            if query:
                norm = db.normalize_word(query)
                base = db.get_base_palavra(norm)
                sql += " AND (normalized_palavra LIKE ? OR base_palavra LIKE ? OR palavra LIKE ?)"
                params.extend([f"%{norm}%", f"%{base}%", f"%{query}%"])

            if fonte and fonte != "Ambos":
                sql += " AND fonte = ?"
                params.append(fonte)

            sql += " ORDER BY CASE WHEN normalized_palavra = ? THEN 1 WHEN base_palavra = ? THEN 2 ELSE 3 END, palavra ASC LIMIT 150"
            if query:
                norm = db.normalize_word(query)
                base = db.get_base_palavra(norm)
                params.extend([norm, base])
            else:
                params.extend(["", ""])

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            for row in rows:
                item_data = dict(row)
                base_w = item_data.get('base_palavra') or db.normalize_word(item_data['palavra'])

                # Checagem de SignWriting local
                sw_info = db.lookup_signwriting(base_w)
                has_sw = " [SWU]" if sw_info else ""
                has_vid = " 🎬" if (item_data.get('video_url') or item_data.get('video_file')) else ""

                item_text = f"{item_data['palavra']} ({item_data['fonte']}){has_sw}{has_vid}"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, item_data)
                self.list_results.addItem(list_item)

            self.status_label.setText(f"{len(rows)} sinais encontrados localmente.")
        except Exception as e:
            self.status_label.setText(f"Erro na busca: {e}")
        finally:
            conn.close()

    def _on_item_selected(self):
        selected_items = self.list_results.selectedItems()
        if selected_items:
            data = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.signal_selected.emit(data)
