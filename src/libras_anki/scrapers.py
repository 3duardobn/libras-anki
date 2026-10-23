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


def fetch_ccb(query):
    """Busca a palavra no glossário CCB (Congregação Cristã no Brasil)."""
    base_url = "https://congregacaocristanobrasil.org.br/libras"
    service_url = "https://congregacaocristanobrasil.org.br/service/tss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": base_url
    }
    norm_query = normalize_word(query)
    pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
    results = []
    seen = set()

    try:
        # Busca direta ou consulta de assuntos
        for cat_id in range(1, 15):
            payload = {"a": "assuntos", "cat": str(cat_id), "b": ""}
            r = requests.post(service_url, data=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                html = r.text
                matches = re.findall(r'<a[^>]+data-video="([^"]+)"[^>]*>(.*?)<\/a>', html, re.DOTALL)
                for video_id, raw_title in matches:
                    clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
                    norm_title = normalize_word(clean_title)
                    if pattern.search(norm_title) and video_id not in seen:
                        seen.add(video_id)
                        results.append({
                            "palavra": clean_title,
                            "descricao": f"Sinal religioso / bíblico (CCB)",
                            "video_url": f"https://www.youtube.com/watch?v={video_id}",
                            "source_link": base_url,
                            "fonte": "CCB"
                        })
    except Exception as e:
        print(f"[Scraper CCB] Erro ao buscar: {e}")
    return results


def fetch_economia(query):
    """Busca a palavra no Glossário de Economia em Libras."""
    url = "https://raw.githubusercontent.com/glossariolibras/economia/master/index.html"
    headers = {"User-Agent": "LibrasAnki/1.0"}
    norm_query = normalize_word(query)
    pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
    results = []

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            html = r.text
            # Encontrar blocos de modal
            modals = re.findall(r'<div class="modal-content">(.*?)<\/div>\s*<\/div>\s*<\/div>', html, re.DOTALL)
            for modal in modals:
                title_match = re.search(r'<h[1-3][^>]*class="modal-title"[^>]*>(.*?)<\/h[1-3]>', modal)
                if not title_match:
                    continue
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                norm_title = normalize_word(title)
                if pattern.search(norm_title):
                    yt_match = re.search(r'embed\/([a-zA-Z0-9_-]+)', modal)
                    yt_id = yt_match.group(1) if yt_match else None
                    if yt_id:
                        results.append({
                            "palavra": title,
                            "descricao": "Termo de Economia e Finanças",
                            "video_url": f"https://www.youtube.com/watch?v={yt_id}",
                            "source_link": f"https://glossariolibras.github.io/economia/index#{title}",
                            "fonte": "Economia"
                        })
    except Exception as e:
        print(f"[Scraper Economia] Erro ao buscar: {e}")
    return results


_fesai_config = {}


def _get_fesai_credentials():
    """Obtém dinamicamente o endpoint e a API key do AppSync no site do FESAI."""
    global _fesai_config
    if _fesai_config.get("api_key") and _fesai_config.get("graphql_url"):
        return _fesai_config["graphql_url"], _fesai_config["api_key"]

    base_url = "https://www.fesai.com.br/"
    headers = {"User-Agent": "LibrasAnki/1.0"}
    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        r.raise_for_status()
        match_script = re.search(r'src=["\'](main\.[a-zA-Z0-9]+\.js)["\']', r.text)
        if match_script:
            js_url = f"{base_url.rstrip('/')}/{match_script.group(1)}"
            r_js = requests.get(js_url, headers=headers, timeout=10)
            r_js.raise_for_status()

            key_match = re.search(r'aws_appsync_apiKey\s*:\s*["\']([^"\']+)["\']', r_js.text)
            endpoint_match = re.search(r'aws_appsync_graphqlEndpoint\s*:\s*["\']([^"\']+)["\']', r_js.text)

            if key_match:
                _fesai_config["api_key"] = key_match.group(1)
            if endpoint_match:
                _fesai_config["graphql_url"] = endpoint_match.group(1)
    except Exception as e:
        print(f"[Scraper FESAI] Não foi possível obter credenciais do site: {e}")

    graphql_url = _fesai_config.get(
        "graphql_url",
        "https://5wlf3cebpnd2zn52osshpmxhdm.appsync-api.us-east-1.amazonaws.com/graphql"
    )
    api_key = _fesai_config.get("api_key")
    return graphql_url, api_key


def fetch_fesai(query):
    """Busca a palavra no glossário FESAI (Termos técnicos de TI)."""
    graphql_url, api_key = _get_fesai_credentials()
    if not api_key or not graphql_url:
        print("[Scraper FESAI] Chave de API não disponível dinamicamente.")
        return []

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "User-Agent": "LibrasAnki/1.0"
    }
    query_graphql = """
    query ListSinals {
      listSinals(limit: 1000) {
        items {
          name
          videos
        }
      }
    }
    """
    norm_query = normalize_word(query)
    pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
    results = []

    try:
        r = requests.post(graphql_url, json={"query": query_graphql}, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", {}).get("listSinals", {}).get("items", [])
            for item in items:
                name = (item.get("name") or "").strip()
                norm_name = normalize_word(name)
                if pattern.search(norm_name):
                    videos = item.get("videos") or []
                    video_url = videos[0] if videos else None
                    if video_url:
                        results.append({
                            "palavra": name,
                            "descricao": "Termo técnico de Tecnologia e Desenvolvimento (FESAI)",
                            "video_url": video_url,
                            "source_link": "https://www.fesai.com.br/",
                            "fonte": "FESAI"
                        })
    except Exception as e:
        print(f"[Scraper FESAI] Erro ao buscar: {e}")
    return results


def fetch_pibic(query):
    """Busca a palavra no Projeto PIBIC (Design, Animação e Fotografia)."""
    base_url = "http://www.pibic.progedu.com.br/libras"
    pages = [("design", "Design"), ("animacao", "Animação"), ("fotografia", "Fotografia")]
    headers = {"User-Agent": "LibrasAnki/1.0"}
    norm_query = normalize_word(query)
    pattern = re.compile(rf'\b{re.escape(norm_query)}\b', re.IGNORECASE)
    results = []
    seen = set()

    for slug, cat_name in pages:
        try:
            r = requests.get(f"{base_url}/{slug}", headers=headers, timeout=15)
            if r.status_code == 200:
                sections = re.findall(r'<section[^>]*>(.*?)<\/section>', r.text, re.DOTALL)
                for section in sections:
                    yt_match = re.search(r'embed\/([a-zA-Z0-9_-]+)', section)
                    if not yt_match:
                        continue
                    yt_id = yt_match.group(1)
                    title_match = re.search(r'<h[1-3][^>]*>(.*?)<\/h[1-3]>', section)
                    if not title_match:
                        continue
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    norm_title = normalize_word(title)
                    if pattern.search(norm_title) and (title.lower(), yt_id) not in seen:
                        seen.add((title.lower(), yt_id))
                        results.append({
                            "palavra": title,
                            "descricao": f"Termo técnico de {cat_name} (PIBIC)",
                            "video_url": f"https://www.youtube.com/watch?v={yt_id}",
                            "source_link": f"{base_url}/{slug}",
                            "fonte": "PIBIC"
                        })
        except Exception as e:
            print(f"[Scraper PIBIC - {cat_name}] Erro ao buscar: {e}")
    return results
