import requests
import re
import concurrent.futures
from libras_anki.db import normalize_word

def fetch_rede_surdos(query):
    """Busca posts sobre a palavra na Rede de Surdos da UFC via API WordPress."""
    url = f"https://redesurdosce.ufc.br/wp-json/wp/v2/posts?search={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            results = []
            norm_query = normalize_word(query)
            pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
            
            for item in data:
                title = item.get('title', {}).get('rendered', '')
                norm_title = normalize_word(title)
                
                # Filtragem com base em limites de palavras (igual ao app Dart)
                if pattern.search(norm_title):
                    content = item.get('content', {}).get('rendered', '')
                    excerpt = item.get('excerpt', {}).get('rendered', '')
                    link = item.get('link', '')
                    
                    # Extração do ID do YouTube no iframe ou link
                    youtube_id = None
                    yt_match = re.search(r'src="https:\/\/www\.youtube\.com\/embed\/([^"?]+)', content)
                    if yt_match:
                        youtube_id = yt_match.group(1)
                    else:
                        yt_match_text = re.search(r'https:\/\/www\.youtube\.com\/watch\?v=([^"&\s]+)', content)
                        if yt_match_text:
                            youtube_id = yt_match_text.group(1)
                            
                    video_url = f"https://www.youtube.com/watch?v={youtube_id}" if youtube_id else None
                    results.append({
                        "palavra": title,
                        "descricao": excerpt if excerpt else content,
                        "video_url": video_url,
                        "source_link": link,
                        "fonte": "RedeSurdos"
                    })
            return results
    except Exception as e:
        print(f"[Scraper UFC] Erro ao buscar: {e}")
    return []

def fetch_ufv(query):
    """Busca a palavra no Dicionário da UFV."""
    url = f"https://sistemas.cead.ufv.br/capes/dicionario/?s={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            html = r.text
            norm_query = normalize_word(query)
            pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
            
            # Localizar links e títulos
            matches = re.findall(r'<a href="([^"]+)">(?:\s*)<h4>([^<]+)</h4>', html)
            results = []
            
            # Função para buscar detalhes de cada link encontrado
            def get_detail(item):
                link, title = item
                title = title.strip()
                norm_title = normalize_word(title)
                if pattern.search(norm_title):
                    try:
                        res_detail = requests.get(link, headers=headers, timeout=10)
                        if res_detail.status_code == 200:
                            v_match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', res_detail.text)
                            if v_match:
                                return {
                                    "palavra": title,
                                    "descricao": "",
                                    "video_url": v_match.group(1).strip(),
                                    "source_link": link,
                                    "fonte": "UFV"
                                }
                    except Exception:
                        pass
                return None

            if matches:
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    detail_results = executor.map(get_detail, matches)
                for res in detail_results:
                    if res:
                        results.append(res)
                        
            return results
    except Exception as e:
        print(f"[Scraper UFV] Erro ao buscar: {e}")
    return []

def fetch_uff(query):
    """Busca a palavra na Libras Acadêmica da UFF via API WordPress."""
    url = f"https://librasacademica.uff.br/wp-json/wp/v2/posts?search={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            results = []
            norm_query = normalize_word(query)
            pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
            
            for item in data:
                title = item.get('title', {}).get('rendered', '')
                norm_title = normalize_word(title)
                
                if pattern.search(norm_title):
                    content = item.get('content', {}).get('rendered', '')
                    excerpt = item.get('excerpt', {}).get('rendered', '')
                    link = item.get('link', '')
                    
                    video_url, youtube_id = extract_uff_video_and_youtube_id(content)
                    final_video_url = video_url
                    if not final_video_url and youtube_id:
                        final_video_url = f"https://www.youtube.com/watch?v={youtube_id}"
                        
                    results.append({
                        "palavra": title,
                        "descricao": excerpt if excerpt else content,
                        "video_url": final_video_url,
                        "source_link": link,
                        "fonte": "LibrasAcademicaUFF"
                    })
            return results
    except Exception as e:
        print(f"[Scraper UFF] Erro ao buscar: {e}")
    return []

