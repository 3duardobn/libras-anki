"""Worker em segundo plano para download de vídeos, conversão para GIF e geração de deck Anki."""

import os
import hashlib
import genanki
from PyQt6.QtCore import QThread, pyqtSignal
from libras_anki import db
from libras_anki.utils import get_output_dir
from libras_anki.dicionario import (
    get_safe_media_filename, download_video, download_signwriting_svg, FONTES
)
from libras_anki.convert_videos import convert_video_to_gif


class DeckBuilderWorker(QThread):
    progress_changed = pyqtSignal(int, str)
    finished_build = pyqtSignal(bool, str)

    def __init__(self, staged_cards: list, deck_name: str, output_filename: str):
        super().__init__()
        self.staged_cards = staged_cards
        self.deck_name = deck_name or "Dicionário Libras"
        self.output_filename = output_filename or "dicionario_libras.apkg"

    def run(self):
        if not self.staged_cards:
            self.finished_build.emit(False, "Nenhum card no deck.")
            return

        total_cards = len(self.staged_cards)
        output_dir = get_output_dir(None)
        media_dir = os.path.join(output_dir, "media")
        converted_dir = os.path.join(output_dir, "media_converted")
        os.makedirs(media_dir, exist_ok=True)
        os.makedirs(converted_dir, exist_ok=True)

        deck_id = int(hashlib.md5(self.deck_name.encode()).hexdigest()[:16], 16) % (1 << 31)
        model_id = int(hashlib.md5(b"DicionarioLibrasGIF_v2").hexdigest()[:16], 16) % (1 << 31)

        model = genanki.Model(
            model_id,
            'Dicionário Libras - GIF v2',
            fields=[
                {'name': 'Palavra'},
                {'name': 'Video'},
                {'name': 'SignWriting'},
                {'name': 'Significado'},
                {'name': 'Exemplo'},
                {'name': 'Fonte'},
                {'name': 'LinkOriginal'},
            ],
            templates=[
                {
                    'name': 'Frente -> Verso',
                    'qfmt': (
                        '<div class="anki-card front-card">'
                        '  <div class="main-word">{{Palavra}}</div>'
                        '</div>'
                    ),
                    'afmt': (
                        '<div class="anki-card back-card">'
                        '  <div class="main-word front-preview">{{Palavra}}</div>'
                        '  <hr id="answer">'
                        '  {{Video}}'
                        '  {{#SignWriting}}'
                        '  <div class="box signwriting">'
                        '    <div class="media-label">SignWriting (Escrita do Sinal)</div>'
                        '    <div class="sw-container">{{SignWriting}}</div>'
                        '  </div>'
                        '  {{/SignWriting}}'
                        '  <br>'
                        '  {{Significado}}'
                        '  {{#Exemplo}}<br>{{Exemplo}}{{/Exemplo}}'
                        '  <br>'
                        '  <div style="font-size: 0.6em; opacity: 0.6; text-align: right; margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 8px;">'
                        '    Fontes: {{Fonte}} | {{LinkOriginal}}'
                        '  </div>'
                        '</div>'
                    ),
                },
            ],
            css="""
.card {
  font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
  background-color: #f3f4f6;
  color: #1f2937;
  text-align: center;
  margin: 0;
  padding: 15px;
}
.nightMode { background-color: #111827 !important; color: #f3f4f6 !important; }
.anki-card {
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
  max-width: 500px;
  margin: 20px auto;
  padding: 30px 20px;
  box-sizing: border-box;
  border: 1px solid #e5e7eb;
  text-align: center;
}
.nightMode .anki-card { background: #1f2937; border-color: #374151; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); }
.main-word { font-size: 2.4rem; font-weight: 800; color: #111827; letter-spacing: -0.5px; margin: 10px 0; line-height: 1.25; }
.nightMode .main-word { color: #ffffff; }
.front-preview { font-size: 1.8rem; font-weight: 700; opacity: 0.8; }
#answer { border: none; height: 2px; background: linear-gradient(90deg, transparent, #3b82f6, transparent); margin: 20px auto; width: 80%; }
.nightMode #answer { background: linear-gradient(90deg, transparent, #60a5fa, transparent); }
.box {
  text-align: left;
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background-color: #f9fafb;
  color: #1f2937;
  font-size: 0.9em;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.02);
}
.nightMode .box { background-color: #111827; color: #f3f4f6; border-color: #374151; }
.meaning { border-left: 4px solid #3b82f6; }
.nightMode .meaning { border-left: 4px solid #60a5fa; }
.example { border-left: 4px solid #10b981; font-style: italic; color: #4b5563; }
.nightMode .example { border-left: 4px solid #34d399; color: #d1d5db; }
.signwriting { border-left: 4px solid #8b5cf6; text-align: center; }
.nightMode .signwriting { border-left: 4px solid #a78bfa; }
.sw-container img { max-height: 160px; margin: 10px auto; display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.08)); }
.nightMode .sw-container img { filter: invert(0.9) hue-rotate(180deg) drop-shadow(0 2px 4px rgba(255,255,255,0.1)); }
.media-label { font-weight: 600; font-size: 0.85em; color: #4b5563; margin-bottom: 5px; }
.nightMode .media-label { color: #9ca3af; }
"""
        )

        deck = genanki.Deck(deck_id, self.deck_name)
        media_files = []
        cards_adicionados = 0

        for i, card_info in enumerate(self.staged_cards):
            pct = int((i / total_cards) * 90)
            palavra = card_info.get("palavra", "Sinal")
            fonte = card_info.get("fonte", "")
            fonte_label = FONTES.get(fonte, fonte)

            self.progress_changed.emit(pct, f"Processando mídia para '{palavra}' ({i+1}/{total_cards})...")

            # 1. Obter vídeo (download se necessário)
            v_url = card_info.get("video_url", "")
            v_file = card_info.get("video_file", "")
            media_filename = get_safe_media_filename(fonte, palavra)
            video_dest = os.path.join(media_dir, media_filename)
            base_name = os.path.splitext(media_filename)[0]
            gif_filename = f"{base_name}.gif"
            gif_dest = os.path.join(converted_dir, gif_filename)

            # Verificar se GIF já existe
            if not os.path.exists(gif_dest):
                # Verificar se vídeo fonte existe
                if not os.path.exists(video_dest):
                    if v_url:
                        self.progress_changed.emit(pct, f"Baixando vídeo de '{palavra}'...")
                        download_video(v_url, video_dest)

                # Converter para GIF se vídeo existir
                if os.path.exists(video_dest):
                    self.progress_changed.emit(pct, f"Convertendo '{palavra}' para GIF...")
                    convert_video_to_gif(video_dest, gif_dest)

            if not os.path.exists(gif_dest):
                # Se não conseguiu GIF, pula o card
                continue

            if gif_dest not in media_files:
                media_files.append(gif_dest)

            video_html = (
                f'<div style="text-align:center;margin:10px 0;">'
                f'<img src="{gif_filename}" style="max-width:100%;max-height:240px;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,0.15);">'
                f'</div>'
            )

            # 2. Obter SignWriting se solicitado
            signwriting_html = ""
            if card_info.get("incluir_signwriting"):
                sw_info = card_info.get("sw_info")
                if sw_info and sw_info.get("swu"):
                    swu = sw_info["swu"]
                    clean_name = db.get_base_palavra(db.normalize_word(palavra))
                    sw_filename = f"sw_{clean_name}.svg"
                    sw_path = os.path.join(media_dir, sw_filename)

                    if not os.path.exists(sw_path):
                        download_signwriting_svg(swu, sw_path)

                    if os.path.exists(sw_path):
                        if sw_path not in media_files:
                            media_files.append(sw_path)
                        signwriting_html = f'<img src="{sw_filename}" class="signwriting-svg" alt="SignWriting">'

            # 3. Formatar Texto Personalizado
            custom_text = card_info.get("texto_personalizado", "").strip()
            if custom_text:
                formatted_text = custom_text.replace("\n", "<br>")
                significado_html = f'<div class="box meaning">{formatted_text}</div>'
            else:
                significado_html = ""

            # 4. Links e tags
            source_link = card_info.get("source_link", "")
            links_html = f'<a href="{source_link}" style="color:#0066cc;text-decoration:none;font-weight:bold;">{fonte_label}</a>' if source_link else ""
            tags = [fonte, "LibrasGUI"]

            note = genanki.Note(
                model=model,
                fields=[
                    palavra.upper(),
                    video_html,
                    signwriting_html,
                    significado_html,
                    "",
                    fonte_label,
                    links_html
                ],
                tags=tags
            )
            deck.add_note(note)
            cards_adicionados += 1

        if cards_adicionados == 0:
            self.finished_build.emit(False, "Nenhum card pôde ser gerado (falha ao converter GIFs).")
            return

        self.progress_changed.emit(95, "Empacotando arquivo .apkg...")
        output_apkg = os.path.join(output_dir, self.output_filename)
        os.makedirs(os.path.dirname(output_apkg), exist_ok=True)

        package = genanki.Package(deck)
        package.media_files = media_files
        package.write_to_file(output_apkg)

        self.progress_changed.emit(100, f"Deck gerado com sucesso com {cards_adicionados} cards!")
        self.finished_build.emit(True, output_apkg)
