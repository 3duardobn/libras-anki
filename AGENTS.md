# AGENTS.md — libras_anki

> Único arquivo de contexto para agentes (consolida o antigo `agents.md` + `CLAUDE.md`).
> Se você é um agente, leia este arquivo antes de mexer no código.

Gerador de decks Anki para estudo de Libras (Língua Brasileira de Sinais).
Baixa vídeos de dicionários online, converte para **GIF animado** e empacota em `.apkg`.

Licença: **GPLv3 or later** (ver `LICENSE`).

## Estrutura

```
src/libras_anki/
  cli.py            # Entrypoint CLI (modo interativo e LLM-mode)
  dicionario.py     # Lógica principal: busca, download, conversão, build_deck()
  db.py             # SQLite: schema, CRUD, normalização, base_palavra, signwriting
  scrapers.py       # Scrapers por fonte (RedeSurdos, UFV, UFF, SpreadTheSign, CCB, Economia, FESAI, PIBIC)
  convert_videos.py # Conversão ffmpeg → GIF (única mídia suportada)
  utils.py          # get_output_dir()
  sort_csv.py       # LEGADO: utilitário standalone, não usado pelo pipeline
data/               # BASES LOCAIS: libras.db (26.928 sinais) e signpuddle.db (39.760 termos SWU)
tests/
  test_dicionario.py
  test_utils.py
output/             # GERADO, não versionado: libras.db, media/, media_converted/, *.apkg
```

## Executar

```bash
source venv-rede-surdos/bin/activate
./venv-rede-surdos/bin/libras-anki [opções]
```

Sem argumentos → modo interativo. Com qualquer argumento → **LLM-mode** (não-interativo).

## Parâmetros da CLI

| Argumento | Tipo | Descrição |
| :--- | :--- | :--- |
| `--init-db` | Flag | Inicializa o banco SQLite, aplica migrações e importa bases de `data/` (`libras.db` e `signpuddle.db`). **Sempre rodar antes do primeiro uso ou após atualizar o código.** |
| `--force-reimport` | Flag | Força a reimportação das bases de dados locais em `data/`. |
| `--import-ufc-online` | Flag | Varre a API online da Rede de Surdos UFC e importa todas as postagens. |
| `--words` | String | Lista de palavras separadas por vírgula. Busca por palavra-base (ignora variantes numeradas: "preto" acha PRETO1 e PRETO2). |
| `--words-file` | String | Caminho para arquivo CSV/TXT com lista de palavras. |
| `--tags` | String | Filtra por correspondência parcial de tags no banco (ex: `Cores`, `Gramatica::ADJETIVO`, `COR/FORMA`). Aceita múltiplas separadas por vírgula. |
| `--sources` | String | Fontes: `RedeSurdos`, `INES`, `UFV`, `LibrasAcademicaUFF`, `SpreadTheSign`, `CCB`, `Economia`, `FESAI`, `PIBIC`, `Ambos` (padrão: `Ambos`). |
| `--deck-name` | String | Nome interno do deck Anki. |
| `--output` | String | Nome do arquivo `.apkg` gerado (relativo à pasta `output/`). |
| `--sql` | String | Executa SQL direto no banco (SELECT, UPDATE, INSERT, etc.). |

**Formato de saída:** sempre GIF animado com enriquecimento automático de **SignWriting (SWU)** quando disponível.

## Fontes de dados

| Fonte | Tipo de mídia | Observações |
| :--- | :--- | :--- |
| INES | MP4 direto | ~11.500 palavras; algumas URLs 404 no servidor deles |
| RedeSurdos (UFC) | YouTube | ~5.200 palavras; requer VPN para download estável |
| SpreadTheSign | MP4 direto | ~4.200 palavras; vídeos de alta qualidade |
| LibrasAcademicaUFF | MP4/YouTube | ~2.700 palavras |
| UFV | MP4 direto | ~2.000 palavras |
| CCB | YouTube | 836 palavras; glossário de sinais religiosos |
| PIBIC | YouTube | 135 palavras; artes, design, animação e fotografia |
| FESAI | MP4 direto | 113 palavras; tecnologia e TI |
| Economia | YouTube | 40 palavras; economia e finanças |
| **SignPuddle** | SVG vetorial | 39.760 termos mapeados para escrita SignWriting (SWU) |

## Banco SQLite — pontos críticos

**Coluna `base_palavra`:** palavra normalizada sem dígitos finais. É a chave de agrupamento de variantes.

- `PRETO1` + `PRETO2` → `base_palavra = 'preto'` → **mesmo card, dois GIFs**
- Sempre rodar `--init-db` após pull/mudança de código para aplicar migrações

