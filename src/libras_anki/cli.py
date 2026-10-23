import os
import sys
import argparse
from libras_anki import db
from libras_anki import dicionario


def escolher_fonte():
    print("\nFontes de dados disponíveis:")
    print("[1] Rede de Surdos (UFC) - RedeSurdos")
    print("[2] Dicionário INES - INES")
    print("[3] Dicionário UFV - UFV")
    print("[4] Libras Acadêmica (UFF) - LibrasAcademicaUFF")
    print("[5] Spread the Sign - SpreadTheSign")
    print("[6] Glossário CCB - CCB")
    print("[7] Glossário de Economia - Economia")
    print("[8] Glossário FESAI (TI) - FESAI")
    print("[9] Projeto PIBIC (Design/Artes) - PIBIC")
    print("[10] Todas as fontes (Busca em todos)")

    while True:
        opcao = input("\nEscolha a fonte: ").strip()
        if opcao == '1': return "RedeSurdos"
        elif opcao == '2': return "INES"
        elif opcao == '3': return "UFV"
        elif opcao == '4': return "LibrasAcademicaUFF"
        elif opcao == '5': return "SpreadTheSign"
        elif opcao == '6': return "CCB"
        elif opcao == '7': return "Economia"
        elif opcao == '8': return "FESAI"
        elif opcao == '9': return "PIBIC"
        elif opcao == '10': return "Ambos"
        print("Opção inválida.")


def menu():
    while True:
        print("\n" + "="*50)
        print("   FERRAMENTAS LIBRAS - GERADOR DE DECK ANKI")
        print("="*50)
        print("1. Inicializar Banco de Dados (SQLite e cache local)")
        print("2. Importar toda a Rede de Surdos UFC (Online)")
        print("3. Buscar Palavra (Teste de Raspagem/SQLite)")
        print("4. Gerar Deck Anki Completo (por fonte)")
        print("5. Gerar Deck Anki Personalizado (CSV ou Lista)")
        print("6. Abrir Interface Gráfica Desktop (PyQt6)")
        print("0. Sair")
        print("="*50)

        escolha = input("\nOpção> ").strip()

        if escolha == '0':
            print("Saindo...")
            break

        elif escolha == '1':
            print("\n--- Inicializando Banco de Dados SQLite ---")
            dicionario.init_dicionario()
            print("Banco de dados SQLite inicializado!")

        elif escolha == '2':
            print("\n--- Importando UFC Completo ---")
            dicionario.scrape_all_ufc_to_db()

        elif escolha == '3':
            print("\n--- Buscar Palavra ---")
            fonte = escolher_fonte()
            palavra = input("Digite a palavra para buscar: ").strip()
            if not palavra:
                print("Palavra é obrigatória.")
                continue
            res = dicionario.search_word_in_all_sources(palavra, source=fonte)
            if res:
                print(f"\nEncontrados {len(res)} registros:")
                for r in res:
                    print("-" * 30)
                    print(f"Palavra: {r['palavra']}")
                    print(f"Fonte: {r['fonte']}")
                    print(f"Link: {r['source_link']}")
                    print(f"Vídeo URL: {r['video_url']}")
                    print(f"Local Vídeo: {r['video_file']}")
                    print(f"Significado: {r['descricao'][:150]}...")
            else:
                print(f"\nNenhum registro encontrado para '{palavra}'.")

        elif escolha == '4':
            print("\n--- Gerar Deck Completo ---")
            fonte = escolher_fonte()
            if fonte == "Ambos":
                print("Por favor, selecione uma fonte específica para gerar o deck completo.")
                continue

            conn = db.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT palavra FROM sinais WHERE fonte = ?", (fonte,))
                rows = cursor.fetchall()
            finally:
                conn.close()

            if not rows:
                print(f"Nenhum registro encontrado localmente para a fonte {fonte}.")
                print("Dica: Inicialize o banco ou faça buscas para popular a base local.")
                continue

            print(f"Encontrados {len(rows)} sinais no banco SQLite local para a fonte {fonte}.")
            confirm = input("Deseja gerar o deck com todas essas palavras? (s/n): ").strip().lower()
            if confirm != 's':
                continue

            palavras = [r['palavra'] for r in rows]
            deck_name = f"Libras - {fonte}"
            filename = f"libras_{fonte.lower()}.apkg"
            dicionario.build_deck(palavras, source=fonte, deck_name=deck_name, filename=filename)

        elif escolha == '5':
            print("\n--- Gerar Deck Personalizado ---")
            fonte = escolher_fonte()

            print("\nComo deseja fornecer as palavras?")
            print("[1] Digitar lista de palavras (separadas por vírgula)")
            print("[2] Ler a partir de um arquivo CSV")

            tipo_input = input("Escolha: ").strip()
            palavras = []

            if tipo_input == '1':
                lista = input("Digite as palavras (ex: abacaxi, cores, animais): ").strip()
                if not lista:
                    print("Lista vazia. Cancelando.")
                    continue
                palavras = [p.strip() for p in lista.split(',') if p.strip()]
            elif tipo_input == '2':
                csv_path = input("Caminho para o arquivo CSV de palavras: ").strip()
                if not csv_path or not os.path.exists(csv_path):
                    print("Arquivo não encontrado. Cancelando.")
                    continue
                palavras = db.read_custom_words_csv(csv_path)
            else:
                print("Opção inválida.")
                continue

            if not palavras:
                print("Nenhuma palavra selecionada. Cancelando.")
                continue

            deck_name = input("Nome do Deck Anki (ex: 'Meus Sinais'): ").strip()
            if not deck_name:
                deck_name = "Meus Sinais"

            filename = input("Nome do arquivo de saída (ex: 'meus_sinais.apkg'): ").strip()
            if not filename:
                filename = "meus_sinais.apkg"
            if not filename.endswith('.apkg'):
                filename += '.apkg'

            dicionario.build_deck(palavras, source=fonte, deck_name=deck_name, filename=filename)

        elif escolha == '6':
            from libras_anki.gui.app import main as gui_main
            gui_main()
            break

        else:
            print("Opção inválida! Tente novamente.")


