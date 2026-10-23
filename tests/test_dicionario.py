import os
import csv
import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from libras_anki import db
from libras_anki import dicionario

@pytest.fixture(autouse=True)
def mock_db_path(tmp_path):
    """Garante que todos os testes usam um banco SQLite temporário isolado."""
    temp_db = os.path.join(tmp_path, "test_libras.db")
    with patch('libras_anki.db.get_db_path', return_value=temp_db):
        db.init_db(import_defaults=False)
        yield temp_db

def test_normalize_word():
    assert db.normalize_word("Abacaxi") == "abacaxi"
    assert db.normalize_word("Maçã") == "maca"
    assert db.normalize_word(" À Vista  ") == "a vista"
    assert db.normalize_word(None) == ""

def test_get_safe_media_filename():
    assert dicionario.get_safe_media_filename("UFV", "Maçã Verde") == "ufv_maca_verde.mp4"
    assert dicionario.get_safe_media_filename("INES", "À Vista") == "ines_a_vista.mp4"

def test_db_insert_and_lookup():
    db.insert_or_update_sinal(
        fonte="RedeSurdos",
        palavra="Abacaxi",
        descricao="Definição de abacaxi",
        video_url="https://youtube.com/watch?v=123"
    )
    
    # Busca com palavra exata
    res1 = db.lookup_sinal("RedeSurdos", "Abacaxi")
    assert len(res1) == 1
    assert res1[0]["palavra"] == "Abacaxi"
    assert res1[0]["descricao"] == "Definição de abacaxi"
    assert res1[0]["video_url"] == "https://youtube.com/watch?v=123"
    
    # Busca com palavra normalizada
    res2 = db.lookup_sinal("RedeSurdos", "abacaxi")
    assert len(res2) == 1
    
    # Atualização de registro existente
    db.insert_or_update_sinal(
        fonte="RedeSurdos",
        palavra="Abacaxi",
        descricao="Nova definição"
    )
    res3 = db.lookup_sinal("RedeSurdos", "Abacaxi")
    assert len(res3) == 1
    assert res3[0]["descricao"] == "Nova definição"
    assert res3[0]["video_url"] == "https://youtube.com/watch?v=123" # Preservou o não enviado

def test_read_custom_words_csv(tmp_path):
    csv_file = tmp_path / "test.csv"
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Palavra", "Outra Coluna"])
        writer.writerow(["Abacaxi", "Fruta"])
        writer.writerow(["Cachorro", "Animal"])
        
    words = db.read_custom_words_csv(str(csv_file))
    assert words == ["Abacaxi", "Cachorro"]

def test_search_word_in_all_sources_local():
    db.insert_or_update_sinal(
        fonte="INES",
        palavra="Cachorro",
        descricao="Definição INES"
    )
    
    # Deve encontrar localmente sem chamar scrapers
    with patch('libras_anki.scrapers.fetch_rede_surdos') as mock_ufc:
        res = dicionario.search_word_in_all_sources("Cachorro", source="INES")
        assert len(res) == 1
        assert res[0]["palavra"] == "Cachorro"
        assert res[0]["fonte"] == "INES"
        mock_ufc.assert_not_called()

def test_search_word_in_all_sources_remote():
    # Não existe no banco local
    mock_item = {
        "palavra": "Gato",
        "descricao": "Significado do gato",
        "video_url": "https://gato.mp4",
        "source_link": "https://gato.com",
        "fonte": "UFV"
    }
    
    with patch('libras_anki.scrapers.fetch_ufv', return_value=[mock_item]) as mock_ufv:
        res = dicionario.search_word_in_all_sources("Gato", source="UFV")
        mock_ufv.assert_called_once_with("Gato")
        assert len(res) == 1
        assert res[0]["palavra"] == "Gato"
        assert res[0]["fonte"] == "UFV"
        
        # Verifica se gravou no SQLite local
        local_res = db.lookup_sinal("UFV", "gato")
        assert len(local_res) == 1
        assert local_res[0]["descricao"] == "Significado do gato"

def test_clean_tag_part():
    assert dicionario.clean_tag_part("ADJ. / SUBST.") == "ADJ._/_SUBST."
    assert dicionario.clean_tag_part("ALIMENTO, BEBIDA") == "ALIMENTO__BEBIDA"
    assert dicionario.clean_tag_part(None) == ""

def test_db_tags():
    db.insert_or_update_sinal(
        fonte="INES",
        palavra="Cadeira",
        tags="INES, Gramatica::SUBSTANTIVO, Assunto::Casa"
    )
    res = db.lookup_sinal("INES", "Cadeira")
    assert len(res) == 1
    assert res[0]["tags"] == "INES, Gramatica::SUBSTANTIVO, Assunto::Casa"

    # Atualizando as tags
    db.insert_or_update_sinal(
        fonte="INES",
        palavra="Cadeira",
        tags="INES, Gramatica::SUBSTANTIVO, Assunto::Casa, Mao::cg01"
    )
    res = db.lookup_sinal("INES", "Cadeira")
    assert len(res) == 1
    assert res[0]["tags"] == "INES, Gramatica::SUBSTANTIVO, Assunto::Casa, Mao::cg01"