**IDs do Anki:** `deck_id` e `model_id` gerados via `hashlib.md5` — determinísticos por nome.
Nunca usar `hash()` do Python (aleatorizado por processo). O fallback de nome de
mídia em `get_safe_media_filename` também usa `hashlib.md5` pelo mesmo motivo.

**Cache de GIF:** se `output/media_converted/<nome>.gif` existe, download e conversão
são pulados. Limpar `video_file` no banco força re-conversão.

### Esquema da tabela `sinais`

| Coluna | Descrição |
| :--- | :--- |
| `id` | PK autoincrement |
| `fonte` | `INES`, `RedeSurdos`, `UFV`, `LibrasAcademicaUFF`, `SpreadTheSign` |
| `palavra` | Nome original (ex: `PRETO1`, `Preto`) |
| `normalized_palavra` | Sem acento, minúsculo (ex: `preto1`) |
| `base_palavra` | Sem acento, minúsculo, sem dígitos finais (ex: `preto`) — chave de agrupamento |
| `descricao` | Significado/definição |
| `libras` | Glosas Libras (só INES) |
| `exemplo` | Frase de exemplo |
| `video_url` | URL fonte do vídeo original |
| `video_file` | Caminho relativo do GIF convertido em `output/media_converted/` |
| `image_url` | URL de imagem (INES) |
| `source_link` | Link da página de origem |
| `tags` | Tags separadas por vírgula (hierarquia com `::`) |

### Esquema da tabela `signwriting`

| Coluna | Descrição |
| :--- | :--- |
| `id` | PK autoincrement |
| `sign_id` | ID de origem no SignPuddle |
| `term` | Termo em texto original |
| `norm_word` | Termo normalizado (sem acentos, minúsculo) — indexado |
| `swu` | Caracteres de escrita SWU (SignWriting in Unicode) |
| `title` | Título do sinal |

### Exploração via `--sql`

```bash
./venv-rede-surdos/bin/libras-anki --sql "PRAGMA table_info(sinais)"
./venv-rede-surdos/bin/libras-anki --sql "SELECT fonte, COUNT(*) FROM sinais GROUP BY fonte"
./venv-rede-surdos/bin/libras-anki --sql "SELECT base_palavra, GROUP_CONCAT(palavra, ' / ') FROM sinais WHERE tags LIKE '%COR%' GROUP BY base_palavra ORDER BY base_palavra"
./venv-rede-surdos/bin/libras-anki --sql "SELECT COUNT(*) FROM sinais WHERE base_palavra IS NULL OR base_palavra = ''"
./venv-rede-surdos/bin/libras-anki --sql "UPDATE sinais SET video_url = 'URL_CORRETA', video_file = '' WHERE palavra = 'PALAVRA' AND fonte = 'INES'"
./venv-rede-surdos/bin/libras-anki --sql "UPDATE sinais SET tags = tags || ', MinhaTag' WHERE palavra = 'VERDE' AND fonte = 'INES'"
```

## Tags por fonte

- **INES**: `Gramatica::<CLASSE>`, `Assunto::<TEMA>`, `Origem::<PAIS>`, `Mao::<CONFIG>`
  - Ex: `INES, Gramatica::ADJETIVO, Assunto::COR/FORMA, Origem::Nacional, Mao::cg12`
  - **Atenção:** `Assunto::COR/FORMA` inclui cores E formas geométricas. Para deck só de cores, use `--words` com lista explícita.
- **RedeSurdos**: `RedeSurdos, Categoria::<PASTA>` (ex: `Categoria::Cores`, `Categoria::Animais`)
- **Outras fontes**: marcadas só com o nome da fonte.

## Comportamento de variantes numeradas (INES)

O INES usa sufixos numéricos para sinais diferentes da mesma palavra (ex: PRETO1, PRETO2).
O sistema agrupa automaticamente todas as variantes em **um único card** com múltiplos
GIFs lado a lado. Labels no card mostram a variante (PRETO1, PRETO2).

- Busca por `preto` → encontra PRETO1 + PRETO2 + Preto (RedeSurdos) → 1 card
- **Implicação para `--words`:** sempre use a forma-base sem número (`preto`, não `preto1`).

## Cache e re-uso de mídia

- Vídeos fonte ficam em `output/media/`
- GIFs convertidos ficam em `output/media_converted/`
- Se o GIF já existe, download e conversão são pulados automaticamente
- Gerar o mesmo deck duas vezes é rápido — só o `.apkg` é recriado

## IDs determinísticos

`deck_id` e `model_id` via `hashlib.md5` do nome — reimportar o deck atualiza as notas
existentes no Anki em vez de criar duplicatas.