def main():
    if len(sys.argv) == 1:
        try:
            menu()
        except KeyboardInterrupt:
            print("\nCancelado pelo usuário. Saindo...")
            sys.exit(0)
    else:
        parser = argparse.ArgumentParser(
            description="Ferramentas Libras - Gerador de Deck Anki (LLM & Humano)"
        )
        parser.add_argument("--gui", action="store_true", help="Abre a interface gráfica desktop (PyQt6).")
        parser.add_argument("--init-db", action="store_true", help="Inicializa o banco de dados e importa bases unificadas (sinais + SignWriting).")
        parser.add_argument("--force-reimport", action="store_true", help="Força a reimportação das bases de dados em data/.")
        parser.add_argument("--import-ufc-online", action="store_true", help="Importa UFC completo do site online.")
        parser.add_argument("--words", type=str, help="Lista de palavras separadas por vírgula.")
        parser.add_argument("--words-file", type=str, help="Caminho para arquivo CSV/TXT de palavras.")
        parser.add_argument("--tags", type=str, help="Filtra palavras por tags/categorias no banco (ex: 'Cores', 'Gramatica::ADJETIVO').")
        parser.add_argument("--sources", type=str, default="Ambos", help="Fontes (RedeSurdos, INES, UFV, LibrasAcademicaUFF, SpreadTheSign, CCB, Economia, FESAI, PIBIC, Ambos).")
        parser.add_argument("--deck-name", type=str, default="Dicionário Libras", help="Nome do deck Anki.")
        parser.add_argument("--output", type=str, default="dicionario_libras.apkg", help="Arquivo de saída .apkg.")
        parser.add_argument("--sql", type=str, help="Executa uma instrução SQL no banco SQLite.")

        args = parser.parse_args()

        if args.gui:
            from libras_anki.gui.app import main as gui_main
            gui_main()
            sys.exit(0)

        if args.sql:
            print("[LLM-Mode] Executando instrução SQL no banco...")
            conn = db.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(args.sql)
                if args.sql.strip().lower().startswith("select"):
                    rows = cursor.fetchall()
                    print(f"[LLM-Mode] Retornados {len(rows)} registros:")
                    for r in rows:
                        print(dict(r))
                else:
                    conn.commit()
                    print(f"[LLM-Mode] Sucesso! Linhas modificadas: {cursor.rowcount}")
            except Exception as e:
                print(f"[LLM-Mode] Erro ao executar SQL: {e}")
                sys.exit(1)
            finally:
                conn.close()
            sys.exit(0)

        if args.init_db or args.force_reimport:
            print("[LLM-Mode] Inicializando banco de dados...")
            db.init_db(force_reimport=args.force_reimport)
            dicionario.init_dicionario()
            print("[LLM-Mode] Banco de dados inicializado com sucesso.")
            sys.exit(0)

        if args.import_ufc_online:
            print("[LLM-Mode] Importando posts online da UFC...")
            dicionario.scrape_all_ufc_to_db()
            print("[LLM-Mode] Importação UFC concluída.")
            sys.exit(0)

        palavras = []
        if args.words:
            palavras = [p.strip() for p in args.words.split(',') if p.strip()]
        elif args.words_file:
            palavras = db.read_custom_words_csv(args.words_file)
        elif args.tags:
            tags_list = [t.strip() for t in args.tags.split(',') if t.strip()]
            sources_list = [s.strip() for s in args.sources.split(',') if s.strip()]
            dicionario.init_dicionario()
            palavras = db.lookup_words_by_tags_and_source(tags_list, sources_list)
            print(f"[LLM-Mode] Encontradas {len(palavras)} palavras associadas às tags: {tags_list}")

        if not palavras:
            print("[LLM-Mode] Erro: Nenhuma palavra selecionada ou encontrada com os filtros fornecidos.")
            sys.exit(1)

        print(f"[LLM-Mode] Iniciando geração do deck para {len(palavras)} palavras...")
        success = dicionario.build_deck(
            palavras_list=palavras,
            source=args.sources,
            deck_name=args.deck_name,
            filename=args.output,
        )
        if success:
            print("[LLM-Mode] Deck gerado com sucesso!")
            sys.exit(0)
        else:
            print("[LLM-Mode] Erro na geração do deck.")
            sys.exit(1)


if __name__ == "__main__":
    main()
