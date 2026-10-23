import os
import csv
import json
import requests
import unicodedata
import genanki
import re
import hashlib
import concurrent.futures
from libras_anki.utils import get_output_dir, sanitize_svg_for_qt
from libras_anki.convert_videos import convert_video_to_gif
from libras_anki import db
from libras_anki import scrapers

FONTES = {
    "RedeSurdos": "Rede de Surdos (UFC)",
    "INES": "Dicionário INES",
    "UFV": "Dicionário UFV",
    "LibrasAcademicaUFF": "Libras Acadêmica (UFF)",
    "SpreadTheSign": "Spread the Sign",
    "CCB": "Glossário CCB (Religioso)",
    "Economia": "Glossário de Economia",
    "FESAI": "Glossário FESAI (TI)",
    "PIBIC": "Projeto PIBIC (Design/Artes)"
}


def get_safe_media_filename(source, word):
    nfkd = unicodedata.normalize('NFKD', word)
    no_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    clean = "".join([c for c in no_accents if c.isalnum() or c in (' ', '_')]).strip().lower().replace(' ', '_')
    if not clean:
        clean = f"sinal_{hashlib.md5(word.encode('utf-8')).hexdigest()[:8]}"
    return f"{source.lower()}_{clean}.mp4"


def init_dicionario():
    db.init_db()
    db.import_existing_ufc_data()

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM sinais WHERE fonte = 'INES'")
        row = cursor.fetchone()
        if row['count'] == 0:
            print("[Dicionário] Tabela do INES no SQLite está vazia. Importando dados do palavras.js...")
            import_ines_to_sqlite()
    finally:
        conn.close()


def clean_tag_part(part):
    if not part:
        return ""
    return str(part).strip().replace(' ', '_').replace(',', '_').replace('"', '').replace("'", "")


def fetch_ines_mappings():
    headers = {"User-Agent": "Mozilla/5.0"}
    base_url = "https://dicionario.ines.gov.br/public/site/js/"
    files = {"classes": "classes.js", "origem": "origem.js", "assunto": "assuntos.js", "mao": "mao.js"}

    mappings = {"classes": {}, "origem": {}, "assunto": {}, "mao": {}}

    for key, filename in files.items():
        url = base_url + filename
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            text = r.text.strip()

            match = re.search(r'=\s*(\[.*\])', text, re.DOTALL)
            if not match:
                match = re.search(r'\[.*\]', text, re.DOTALL)

            if match:
                json_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
                if json_str.endswith(';'):
                    json_str = json_str[:-1]
                data = json.loads(json_str)

                for item in data:
                    item_id = str(item.get('id', ''))
                    if not item_id:
                        continue
                    if key == "mao":
                        img_url = item.get('url', '')
                        mappings[key][item_id] = os.path.splitext(img_url)[0] if img_url else item.get('ordem', '')
                    else:
                        mappings[key][item_id] = item.get('nome', '')
            print(f"[Dicionário] Mapeamento '{key}' carregado com {len(mappings[key])} itens.")
        except Exception as e:
            print(f"[Dicionário] Erro ao carregar mapeamento '{key}' do INES: {e}")

    return mappings


