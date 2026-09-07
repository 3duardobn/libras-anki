# Libras Anki Generator

Gerador de decks do [Anki](https://apps.ankiweb.net/) para estudo de **Libras**
(Língua Brasileira de Sinais). Busca sinais em dicionários online, converte os
vídeos para **GIF animado** e empacota tudo num arquivo `.apkg` pronto para importar.

> Licença: **GPLv3 or later** — ver [LICENSE](LICENSE).

## Como funciona

1. **Busca** — o programa consulta o banco SQLite local e, se preciso, os sites
   das fontes (RedeSurdos/UFC, INES, UFV, UFF, SpreadTheSign).
2. **Download** — baixa os vídeos originais para `output/media/`.
3. **Conversão** — converte cada vídeo em GIF animado (`output/media_converted/`)
   via `ffmpeg`. GIFs já convertidos são reaproveitados (cache).
4. **Deck** — agrupa variantes da mesma palavra (ex: PRETO1 + PRETO2) num único
   card com os GIFs lado a lado e gera o `.apkg`.

## Requisitos

- Python >= 3.8
- [FFmpeg](https://ffmpeg.org/) instalado no sistema e no `PATH`
- VPN (opcional, mas recomendada — o YouTube costuma bloquear downloads da RedeSurdos sem ela)

## Instalação

```bash
python -m venv venv-rede-surdos
source venv-rede-surdos/bin/activate
pip install -e .
```

Na primeira vez (ou após atualizar o código), inicialize o banco:

```bash
./venv-rede-surdos/bin/libras-anki --init-db
```

## Uso

Sem argumentos abre o **menu interativo**. Com qualquer argumento entra em
**modo não-interativo** (próprio para automação/agentes):

```bash
# Deck de cores
./venv-rede-surdos/bin/libras-anki \
  --words "amarelo, azul, branco, preto, verde, vermelho" \
  --sources "Ambos" \
  --deck-name "Cores - Libras" \
  --output "cores.apkg"

# Deck por categoria da RedeSurdos
./venv-rede-surdos/bin/libras-anki \
  --tags "Categoria::Animais" --sources "RedeSurdos" \
  --deck-name "Animais - UFC" --output "animais_ufc.apkg"

# Consultar o banco direto
./venv-rede-surdos/bin/libras-anki --sql "SELECT fonte, COUNT(*) FROM sinais GROUP BY fonte"
```

Ver [AGENTS.md](AGENTS.md) para a referência completa da CLI, exemplos,
esquema do banco e solução de problemas.

## Fontes de dados

| Fonte | Conteúdo |
| :--- | :--- |
| INES | ~5800 palavras (dicionario.ines.gov.br) |
| RedeSurdos (UFC) | Sinais em vídeo via YouTube (redesurdosce.ufc.br) |
| UFV | Dicionário da UFV |
| LibrasAcademicaUFF | Libras Acadêmica da UFF |
| SpreadTheSign | spreadthesign.com |

## Estrutura do projeto

```
src/libras_anki/   # código-fonte (cli, dicionario, db, scrapers, convert_videos, utils)
tests/             # pytest
output/            # GERADO e ignorado pelo git: banco, mídias e .apkg
AGENTS.md          # guia completo para agentes/LLMs e referência da CLI
```

## Testes

```bash
./venv-rede-surdos/bin/python -m pytest tests/ -q
```

## Licença

Este programa é software livre: você pode redistribuí-lo e/ou modificá-lo sob
os termos da **GNU General Public License v3 (ou posterior)**, publicada pela
Free Software Foundation. Ver [LICENSE](LICENSE) para o texto completo.
