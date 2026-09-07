import os
import sqlite3
import unicodedata
import csv
import re


def get_db_path():
    from libras_anki.utils import get_output_dir
    output_dir = get_output_dir(None)
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, "libras.db")


def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_word(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    no_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return no_accents.lower().strip()


def get_base_palavra(normalized):
    """Strip trailing digits — handles INES numbered variants (PRETO1, PRETO2 → preto)."""
    base = re.sub(r'\d+$', '', normalized).strip()
    return base if base else normalized


def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sinais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fonte TEXT,
                palavra TEXT,
                normalized_palavra TEXT,
                base_palavra TEXT,
                descricao TEXT,
                libras TEXT,
                exemplo TEXT,
                video_url TEXT,
                video_file TEXT,
                image_url TEXT,
                source_link TEXT,
                tags TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_normalized_palavra ON sinais(normalized_palavra)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fonte ON sinais(fonte)")

        # Migration: add base_palavra column to existing DBs
        try:
            cursor.execute("ALTER TABLE sinais ADD COLUMN base_palavra TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_base_palavra ON sinais(base_palavra)")

        # Populate base_palavra for any rows missing it
        cursor.execute("""
            UPDATE sinais
            SET base_palavra = LOWER(TRIM(RTRIM(normalized_palavra, '0123456789')))
            WHERE base_palavra IS NULL OR base_palavra = ''
        """)
        conn.commit()
    finally:
        conn.close()


def lookup_sinal(fonte, palavra):
    """Returns all records matching the word OR any numbered variant of it."""
    conn = get_db_connection()
    norm = normalize_word(palavra)
    base = get_base_palavra(norm)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sinais WHERE fonte = ? AND (normalized_palavra = ? OR base_palavra = ?)",
            (fonte, norm, base)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def insert_or_update_sinal(fonte, palavra, descricao="", libras="", exemplo="", video_url="", video_file="", image_url="", source_link="", tags=""):
    conn = get_db_connection()
    norm = normalize_word(palavra)
    base = get_base_palavra(norm)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sinais WHERE fonte = ? AND palavra = ?",
            (fonte, palavra)
        )
        row = cursor.fetchone()

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
            """, (descricao, libras, exemplo, video_url, video_file, image_url, source_link, tags, norm, base, sinal_id))
        else:
            cursor.execute("""
                INSERT INTO sinais (fonte, palavra, normalized_palavra, base_palavra, descricao, libras, exemplo, video_url, video_file, image_url, source_link, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fonte, palavra, norm, base, descricao, libras, exemplo, video_url, video_file, image_url, source_link, tags))
        conn.commit()
    finally:
        conn.close()


def import_existing_ufc_data():
    from libras_anki.utils import get_output_dir
    output_base = get_output_dir(None)
    if not os.path.exists(output_base):
        return

    init_db()

    pastas = []
    for d in os.listdir(output_base):
        path = os.path.join(output_base, d)
        if os.path.isdir(path) and d not in ("ines", "output") and not d.startswith('.'):
            pastas.append(d)

    if not pastas:
        return

    print(f"[DB] Analisando {len(pastas)} pastas para importar dados da UFC no SQLite...")

    importados = 0
    for cat in pastas:
        cat_dir = os.path.join(output_base, cat)
        csv_path = os.path.join(cat_dir, "video_links.csv")
        if not os.path.exists(csv_path):
            csv_path = os.path.join(cat_dir, "word_links.csv")

        if not os.path.exists(csv_path):
            continue

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    palavra = row.get('Palavra')
                    if not palavra:
                        continue

                    word_link = row.get('Link') or row.get('Word_Link') or ""
                    video_link = row.get('Video_Link') or ""

                    texto = ""
                    vid_id = "".join([c for c in palavra if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_').lower()
                    if vid_id:
                        md_path = os.path.join(cat_dir, "sinais", f"{vid_id}.md")
                        if os.path.exists(md_path):
                            with open(md_path, 'r', encoding='utf-8') as mf:
                                texto = mf.read()

                    video_file = ""
                    nfkd = unicodedata.normalize('NFKD', palavra)
                    no_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
                    clean_id = "".join([c for c in no_accents if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_').lower()

                    if clean_id:
                        check_filename = f"_{clean_id}.mp4"
                        check_path = os.path.join(cat_dir, "media_converted", check_filename)
                        if os.path.exists(check_path):
                            video_file = os.path.join(cat, "media_converted", check_filename)

                    cat_cleaned = cat.replace('_', ' ').title().strip().replace(' ', '_').replace(',', '_').replace('"', '').replace("'", "")
                    tags_str = f"RedeSurdos, Categoria::{cat_cleaned}"
                    insert_or_update_sinal(
                        fonte="RedeSurdos",
                        palavra=palavra,
                        descricao=texto,
                        video_url=video_link,
                        video_file=video_file,
                        source_link=word_link,
                        tags=tags_str
                    )
                    importados += 1
        except Exception as e:
            print(f"[DB] Erro ao importar categoria '{cat}': {e}")

    if importados > 0:
        print(f"[DB] Importação concluída. {importados} registros UFC cadastrados no SQLite.")


def read_custom_words_csv(csv_path):
    if not os.path.exists(csv_path):
        print(f"[DB] Erro: Arquivo CSV '{csv_path}' não encontrado.")
        return []

    words = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return []

            col_idx = 0
            for idx, col in enumerate(header):
                if col.strip().lower() in ('palavra', 'word', 'sinal', 'nome'):
                    col_idx = idx
                    break

            if header[col_idx].strip().lower() not in ('palavra', 'word', 'sinal', 'nome'):
                words.append(header[col_idx].strip())

            for row in reader:
                if row and len(row) > col_idx:
                    val = row[col_idx].strip()
                    if val:
                        words.append(val)
    except Exception as e:
        print(f"[DB] Erro ao ler CSV personalizado: {e}")
        return []

    print(f"[DB] Carregadas {len(words)} palavras do CSV.")
    return words


def lookup_words_by_tags_and_source(tags_list, sources_list=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        query = "SELECT DISTINCT palavra FROM sinais WHERE 1=1"
        params = []

        if sources_list and "Ambos" not in sources_list:
            placeholders = ",".join(["?"] * len(sources_list))
            query += f" AND fonte IN ({placeholders})"
            params.extend(sources_list)

        if tags_list:
            tag_conditions = []
            for tag in tags_list:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            query += f" AND ({' OR '.join(tag_conditions)})"

        cursor.execute(query, params)
        return [row['palavra'] for row in cursor.fetchall()]
    finally:
        conn.close()