def import_ines_to_sqlite():
    url = "https://dicionario.ines.gov.br/public/site/js/palavras.js"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        mappings = fetch_ines_mappings()
        classes_map = mappings["classes"]
        origem_map = mappings["origem"]
        assunto_map = mappings["assunto"]
        mao_map = mappings["mao"]

        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        text = r.text.strip()

        match = re.search(r'var\s+palavras\s*=\s*(.*);', text, re.DOTALL)
        if not match:
            match = re.search(r'\[.*\]', text, re.DOTALL)

        if match:
            json_str = match.group(0)
            if json_str.startswith('var'):
                json_str = re.sub(r'^var\s+palavras\s*=\s*', '', json_str)
            if json_str.endswith(';'):
                json_str = json_str[:-1]

            palavras = json.loads(json_str)
            print(f"[Dicionário] Carregadas {len(palavras)} palavras do INES. Gravando no SQLite...")

            conn = db.get_db_connection()
            try:
                cursor = conn.cursor()
                for p in palavras:
                    word = p.get('palavra')
                    if not word:
                        continue

                    video_name = p.get('video')
                    video_url = f"https://dicionario.ines.gov.br/public/media/palavras/videos/{video_name}" if video_name else ""

                    image_name = p.get('image')
                    image_url = f"https://dicionario.ines.gov.br/public/media/palavras/images/{image_name}" if image_name else ""

                    tags_list = ["INES"]

                    classe_id = str(p.get('classe', ''))
                    if classe_id in classes_map:
                        tags_list.append(f"Gramatica::{clean_tag_part(classes_map[classe_id])}")

                    assunto_id = str(p.get('assunto', ''))
                    if assunto_id in assunto_map:
                        tags_list.append(f"Assunto::{clean_tag_part(assunto_map[assunto_id])}")

                    origem_id = str(p.get('origem', ''))
                    if origem_id in origem_map:
                        tags_list.append(f"Origem::{clean_tag_part(origem_map[origem_id])}")

                    mao_id = str(p.get('mao', ''))
                    if mao_id in mao_map:
                        tags_list.append(f"Mao::{clean_tag_part(mao_map[mao_id])}")

                    tags_str = ", ".join(tags_list)
                    norm = db.normalize_word(word)
                    base = db.get_base_palavra(norm)

                    cursor.execute("SELECT id FROM sinais WHERE fonte = ? AND palavra = ?", ("INES", word))
                    row = cursor.fetchone()

                    descricao = p.get('descricao', '')
                    libras = p.get('libras', '')
                    exemplo = p.get('exemplo', '')
                    source_link = f"https://dicionario.ines.gov.br/pt/search?word={requests.utils.quote(word)}"

                    if row:
                        sinal_id = row['id']
                        cursor.execute("""
                            UPDATE sinais
                            SET descricao = COALESCE(NULLIF(?, ''), descricao),
                                libras = COALESCE(NULLIF(?, ''), libras),
                                exemplo = COALESCE(NULLIF(?, ''), exemplo),
                                video_url = COALESCE(NULLIF(?, ''), video_url),
                                video_file = COALESCE(NULLIF(?, ''), video_file),
                                image_url = COALESCE(NULLIF(?, ''), image_url),
                                source_link = COALESCE(NULLIF(?, ''), source_link),
                                tags = COALESCE(NULLIF(?, ''), tags),
                                normalized_palavra = ?,
                                base_palavra = ?
                            WHERE id = ?
                        """, (descricao, libras, exemplo, video_url, video_name, image_url, source_link, tags_str, norm, base, sinal_id))
                    else:
                        cursor.execute("""
                            INSERT INTO sinais (fonte, palavra, normalized_palavra, base_palavra, descricao, libras, exemplo, video_url, video_file, image_url, source_link, tags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, ("INES", word, norm, base, descricao, libras, exemplo, video_url, video_name, image_url, source_link, tags_str))
                conn.commit()
            finally:
                conn.close()
            print("[Dicionário] Sucesso ao importar base do INES para o SQLite.")
    except Exception as e:
        print(f"[Dicionário] Erro ao importar base do INES: {e}")


def search_word_in_all_sources(word, source="Ambos"):
    word_norm = db.normalize_word(word)
    results = []

    fontes_pesquisa = [source] if source != "Ambos" else list(FONTES.keys())

    for f in fontes_pesquisa:
        local_res = db.lookup_sinal(f, word_norm)
        if local_res:
            results.extend(local_res)

    if results:
        found_sources = {r['fonte'] for r in results}
        missing_sources = [f for f in fontes_pesquisa if f not in found_sources]
    else:
        missing_sources = fontes_pesquisa

    for f in missing_sources:
        if f == "INES":
            continue

        print(f"[Dicionário] Buscando '{word}' remotamente na fonte: {FONTES[f]}...")
        online_res = []
        if f == "RedeSurdos":
            online_res = scrapers.fetch_rede_surdos(word)
        elif f == "UFV":
            online_res = scrapers.fetch_ufv(word)
        elif f == "LibrasAcademicaUFF":
            online_res = scrapers.fetch_uff(word)
        elif f == "SpreadTheSign":
            online_res = scrapers.fetch_spread_the_sign(word)
        elif f == "CCB":
            online_res = scrapers.fetch_ccb(word)
        elif f == "Economia":
            online_res = scrapers.fetch_economia(word)
        elif f == "FESAI":
            online_res = scrapers.fetch_fesai(word)
        elif f == "PIBIC":
            online_res = scrapers.fetch_pibic(word)

        if online_res:
            print(f"  [→] Encontrados {len(online_res)} resultados online.")
            for r in online_res:
                db.insert_or_update_sinal(
                    fonte=r['fonte'],
                    palavra=r['palavra'],
                    descricao=r['descricao'],
                    video_url=r['video_url'],
                    source_link=r['source_link'],
                    tags=r['fonte']
                )
            results.extend(db.lookup_sinal(f, word_norm))

    return results


def download_signwriting_svg(swu, dest_path):
    if not swu:
        return False
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return True

    headers = {"User-Agent": "LibrasAnki/1.0 (SignWriting Generator)"}
    url = f"https://signpuddle.com/server/swu/svg/{requests.utils.quote(swu, safe='')}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200 and r.content.lstrip().startswith(b"<svg"):
            clean_content = sanitize_svg_for_qt(r.content)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(clean_content)
            return True
    except Exception as e:
        print(f"  [SignWriting] Erro ao baixar SVG: {e}")
    return False


def download_video(video_url, dest_path):
    if not video_url:
        return False
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return True

    headers = {"User-Agent": "Mozilla/5.0"}

    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        import shutil
        import yt_dlp

        base_opts = {
            'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
            'outtmpl': dest_path,
            'quiet': True,
            'no_warnings': True,
            'remote_components': {'ejs:github'},
        }

        # Configurar runtime JavaScript para resolução de desafios (n-sig challenge)
        node_bin = shutil.which("node") or os.path.expanduser("~/.nvm/versions/node/v24.21.0/bin/node")
        if os.path.exists(node_bin):
            base_opts['js_runtimes'] = {'node': {'path': node_bin}}
        else:
            base_opts['js_runtimes'] = {'node': {}}

        # 1. Tentar com arquivo cookies.txt se fornecido no projeto
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cookies_txt = os.path.join(root_dir, "cookies.txt")
        if os.path.exists(cookies_txt):
            base_opts['cookiefile'] = cookies_txt

        # Tentar primeiro sem cookies de navegador
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                ydl.download([video_url])
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True
        except Exception:
            pass

        # 2. Se falhar (ex: 'Please sign in'), tentar automaticamente via cookies de navegadores instalados
        for browser in ['firefox', 'chrome', 'chromium', 'brave', 'edge']:
            try:
                browser_opts = dict(base_opts)
                browser_opts['cookiesfrombrowser'] = (browser, None, None, None)
                with yt_dlp.YoutubeDL(browser_opts) as ydl:
                    ydl.download([video_url])
                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                    return True
            except Exception:
                continue

        # Se todas as alternativas falharem
        if os.path.exists(dest_path):
            os.remove(dest_path)
        print(f"  [Erro] Falha ao baixar YouTube ({video_url}): O YouTube exigiu autenticação.")
        return False
    else:
        try:
            r = requests.get(video_url, headers=headers, stream=True, timeout=20)
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
        except Exception as e:
            print(f"  [Erro] Falha ao baixar link direto ({video_url}): {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False


def build_deck(palavras_list, source="Ambos", deck_name="Dicionário Libras", filename="dicionario_libras.apkg"):
    init_dicionario()

    # Dedup input list
    seen_words_dedup = set()
    unique_palavras = []
    for word in palavras_list:
        w_norm = db.normalize_word(word)
        if w_norm and w_norm not in seen_words_dedup:
            seen_words_dedup.add(w_norm)
            unique_palavras.append(word)
    palavras_list = unique_palavras

    output_base = get_output_dir(None)
    media_dir = os.path.join(output_base, "media")
    converted_dir = os.path.join(output_base, "media_converted")
    os.makedirs(media_dir, exist_ok=True)
    os.makedirs(converted_dir, exist_ok=True)

    # 1. Gather records from DB / online
    sinais_a_gerar = []
    for word in palavras_list:
        records = search_word_in_all_sources(word, source=source)
        if not records:
            print(f"[Dicionário] AVISO: Palavra '{word}' não encontrada em nenhuma fonte.")
        else:
            sinais_a_gerar.extend(records)

    if not sinais_a_gerar:
        print("[Dicionário] Erro: Nenhum sinal encontrado para a lista informada.")
        return False

    print(f"\n[Dicionário] Processando {len(sinais_a_gerar)} registros de sinais para o deck...")

    # 2. Download source videos concurrently
    def download_worker(sinal):
        if not sinal['video_url']:
            return None
        if sinal['fonte'] == 'INES':
            video_name = sinal['video_url'].split('/')[-1]
        else:
            video_name = get_safe_media_filename(sinal['fonte'], sinal['palavra'])

        dest_path = os.path.join(media_dir, video_name)

        # Skip download if GIF already converted — convert_worker will see it and skip too
        gif_cached = os.path.join(converted_dir, os.path.splitext(video_name)[0] + '.gif')
        if os.path.exists(gif_cached):
            return (sinal['id'], video_name, dest_path)

        if not os.path.exists(dest_path):
            print(f"  [Download] Baixando vídeo para '{sinal['palavra']}' ({sinal['fonte']})...")
            if not download_video(sinal['video_url'], dest_path):
                return None
        return (sinal['id'], video_name, dest_path)

    downloaded_tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for res in executor.map(download_worker, sinais_a_gerar):
            if res:
                downloaded_tasks.append(res)

    # 3. Convert to GIF concurrently
    print("\n[Dicionário] Convertendo vídeos para GIFs animados...")

    def convert_worker(task):
        sinal_id, video_name, in_path = task
        base_name = os.path.splitext(video_name)[0]
        gif_name = f"{base_name}.gif"
        gif_path = os.path.join(converted_dir, gif_name)
        if not os.path.exists(gif_path):
            success, err = convert_video_to_gif(in_path, gif_path)
            if not success:
                print(f"  [Erro FFmpeg GIF] {gif_name}: {err}")
                return None
        return (sinal_id, gif_path)

    converted_paths = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for res in executor.map(convert_worker, downloaded_tasks):
            if res:
                converted_paths.append(res)

    # Update DB with gif paths
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        for sinal_id, gif_path in converted_paths:
            rel_path = os.path.join("media_converted", os.path.basename(gif_path))
            cursor.execute("UPDATE sinais SET video_file = ? WHERE id = ?", (rel_path, sinal_id))
        conn.commit()
    finally:
        conn.close()

    # 4. Build Anki deck
    print(f"\n[Dicionário] Gerando pacote Anki...")

    deck_id = int(hashlib.md5(deck_name.encode()).hexdigest()[:16], 16) % (1 << 31)
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

    deck = genanki.Deck(deck_id, deck_name)
    media_files = []
    adicionados = 0

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()

        # Group by base_palavra — merges PRETO1 + PRETO2 into same card
        sinais_consolidados = {}
        seen_sinal_ids = set()
        for s in sinais_a_gerar:
            if s['id'] in seen_sinal_ids:
                continue
            seen_sinal_ids.add(s['id'])

            cursor.execute("SELECT * FROM sinais WHERE id = ?", (s['id'],))
            fetched = cursor.fetchone()
            if not fetched:
                continue
            row = dict(fetched)

            norm = row.get('normalized_palavra') or db.normalize_word(row['palavra'])
            base_key = row.get('base_palavra') or db.get_base_palavra(norm)
            if not base_key:
                continue
            if base_key not in sinais_consolidados:
                sinais_consolidados[base_key] = []
            sinais_consolidados[base_key].append(row)

        for base_key, group in sinais_consolidados.items():
            # Strip trailing digits from display word (PRETO1 → PRETO)
            palavra_display = re.sub(r'\d+$', '', group[0]['palavra']).strip().upper()

            significados_elements = []
            exemplos_list = []
            fontes_nomes = []
            links_list = []
            todas_tags = set()
            valid_videos = []

            for row in group:
                fonte_label = FONTES.get(row.get('fonte'), row.get('fonte'))
                if fonte_label not in fontes_nomes:
                    fontes_nomes.append(fonte_label)

                video_rel_path = row.get('video_file')
                if video_rel_path:
                    filename_only = os.path.basename(video_rel_path)
                    base_name = os.path.splitext(filename_only)[0]
                    gif_filename = f"{base_name}.gif"
                    gif_abs_path = os.path.join(converted_dir, gif_filename)
                    if os.path.exists(gif_abs_path):
                        valid_videos.append({
                            'label': row['palavra'].upper(),
                            'gif_filename': gif_filename,
                            'gif_path': gif_abs_path,
                        })

                sig = row.get('descricao', '').strip()
                if row.get('fonte') == 'INES' and row.get('libras'):
                    sig += f"<br><br><b>Glosas Libras:</b> {row.get('libras')}"
                if sig:
                    significados_elements.append(
                        f'<div class="box meaning" style="margin-bottom: 8px;">'
                        f'<b>{fonte_label}:</b><br>{sig}</div>'
                    )

                ex = row.get('exemplo', '').strip()
                if ex:
                    exemplos_list.append(f"<li><b>{fonte_label}:</b> {ex}</li>")

                link = row.get('source_link')
                if link:
                    links_list.append(f'<a href="{link}" style="color:#0066cc;text-decoration:none;font-weight:bold;">{fonte_label}</a>')

                tags_str = row.get('tags') or ""
                for t in tags_str.split(","):
                    t_clean = clean_tag_part(t)
                    if t_clean:
                        todas_tags.add(t_clean)

            if not valid_videos:
                continue

            # Add GIFs to package media list
            for v in valid_videos:
                if v['gif_path'] not in media_files:
                    media_files.append(v['gif_path'])

            # Build GIF HTML
            if len(valid_videos) == 1:
                v = valid_videos[0]
                video_html = (
                    f'<div style="text-align:center;margin:10px 0;">'
                    f'<img src="{v["gif_filename"]}" style="max-width:100%;max-height:240px;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,0.15);">'
                    f'</div>'
                )
            else:
                # Multiple variants side by side (PRETO1 + PRETO2, or multi-source)
                gif_elements = []
                for v in valid_videos:
                    gif_elements.append(
                        f'<div style="text-align:center;flex:1;min-width:160px;max-width:240px;margin:5px;">'
                        f'<div class="media-label">{v["label"]}</div>'
                        f'<img src="{v["gif_filename"]}" style="width:100%;height:auto;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,0.15);">'
                        f'</div>'
                    )
                video_html = (
                    f'<div style="display:flex;flex-wrap:wrap;justify-content:center;gap:15px;margin:10px 0;">'
                    f'{"".join(gif_elements)}'
                    f'</div>'
                )

            significados_html = "".join(significados_elements)
            exemplos_html = ""
            if exemplos_list:
                exemplos_html = (
                    f'<div class="box example">'
                    f'<b>Exemplos:</b><br>'
                    f'<ul style="margin:5px 0 0 20px;padding:0;">{"".join(exemplos_list)}</ul>'
                    f'</div>'
                )

            # Buscar SignWriting (SWU) correspondente
            signwriting_html = ""
            sw_info = db.lookup_signwriting(base_key)
            if sw_info and sw_info.get("swu"):
                swu = sw_info["swu"]
                sw_clean_name = f"sw_{base_key}.svg"
                sw_abs_path = os.path.join(output_base, "media", sw_clean_name)
                if download_signwriting_svg(swu, sw_abs_path):
                    if os.path.exists(sw_abs_path):
                        if sw_abs_path not in media_files:
                            media_files.append(sw_abs_path)
                        signwriting_html = f'<img src="{sw_clean_name}" class="signwriting-svg" alt="SignWriting {palavra_display}">'

            fontes_html = ", ".join(fontes_nomes)
            links_html = " | ".join(links_list)
            tags_list_anki = [t.replace(' ', '_') for t in todas_tags]

            note = genanki.Note(
                model=model,
                fields=[palavra_display, video_html, signwriting_html, significados_html, exemplos_html, fontes_html, links_html],
                tags=tags_list_anki
            )
            deck.add_note(note)
            adicionados += 1
    finally:
        conn.close()

    if adicionados == 0:
        print("[Dicionário] Erro: Nenhum card adicionado (GIFs ausentes).")
        return False

    output_apkg = os.path.join(output_base, filename)
    os.makedirs(os.path.dirname(output_apkg), exist_ok=True)
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(output_apkg)

    print(f"\n[Dicionário] SUCESSO! Deck '{deck_name}' gerado com {adicionados} cartas.")
    print(f"[Dicionário] Arquivo salvo em: {output_apkg}")
    return True


def scrape_all_ufc_to_db():
    print("[UFC] Iniciando importação completa de postagens da Rede de Surdos UFC...")
    page = 1
    total_imported = 0
    headers = {"User-Agent": "Mozilla/5.0"}

    while True:
        url = f"https://redesurdosce.ufc.br/wp-json/wp/v2/posts?per_page=100&page={page}"
        try:
            print(f"  [UFC] Carregando página {page}...")
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break

            for item in data:
                title = item.get('title', {}).get('rendered', '')
                if not title:
                    continue
                content = item.get('content', {}).get('rendered', '')
                excerpt = item.get('excerpt', {}).get('rendered', '')
                link = item.get('link', '')

                youtube_id = None
                yt_match = re.search(r'src="https:\/\/www\.youtube\.com\/embed\/([^"?]+)', content)
                if yt_match:
                    youtube_id = yt_match.group(1)
                else:
                    yt_match_text = re.search(r'https:\/\/www\.youtube\.com\/watch\?v=([^"&\s]+)', content)
                    if yt_match_text:
                        youtube_id = yt_match_text.group(1)

                video_url = f"https://www.youtube.com/watch?v={youtube_id}" if youtube_id else None

                db.insert_or_update_sinal(
                    fonte="RedeSurdos",
                    palavra=title,
                    descricao=excerpt if excerpt else content,
                    video_url=video_url,
                    source_link=link,
                    tags="RedeSurdos"
                )
                total_imported += 1
            page += 1
        except Exception as e:
            print(f"  [UFC] Finalizado ou erro na página {page}: {e}")
            break

    print(f"[UFC] Importação concluída. Total: {total_imported} postagens.")
    return total_imported
