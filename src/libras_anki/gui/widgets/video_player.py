"""Widget de reprodução de vídeo integrado com controles de reprodução, loop e suporte a WebView (YouTube Embed + HTML5 Video)."""

import os
import re
import hashlib
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QProgressBar, QStackedWidget
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from libras_anki.dicionario import download_video
from libras_anki.utils import get_output_dir


def extract_youtube_id(url: str):
    if not url:
        return None
    match = re.search(r'(?:v=|\/embed\/|youtu\.be\/|\/v\/|\/shorts\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None


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

        # 4. Tela WebView para Reprodução Integrada (YouTube Embed + Vídeos Diretos)
        is_offscreen = os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        self.has_webengine = HAS_WEBENGINE and not is_offscreen
        if self.has_webengine:
            self.web_page = QWidget(self)
            web_layout = QVBoxLayout(self.web_page)
            web_layout.setContentsMargins(0, 0, 0, 0)
            web_layout.setSpacing(4)

            self.web_view = QWebEngineView(self)
            self.web_view.setMinimumSize(280, 200)
            self.web_view.setStyleSheet("background-color: #000000; border-radius: 8px;")

            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

            web_layout.addWidget(self.web_view)

            web_bar = QHBoxLayout()
            self.web_info = QLabel("🌐 Reprodução Web", self)
            self.web_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
            web_bar.addWidget(self.web_info)
            web_bar.addStretch()

            self.btn_cache_yt = QPushButton("💾 Baixar para Offline", self)
            self.btn_cache_yt.setStyleSheet("font-size: 11px; padding: 4px 8px;")
            self.btn_cache_yt.clicked.connect(self._start_download)
            web_bar.addWidget(self.btn_cache_yt)

            web_layout.addLayout(web_bar)

        self.stack.addWidget(self.empty_page)   # 0
        self.stack.addWidget(self.load_page)    # 1
        self.stack.addWidget(self.player_page)  # 2
        if self.has_webengine:
            self.stack.addWidget(self.web_page) # 3

        main_layout.addWidget(self.stack)
        self.stack.setCurrentIndex(0)

    def load_signal_video(self, video_url: str, video_file: str, base_name: str = ""):
        self.player.stop()
        if self.has_webengine:
            self.web_view.setHtml("<html><body style='background:#000;'></body></html>")

        self.current_video_url = video_url or ""
        self.current_local_path = ""

        # 1. Verificar se já existe arquivo local baixado/convertido
        output_dir = get_output_dir(None)
        possible_paths = []
        if video_file:
            possible_paths.append(os.path.join(output_dir, video_file))
            possible_paths.append(os.path.join(output_dir, "media_converted", os.path.basename(video_file)))

        if base_name:
            possible_paths.append(os.path.join(output_dir, "media", f"{base_name}.mp4"))
            possible_paths.append(os.path.join(output_dir, "media_converted", f"{base_name}.gif"))

        for p in possible_paths:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                self.current_local_path = p
                break

        # 2. Reprodução via WebEngine (YouTube ou vídeos normais/locais)
        if self.has_webengine:
            if self.current_local_path:
                abs_local = os.path.abspath(self.current_local_path)
                file_url = QUrl.fromLocalFile(abs_local).toString()
                if abs_local.lower().endswith(".gif"):
                    html = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body,html{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#000;display:flex;align-items:center;justify-content:center;}}img{{max-width:100%;max-height:100%;object-fit:contain;}}</style></head><body><img src="{file_url}"></body></html>"""
                else:
                    html = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body,html{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#000;display:flex;align-items:center;justify-content:center;}}video{{width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain;background:#000;}}</style></head><body><video src="{file_url}" autoplay loop controls playsinline></video></body></html>"""
                self.web_view.setHtml(html, QUrl.fromLocalFile(abs_local))
                self.web_info.setText("📁 Arquivo Local (Offline)")
                self.btn_cache_yt.setText("✓ Vídeo Local")
                self.btn_cache_yt.setEnabled(False)
                self.stack.setCurrentWidget(self.web_page)
                return

            yt_id = extract_youtube_id(self.current_video_url)
            if yt_id:
                embed_html = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body,html{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#000;}}iframe{{width:100%;height:100%;border:none;}}</style></head><body><iframe src="https://www.youtube-nocookie.com/embed/{yt_id}?autoplay=1&loop=1&playlist={yt_id}&rel=0" allow="autoplay; encrypted-media; fullscreen" allowfullscreen></iframe></body></html>"""
                self.web_view.setHtml(embed_html, QUrl("https://www.youtube-nocookie.com/"))
                self.web_info.setText("🌐 YouTube (Reprodução Online)")
                self.btn_cache_yt.setText("💾 Baixar para Offline")
                self.btn_cache_yt.setEnabled(True)
                self.stack.setCurrentWidget(self.web_page)
                return

            if self.current_video_url:
                video_html = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body,html{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#000;display:flex;align-items:center;justify-content:center;}}video{{width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain;background:#000;}}</style></head><body><video src="{self.current_video_url}" autoplay loop controls playsinline></video></body></html>"""
                self.web_view.setHtml(video_html, QUrl(self.current_video_url))
                self.web_info.setText("🌐 Vídeo Online (Reprodução Direta)")
                self.btn_cache_yt.setText("💾 Baixar para Offline")
                self.btn_cache_yt.setEnabled(True)
                self.stack.setCurrentWidget(self.web_page)
                return

            self.empty_label.setText("Este sinal não possui vídeo cadastrado.")
            self.stack.setCurrentIndex(0)
            return

        # 3. Fallback sem WebEngine (ex: QMediaPlayer)
        if self.current_local_path and os.path.exists(self.current_local_path):
            self._play_file(self.current_local_path)
            return

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

        if self.has_webengine:
            self.btn_cache_yt.setEnabled(False)
            self.btn_cache_yt.setText("⏳ Baixando...")
        self.btn_fetch.hide()
        self.load_label.setText("Baixando vídeo original da internet...")
        self.progress_bar.show()

        output_dir = get_output_dir(None)
        url_hash = hashlib.md5(self.current_video_url.encode("utf-8")).hexdigest()[:12]
        dest_filename = f"video_{url_hash}.mp4"
        dest_path = os.path.join(output_dir, "media", dest_filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.wait()

        self.download_worker = VideoDownloadWorker(self.current_video_url, dest_path)
        self.download_worker.finished_download.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_finished(self, success, file_path):
        self.progress_bar.hide()
        if success and os.path.exists(file_path):
            self.current_local_path = file_path
            if self.has_webengine:
                self.web_info.setText("📁 Arquivo Local (Offline)")
                self.btn_cache_yt.setText("✓ Vídeo Local")
                self.btn_cache_yt.setEnabled(False)
            else:
                self._play_file(file_path)
        else:
            if self.has_webengine:
                self.btn_cache_yt.setText("⚠️ Falha ao Baixar")
                self.btn_cache_yt.setEnabled(True)
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
        if self.has_webengine:
            self.web_view.setHtml("<html><body style='background:#000;'></body></html>")
        self.current_video_url = ""
        self.current_local_path = ""
        self.empty_label.setText("Selecione um sinal para ver o vídeo")
        self.stack.setCurrentIndex(0)
