import os
import hashlib
import argparse
import sys
import csv
from mutagen import File
from tqdm import tqdm


class Colors:
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    BOLD = '\033[1m'
    GRAY = '\033[90m'
    END = '\033[0m'


def get_args():
    parser = argparse.ArgumentParser(
        description=f"{Colors.CYAN}Поиск дубликатов с расчетом объема и экспортом в CSV.{Colors.END}",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-dir", "--directory", help="Директория для поиска")
    return parser.parse_args()


def get_file_hash(path):
    hasher = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None


def get_audio_info(path):
    try:
        size_bytes = os.path.getsize(path)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        audio = File(path)
        bitrate = "N/A"
        if audio and audio.info and hasattr(audio.info, 'bitrate'):
            bitrate = f"{int(audio.info.bitrate / 1000)} kbps"
        return size_bytes, f"{size_mb} MB", bitrate
    except:
        return 0, "N/A", "N/A"


def find_duplicates(root_path):
    root_path = os.path.abspath(root_path)
    if not os.path.isdir(root_path):
        print(f"{Colors.RED}[x] Ошибка: Путь не найден.{Colors.END}");
        return

    all_audio_files = []
    extensions = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.ape', '.dsf', '.dff')

    print(f"{Colors.CYAN}Анализ папок...{Colors.END}")
    for root, _, files in os.walk(root_path):
        for file in files:
            if file.lower().endswith(extensions):
                all_audio_files.append(os.path.join(root, file))

    if not all_audio_files:
        print(f"{Colors.YELLOW}Файлы не найдены.{Colors.END}");
        return

    files_by_hash = {}
    print(f"{Colors.CYAN}Поиск дубликатов:{Colors.END}") #sha256
    for full_path in tqdm(all_audio_files, desc="Прогресс", unit="файл", colour="green"):
        f_hash = get_file_hash(full_path)
        if f_hash:
            files_by_hash.setdefault(f_hash, []).append(full_path)

    duplicates = [paths for paths in files_by_hash.values() if len(paths) > 1]
    if not duplicates:
        print(f"\n{Colors.GREEN}Дубликатов нет!{Colors.END}");
        return

    total_wasted_size = 0
    csv_data = []

    print(f"\n{Colors.BOLD}{Colors.YELLOW}РЕЗУЛЬТАТЫ:{Colors.END}")
    print("=" * 60)

    for paths in duplicates:
        filename = os.path.basename(paths[0])
        print(f"{Colors.BOLD}Файл: {Colors.CYAN}{filename}{Colors.END}")

        # Инфо о первом файле (оригинал для расчета)
        orig_size_bytes, _, _ = get_audio_info(paths[0])

        for i, p in enumerate(paths):
            size_bytes, size_str, bitrate = get_audio_info(p)
            folder = os.path.dirname(p)

            # Если это не первый файл в группе, считаем его "мусором"
            if i > 0: total_wasted_size += size_bytes

            print(f"  {folder} {Colors.GRAY}{size_str} | {bitrate}{Colors.END}")

            csv_data.append([filename, folder, size_str, bitrate])
        print(f"{Colors.GRAY}" + "-" * 40 + f"{Colors.END}")

    # Итоги
    wasted_mb = round(total_wasted_size / (1024 * 1024), 2)
    print(f"\n{Colors.BOLD}{Colors.YELLOW}Можно освободить: {wasted_mb} MB {Colors.END}")

    # Сохранение в CSV
    csv_file = "duplicates_report.csv"
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Название', 'Папка', 'Размер', 'Битрейт'])
            writer.writerows(csv_data)
        print(f"{Colors.CYAN}Отчет сохранен в: {os.path.abspath(csv_file)}{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}[x] Ошибка записи CSV: {e}{Colors.END}")


if __name__ == "__main__":
    args = get_args()
    target = args.directory or input(f"{Colors.YELLOW}Путь: {Colors.END}").strip()
    if target: find_duplicates(target)
