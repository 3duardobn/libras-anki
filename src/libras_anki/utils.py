import os

def get_output_dir(pasta_name):
    """
    Retorna o caminho absoluto do diretório de saída correspondente.
    Se o caminho for relativo (ex: 'animais'), resolve-o sob a pasta raiz 'output/'.
    Se já for absoluto ou começar com 'output', preserva o caminho original.
    """
    if not pasta_name:
        return os.path.abspath("output")
    if os.path.isabs(pasta_name):
        return pasta_name
    
    norm = os.path.normpath(pasta_name)
    parts = norm.split(os.sep)
    if parts[0] == "output":
        return os.path.abspath(norm)
        
    return os.path.abspath(os.path.join("output", norm))
