"""Widget de reprodução de vídeo integrado com controles de reprodução e suporte a loop."""

import os
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QProgressBar, QStackedWidget
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from libras_anki.dicionario import download_video
from libras_anki.utils import get_output_dir


class VideoDownloadWorker(QThread):
    finished_download = pyqtSignal(bool, str)

    def __init__(self, video_url, dest_path):
        super().__init__()
        self.video_url = video_url
        self.dest_path = dest_path

    def run(self):
        try:
            ok = download_video(self.video_url, self.dest_path)
            self.finished_download.emit(ok, self.dest_path if ok else "")
        except Exception:
            self.finished_download.emit(False, "")


class VideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_video_url = ""
        self.current_local_path = ""
        self.is_looping = True
        self.download_worker = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        self.stack = QStackedWidget(self)

        # 1. Tela do Player
        self.player_page = QWidget(self)
        player_layout = QVBoxLayout(self.player_page)
        player_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumSize(280, 200)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 8px;")

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

        player_layout.addWidget(self.video_widget)

        # Controles
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(4, 2, 4, 2)

        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFixedWidth(40)
        self.btn_play.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.btn_play)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.slider)

        self.time_label = QLabel("00:00 / 00:00", self)
        self.time_label.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        controls_layout.addWidget(self.time_label)

        self.btn_loop = QPushButton("🔁 Loop", self)
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setStyleSheet("background-color: #1e3a8a; color: #93c5fd;")
        self.btn_loop.toggled.connect(self._toggle_loop)
        controls_layout.addWidget(self.btn_loop)

        player_layout.addLayout(controls_layout)

        # 2. Tela de Download / Carregamento
        self.load_page = QWidget(self)
        load_layout = QVBoxLayout(self.load_page)
        load_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.load_label = QLabel("Vídeo não baixado localmente.", self)
        self.load_label.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        load_layout.addWidget(self.load_label)

        self.btn_fetch = QPushButton("🌐 Baixar e Reproduzir Vídeo Original", self)
        self.btn_fetch.setObjectName("primaryButton")
        self.btn_fetch.clicked.connect(self._start_download)
        load_layout.addWidget(self.btn_fetch)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.hide()
        load_layout.addWidget(self.progress_bar)

        # 3. Tela Placeholder (vazio)
        self.empty_page = QWidget(self)
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label = QLabel("Selecione um sinal para ver o vídeo", self)
        self.empty_label.setStyleSheet("color: #71717a; font-style: italic;")
        empty_layout.addWidget(self.empty_label)

        self.stack.addWidget(self.empty_page)   # 0
        self.stack.addWidget(self.load_page)    # 1
        self.stack.addWidget(self.player_page)  # 2

        main_layout.addWidget(self.stack)
        self.stack.setCurrentIndex(0)

    def load_signal_video(self, video_url: str, video_file: str, base_name: str = ""):
        self.player.stop()
        self.current_video_url = video_url or ""
        self.current_local_path = ""

        # Verificar se já existe arquivo local
        output_dir = get_output_dir(None)
        possible_paths = []
        if video_file:
            possible_paths.append(os.path.join(output_dir, video_file))
            possible_paths.append(os.path.join(output_dir, "media_converted", os.path.basename(video_file)))

        if base_name:
            possible_paths.append(os.path.join(output_dir, "media", f"{base_name}.mp4"))
            possible_paths.append(os.path.join(output_dir, "media_converted", f"{base_name}.gif"))

        for p in possible_paths:
            if os.path.exists(p):
                self.current_local_path = p
                break

        if self.current_local_path and os.path.exists(self.current_local_path):
            self._play_file(self.current_local_path)
            return

        # Se não existe localmente mas temos URL
        if self.current_video_url:
            self.load_label.setText("Vídeo disponível online. Deseja reproduzir?")
            self.btn_fetch.show()
            self.progress_bar.hide()
            self.stack.setCurrentIndex(1)
        else:
            self.empty_label.setText("Este sinal não possui vídeo cadastrado.")
            self.stack.setCurrentIndex(0)

    def _start_download(self):
        if not self.current_video_url:
            return

        self.btn_fetch.hide()
        self.load_label.setText("Baixando vídeo original da internet...")
        self.progress_bar.show()

        output_dir = get_output_dir(None)
        dest_filename = f"video_{abs(hash(self.current_video_url)) % 10000000}.mp4"
        dest_path = os.path.join(output_dir, "media", dest_filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        self.download_worker = VideoDownloadWorker(self.current_video_url, dest_path)
        self.download_worker.finished_download.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_finished(self, success, file_path):
        self.progress_bar.hide()
        if success and os.path.exists(file_path):
            self.current_local_path = file_path
            self._play_file(file_path)
        else:
            self.btn_fetch.show()
            self.load_label.setText("Falha ao baixar vídeo. Verifique sua conexão.")

    def _play_file(self, file_path):
        self.stack.setCurrentIndex(2)
        url = QUrl.fromLocalFile(file_path)
        self.player.setSource(url)
        self.player.play()
        self.btn_play.setText("⏸")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶")
        else:
            self.player.play()
            self.btn_play.setText("⏸")

    def set_position(self, position):
        self.player.setPosition(position)

    def _on_position_changed(self, position):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self._update_time_label(position, self.player.duration())

    def _on_duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self._update_time_label(self.player.position(), duration)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_looping:
                self.player.setPosition(0)
                self.player.play()
            else:
                self.btn_play.setText("▶")

    def _toggle_loop(self, checked):
        self.is_looping = checked
        if checked:
            self.btn_loop.setStyleSheet("background-color: #1e3a8a; color: #93c5fd;")
        else:
            self.btn_loop.setStyleSheet("")

    def _update_time_label(self, current, total):
        cur_sec = current // 1000
        tot_sec = total // 1000
        self.time_label.setText(f"{cur_sec // 60:02d}:{cur_sec % 60:02d} / {tot_sec // 60:02d}:{tot_sec % 60:02d}")

    def clear(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.wait()
        self.player.stop()
        self.current_video_url = ""
        self.current_local_path = ""
        self.empty_label.setText("Selecione um sinal para ver o vídeo")
        self.stack.setCurrentIndex(0)