def extract_uff_video_and_youtube_id(content):
    """Auxiliar para extrair URLs de vídeos ou IDs do YouTube de postagens da UFF."""
    video_url = None
    youtube_id = None
    
    # 1. Tag de vídeo direta
    video_match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', content)
    if video_match:
        video_url = video_match.group(1)
        
    # 2. YouTube Embed
    if not video_url:
        yt_match = re.search(r'src=["\']https:\/\/www\.youtube\.com\/embed\/([^"\'?]+)', content)
        if yt_match:
            youtube_id = yt_match.group(1)
            return video_url, youtube_id
            
    # 3. YouTube Watch URL
    if not youtube_id and not video_url:
        yt_text_match = re.search(r'https:\/\/www\.youtube\.com\/watch\?v=([^"\'&\s]+)', content)
        if yt_text_match:
            youtube_id = yt_text_match.group(1)
            return video_url, youtube_id
            
    # 4. YouTube short link
    if not youtube_id and not video_url:
        yt_short_match = re.search(r'https:\/\/youtu\.be\/([^"\'&\s<]+)', content)
        if yt_short_match:
            youtube_id = yt_short_match.group(1)
            return video_url, youtube_id
            
    # 5. Link MP4 direto em tags src
    if not video_url:
        mp4_match = re.search(r'src=["\'](http[^"\']+?\.mp4)["\']', content)
        if mp4_match:
            video_url = mp4_match.group(1)
            
    return video_url, youtube_id

def fetch_spread_the_sign(query):
    """Busca a palavra no Spread the Sign."""
    url = f"https://www.spreadthesign.com/pt.br/search/?q={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            html = r.text
            results = []
            norm_query = normalize_word(query)
            pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
            
            # 1. Verifica se há um vídeo direto na página inicial da pesquisa (única correspondência)
            video_match = re.search(r'<video[^>]*src=["\'](https:\/\/media\.spreadthesign\.com\/video\/mp4\/[^"\']+)["\']', html)
            if video_match:
                video_url = video_match.group(1)
                title_match = re.search(r'<span class="flag-icon flag-icon-br bordered"><\/span>\s*([^<\n]+)', html)
                if title_match:
                    title = title_match.group(1).strip()
                    norm_title = normalize_word(title)
                    if pattern.search(norm_title):
                        results.append({
                            "palavra": title,
                            "descricao": "",
                            "video_url": video_url,
                            "source_link": url,
                            "fonte": "SpreadTheSign"
                        })
                        
            # 2. Processa múltiplos links da página de resultados
            matches = re.findall(r'<div class="search-result-title">\s*<a href="(\/pt\.br\/word\/[^"]+)"[^>]*>\s*([^<\n]+)', html)
            
            detail_links = []
            for link, title in matches:
                title = title.strip()
                norm_title = normalize_word(title)
                if pattern.search(norm_title):
                    detail_links.append((f"https://www.spreadthesign.com{link}", title))
                    
            # Crawl concorrente nos detalhes das palavras encontradas
            def crawl_sts_detail(item):
                d_url, d_title = item
                try:
                    res_html = requests.get(d_url, headers=headers, timeout=10).text
                    v_match = re.search(r'<video[^>]*src=["\'](https:\/\/media\.spreadthesign\.com\/video\/mp4\/[^"\']+)["\']', res_html)
                    if v_match:
                        return {
                            "palavra": d_title,
                            "descricao": "",
                            "video_url": v_match.group(1),
                            "source_link": d_url,
                            "fonte": "SpreadTheSign"
                        }
                except Exception:
                    pass
                return None
                
            if detail_links:
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    detail_results = executor.map(crawl_sts_detail, detail_links)
                for res in detail_results:
                    if res:
                        if not any(r['video_url'] == res['video_url'] for r in results):
                            results.append(res)
                            
            return results
    except Exception as e:
        print(f"[Scraper SpreadTheSign] Erro ao buscar: {e}")
    return []