def test_import_ines_to_sqlite():
    mock_classes = 'var classes = [{"id":2,"nome":"ADJETIVO"}];'
    mock_origem = 'var origem = [{"id":1,"nome":"Nacional"}];'
    mock_assuntos = 'var assuntos = [{"id":"3","nome":"ANIMAL/INSETO/PEIXE/AVE"}];'
    mock_mao = 'var mao = [{"id":"10","ordem":"01","url":"cg01.jpg","status":"1"}];'
    mock_palavras = 'var palavras = [{"id":1,"palavra":"A","classe":2,"assunto":3,"origem":1,"mao":10,"video":"a.mp4","image":"a.jpg","descricao":"Primeira letra"}];'

    def side_effect(url, *args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        if "classes.js" in url:
            mock_response.text = mock_classes
        elif "origem.js" in url:
            mock_response.text = mock_origem
        elif "assuntos.js" in url:
            mock_response.text = mock_assuntos
        elif "mao.js" in url:
            mock_response.text = mock_mao
        elif "palavras.js" in url:
            mock_response.text = mock_palavras
        else:
            mock_response.status_code = 404
        return mock_response

    with patch('requests.get', side_effect=side_effect):
        dicionario.import_ines_to_sqlite()

    # Verifica se inseriu o registro com as tags correspondentes no DB mockado
    res = db.lookup_sinal("INES", "A")
    assert len(res) == 1
    assert res[0]["palavra"] == "A"
    assert res[0]["tags"] == "INES, Gramatica::ADJETIVO, Assunto::ANIMAL/INSETO/PEIXE/AVE, Origem::Nacional, Mao::cg01"

def test_lookup_words_by_tags_and_source():
    db.insert_or_update_sinal(fonte="INES", palavra="Gato", tags="INES, Assunto::Animais")
    db.insert_or_update_sinal(fonte="INES", palavra="Cachorro", tags="INES, Assunto::Animais")
    db.insert_or_update_sinal(fonte="RedeSurdos", palavra="Leão", tags="RedeSurdos, Categoria::Animais")
    db.insert_or_update_sinal(fonte="INES", palavra="Rosa", tags="INES, Assunto::Cores")
    
    # 1. Filtro por tag apenas
    res_animais = db.lookup_words_by_tags_and_source(["Animais"])
    assert "Gato" in res_animais
    assert "Cachorro" in res_animais
    assert "Leão" in res_animais
    assert "Rosa" not in res_animais
    
    # 2. Filtro por tag e fonte específica
    res_ines_animais = db.lookup_words_by_tags_and_source(["Animais"], ["INES"])
    assert "Gato" in res_ines_animais
    assert "Cachorro" in res_ines_animais
    assert "Leão" not in res_ines_animais
    
    # 3. Filtro por múltiplas tags
    res_multi = db.lookup_words_by_tags_and_source(["Animais", "Cores"])
    assert "Gato" in res_multi
    assert "Rosa" in res_multi


def test_build_deck_gif(tmp_path):
    # Insere sinal simulado
    db.insert_or_update_sinal(
        fonte="RedeSurdos",
        palavra="Azul",
        descricao="Cor azul",
        video_url="https://youtube.com/watch?v=azul"
    )

    # Mocks do download e do conversor FFmpeg (somente GIF é suportado)
    with patch('libras_anki.dicionario.init_dicionario', return_value=None), \
         patch('libras_anki.dicionario.download_video', return_value=True), \
         patch('libras_anki.dicionario.convert_video_to_gif', return_value=(True, None)), \
         patch('libras_anki.dicionario.get_output_dir', return_value=str(tmp_path)):

        # Cria diretórios e arquivos fake para simular mídia já convertida
        media_dir = tmp_path / "media"
        converted_dir = tmp_path / "media_converted"
        media_dir.mkdir(parents=True, exist_ok=True)
        converted_dir.mkdir(parents=True, exist_ok=True)

        (media_dir / "redesurdos_azul.mp4").touch()
        (converted_dir / "redesurdos_azul.gif").touch()

        apkg_gif = tmp_path / "gif_deck.apkg"
        res_gif = dicionario.build_deck(
            palavras_list=["Azul"],
            source="RedeSurdos",
            deck_name="GIF Deck",
            filename=str(apkg_gif),
        )
        assert res_gif is True
        assert apkg_gif.exists()


def test_fontes_expanded():
    assert "CCB" in dicionario.FONTES
    assert "Economia" in dicionario.FONTES
    assert "FESAI" in dicionario.FONTES
    assert "PIBIC" in dicionario.FONTES


def test_signwriting_lookup_and_svg(tmp_path):
    conn = db.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO signwriting (sign_id, term, norm_word, swu, title) VALUES (?, ?, ?, ?, ?)",
            (10, "abacate", "abacate", "SWU_MOCK_123", "Abacate")
        )
        conn.commit()
    finally:
        conn.close()

    res = db.lookup_signwriting("Abacate")
    assert res is not None
    assert res["swu"] == "SWU_MOCK_123"
    assert res["title"] == "Abacate"

    # Teste de fallback de base_palavra para variante numerada
    res_num = db.lookup_signwriting("Abacate1")
    assert res_num is not None
    assert res_num["swu"] == "SWU_MOCK_123"

    # Teste de palavra inexistente
    assert db.lookup_signwriting("PalavraInexistenteXYZ") is None

    # Teste de download de SVG com mock
    dest_svg = tmp_path / "test_sw.svg"
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'<svg width="100" height="100"><g></g></svg>'
        mock_get.return_value = mock_resp

        ok = dicionario.download_signwriting_svg("SWU_MOCK_123", str(dest_svg))
        assert ok is True
        assert dest_svg.exists()
        assert b"<svg" in dest_svg.read_bytes()

