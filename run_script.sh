#!/usr/bin/env bash
# ==============================================================================
# run_script.sh — Script de inicialização do Libras Anki (GUI & CLI)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv-rede-surdos"

# 1. Verificar e configurar ambiente virtual se necessário
if [ ! -d "$VENV_DIR" ]; then
    echo "⚙️  Ambiente virtual não encontrado. Criando '$VENV_DIR'..."
    if command -v uv >/dev/null 2>&1; then
        uv venv "$VENV_DIR"
        uv pip install -e ".[test]" --python "$VENV_DIR/bin/python"
    else
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install --upgrade pip
        "$VENV_DIR/bin/pip" install -e ".[test]"
    fi
    echo "✅ Ambiente virtual configurado com sucesso!"
fi

# Ativar virtualenv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 2. Inicializar banco de dados SQLite local se ainda não existir
DB_PATH="$SCRIPT_DIR/output/libras.db"
if [ ! -f "$DB_PATH" ]; then
    echo "📦 Inicializando banco local e importando bases unificadas (26.928 sinais + SignWriting)..."
    python -m libras_anki.cli --init-db
fi

# 3. Execução
if [ $# -eq 0 ]; then
    echo "🚀 Iniciando Libras Anki Studio (Interface Gráfica PyQt6)..."
    exec python -m libras_anki.gui.app
else
    # Repassar argumentos para a CLI (ex: --words, --tags, --help, --sql)
    exec python -m libras_anki.cli "$@"
fi
