import sys
import os
import subprocess
import concurrent.futures
import argparse
from libras_anki.utils import get_output_dir

try:
    import ffmpeg
except ImportError:
    print("ERRO: Pacote 'ffmpeg-python' não encontrado. Execute 'pip install ffmpeg-python'")
    sys.exit(1)

GIF_FPS = 15       # 15fps: fluido para Libras, mantém tamanho gerenciável
RESOLUTION = 480   # Altura em pixels (480p)
MAX_WORKERS = 3


def convert_video_to_gif(in_path, out_path):
    try:
        cmd = [
            'ffmpeg', '-y', '-i', in_path,
            '-vf', f'fps={GIF_FPS},scale=-2:{RESOLUTION}:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
            out_path
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def get_video_resolution(path):
    try:
        probe = ffmpeg.probe(path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if video_stream:
            return int(video_stream['height'])
    except Exception:
        pass
    return None


def main(args=None):
    parser = argparse.ArgumentParser(description="Converte vídeos para GIF animado.")
    parser.add_argument("--pasta", required=True, help="A pasta base do projeto.")
    parsed_args = parser.parse_args(args)

    base_dir = get_output_dir(parsed_args.pasta)
    in_dir = os.path.join(base_dir, "media")
    out_dir = os.path.join(base_dir, "media_converted")

    if not os.path.exists(in_dir):
        print(f"Erro: pasta de entrada '{in_dir}' não existe.")
        return False

    os.makedirs(out_dir, exist_ok=True)

    extensions = (".mp4", ".mkv", ".webm", ".avi", ".mov")
    videos_to_convert = [f for f in os.listdir(in_dir) if f.lower().endswith(extensions)]

    if not videos_to_convert:
        print(f"Nenhum vídeo encontrado em '{in_dir}'.")
        return True

    print(f"Encontrados {len(videos_to_convert)} vídeos.")
    print(f"Configuração: GIF | {GIF_FPS}fps | {RESOLUTION}p\n")

    for f in videos_to_convert:
        h = get_video_resolution(os.path.join(in_dir, f))
        if h and h < RESOLUTION:
            print(f"  [AVISO] {f} é {h}p — menor que o alvo {RESOLUTION}p (upscale inútil)")

    def process_func(filename):
        import unicodedata
        in_path = os.path.join(in_dir, filename)

        nome_bruto = os.path.splitext(filename)[0]
        nfkd = unicodedata.normalize('NFKD', nome_bruto)
        sem_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
        nome_limpo = "".join([c for c in sem_acentos if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_').lower()

        out_name = nome_limpo + ".gif"
        out_path = os.path.join(out_dir, out_name)

        if os.path.exists(out_path):
            print(f"  [SKIP] Já convertido: {filename}")
            return True, filename

        print(f"  [→] Convertendo: {filename}")
        success, erro = convert_video_to_gif(in_path, out_path)

        if not success:
            print(f"  [ERRO] {filename}:\n{erro}")
        else:
            orig_mb = os.path.getsize(in_path) / 1_048_576
            conv_mb = os.path.getsize(out_path) / 1_048_576
            print(f"  [✓] {filename} | {orig_mb:.2f}MB → {conv_mb:.2f}MB")

        return success, filename

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(process_func, videos_to_convert))

    sucessos = sum(1 for r in results if r[0])
    falhas = len(results) - sucessos
    print(f"\nConcluído: {sucessos}/{len(videos_to_convert)} convertidos.", end="")
    if falhas:
        print(f" {falhas} falha(s).")
        return False
    print(" Sem erros.")
    return True


if __name__ == "__main__":
    main()