## Exemplos práticos

```bash
# Deck de cores (só cores — NÃO usar --tags "COR/FORMA", que inclui formas geométricas)
./venv-rede-surdos/bin/libras-anki \
  --words "alaranjado, amarelo, azul, bege, branco, cinza, colorido, cor, dourado, laranja, lilas, louro, marrom, negro, preto, rosa, roxo, ruivo, verde, vermelho, vermelhao, violeta" \
  --sources "Ambos" \
  --deck-name "Cores - Libras" \
  --output "cores_gif.apkg"

# Deck de matérias e materiais escolares
./venv-rede-surdos/bin/libras-anki \
  --words "química, física, biologia, matemática, história, geografia, português, filosofia, gramática, dicionário, borracha, lápis, caderno, caneta, mochila, livro, apontador, estojo, papel, tinta, calculadora, computador, giz, apagador, escola, professor, aula, prova, nota, lousa, quadro, régua, tesoura, inglês, artes, aluno, cola" \
  --sources "Ambos" \
  --deck-name "Escola - Matérias e Materiais" \
  --output "escola.apkg"

# Deck por categoria RedeSurdos
./venv-rede-surdos/bin/libras-anki --tags "Categoria::Animais" --sources "RedeSurdos" --deck-name "Animais - UFC" --output "animais_ufc.apkg"

# Deck INES por assunto
./venv-rede-surdos/bin/libras-anki --tags "Assunto::ALIMENTO" --sources "INES" --deck-name "Alimentos - INES" --output "alimentos_ines.apkg"

# Inicializar/migrar banco (obrigatório após instalação ou update de código)
./venv-rede-surdos/bin/libras-anki --init-db
```

### Corrigir URL de vídeo 404 do INES

```bash
curl -s -o /dev/null -w "%{http_code}" "https://dicionario.ines.gov.br/public/media/palavras/videos/palavra1Sm_Prog001.mp4"
./venv-rede-surdos/bin/libras-anki --sql "UPDATE sinais SET video_url = 'URL_CORRETA', video_file = '' WHERE palavra = 'PALAVRA1' AND fonte = 'INES'"
```

## Decisões de design

- **Somente GIF** — MP4/WebM removidos. GIF é `<img>` no Anki: sem codec, sem `preload`, sem freeze.
- **Agrupamento por `base_palavra`** — variantes INES num card único, GIFs lado a lado com labels.
- **Para "só cores"** — usar `--words` com lista explícita, não `--tags "COR/FORMA"`.
- **URL BRANCO1 corrigida** — `brancoSm_Prog001.mp4` → `branco1Sm_Prog001.mp4` no banco.
- **LILÁS** — sem vídeo no servidor INES; card não gerado.

## Problemas conhecidos

| Problema | Causa | Solução |
| :--- | :--- | :--- |
| Vídeos RedeSurdos falham | YouTube bloqueia sem VPN | Ativar VPN antes de gerar |
| Algumas URLs INES 404 | Nomes incorretos no servidor INES | Testar variantes (`palavra1Sm_`, `palavraSm_`) e corrigir via `--sql` |
| LILÁS sem vídeo | Entrada incompleta no INES | Sem solução disponível |
| Card sem GIF não aparece | `valid_videos` vazio → card pulado | Normal — só cards com mídia são incluídos |

## Código legado / candidatos a remoção (não quebrar o pipeline)

- `src/libras_anki/sort_csv.py` — utilitário standalone de ordenação de CSV; **não importado por ninguém**, não ligado à CLI. Remover o arquivo é seguro se ninguém usa fora do repo.
- `convert_videos.py::main()` + `get_video_resolution()` — CLI batch standalone (`--pasta`); o pipeline só usa `convert_video_to_gif()`. Se `main()` for removido, a dependência `ffmpeg-python` (usada só pelo `probe`) pode sair do `pyproject.toml`.
- `db.import_existing_ufc_data()` — importa o layout antigo (pastas por categoria com `video_links.csv`/`word_links.csv`); hoje é no-op na maioria dos ambientes. Manter até confirmar que ninguém depende da migração legada.
- Já removidos nesta organização: import não usado `BeautifulSoup` (`scrapers.py` usa só regex), deps `beautifulsoup4` e `markdownify` (nenhum import no código), fallback `hash()` não-determinístico (trocado por `hashlib.md5`).

## Dependências

```toml
requests, yt-dlp, ffmpeg-python, genanki
```

`ffmpeg` precisa estar instalado no sistema (usado via subprocess para gerar os GIFs).

## Testes

```bash
./venv-rede-surdos/bin/python -m pytest tests/ -q
```
