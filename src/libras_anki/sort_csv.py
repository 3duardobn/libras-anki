import sys
import csv
import unicodedata
import re
from collections import defaultdict
import argparse
from libras_anki.utils import get_output_dir

def normalize_for_sort(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def normalize_base_word(text):
    """Remove trailing (1), (2), etc. and extra spaces to find true base word."""
    base = re.sub(r'\s*\(\d+\)$', '', text).strip()
    return base

def main(args=None):
    parser = argparse.ArgumentParser(description="Ordena as palavras e numera as duplicadas em um arquivo CSV/TSV.")
    parser.add_argument("--arquivo", required=True, help="Caminho para o arquivo CSV ou TSV.")
    parsed_args = parser.parse_args(args)
        
    csv_file = get_output_dir(parsed_args.arquivo)
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            if csv_file.endswith('.tsv'):
                reader = csv.DictReader(f, delimiter='\t')
            else:
                reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
            
        # Agrupar pelo base word normalizado
        grouped = defaultdict(list)
        for row in rows:
            original_word = row.get('Palavra', '')
            base_word = normalize_base_word(original_word)
            norm_key = normalize_for_sort(base_word)
            grouped[norm_key].append((base_word, row))
            
        # Reatribuir as palavras numerando quando houver repetição
        ordered_rows = []
        for norm_key, items in grouped.items():
            if len(items) > 1:
                # Ordenar dentro dos repetidos de alguma forma antes de numerar? Ou manter a ordem original
                for i, (base_word, row) in enumerate(items, start=1):
                    row['Palavra'] = f"{base_word} ({i})"
                    ordered_rows.append(row)
            else:
                base_word, row = items[0]
                # Poderíamos manter o base_word mas, pra ser seguro, usaremos a que veio originalmente caso fosse única
                row['Palavra'] = base_word
                ordered_rows.append(row)
                
        # Ordenar a lista final: primeiro pelo formato normalizado ignorando os numeros, depois pela string original com os numeros (pra ficar 1, 2, 3 certinho)
        ordered_rows.sort(key=lambda x: (
            normalize_for_sort(normalize_base_word(x.get('Palavra', ''))),
            x.get('Palavra', '').lower()
        ))
        
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            if csv_file.endswith('.tsv'):
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            else:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ordered_rows)
            
        print(f"Sucesso! O arquivo '{csv_file}' foi atualizado e as cópias foram numeradas consecutivamente.")
        return True
        
    except Exception as e:
        print(f"Erro ao processar e ordenar o CSV: {e}")
        return False

if __name__ == "__main__":
    main()
