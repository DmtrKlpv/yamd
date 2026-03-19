import os
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sys
import re


class Colors:
    GREEN, RED, YELLOW, CYAN, BOLD, END = '\033[92m', '\033[91m', '\033[93m', '\033[96m', '\033[1m', '\033[0m'


def get_args():
    parser = argparse.ArgumentParser(
        description=f"{Colors.CYAN}Утилита для создания плейлистов.{Colors.END}",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("path", nargs="?", help="Путь к музыке (откуда брать папки)")
    parser.add_argument(
        "-f", "--format",
        choices=["m3u", "m3u8", "pls", "xspf", "wpl"],
        help="Формат плейлиста:\n"
             "m3u   - Классический плейлист (ANSI)\n"
             "m3u8  - Плейлист UTF-8 (для Foobar2000)\n"
             "pls   - Плейлист Winamp/другие\n"
             "xspf  - XML формат (для VLC)\n"
             "wpl   - Windows Media Player"
    )
    parser.add_argument("-savedir", help="Папка для сохранения плейлистов")
    parser.add_argument("-list", "--from-list", help="Создать плейлист из текстового файла")
    parser.add_argument("-mass", help="Путь к папке с TXT-файлами для массового создания плейлистов")
    parser.add_argument("-searchdir", help="Папка для поиска треков (используется с -list или -mass)")
    parser.add_argument("-abs", "--absolute", action="store_true", help="Использовать абсолютные пути в плейлисте")
    return parser.parse_args()


def normalize_name(name):
    """Очистка имени: убирает расширение, пунктуацию и лишние пробелы"""
    name = os.path.splitext(name)[0]
    # Заменяем все не-буквы и не-цифры на пробелы
    name = re.sub(r'[^\w\s]', ' ', name)
    return " ".join(name.lower().split())


def choose_format():
    formats = {"1": "m3u", "2": "m3u8", "3": "pls", "4": "xspf", "5": "wpl"}
    print(f"{Colors.BOLD}Выберите формат:{Colors.END}\n"
          f"1. M3U\n2. M3U8\n3. PLS\n4. XSPF\n5. WPL")
    return formats.get(input(f"{Colors.YELLOW}Введите номер: {Colors.END}").strip(), "m3u8")


def save_playlist(path, tracks, ext, name):
    if not tracks: return
    try:
        if ext in ['m3u', 'm3u8']:
            enc = 'utf-8' if ext == 'm3u8' else 'cp1251'
            with open(path, 'w', encoding=enc, errors='replace') as f:
                f.write("#EXTM3U\n" + "\n".join(tracks) + "\n")
        elif ext == 'pls':
            with open(path, 'w', encoding='utf-8') as f:
                f.write("[playlist]\n")
                for i, t in enumerate(tracks, 1):
                    f.write(f"File{i}={t}\nTitle{i}={os.path.basename(t)}\n")
                f.write(f"NumberOfEntries={len(tracks)}\nVersion=2\n")
        elif ext in ['xspf', 'wpl']:
            ns = "http://xspf.org" if ext == 'xspf' else ""
            root_el = ET.Element("playlist", version="1", xmlns=ns) if ext == 'xspf' else ET.Element("smil")
            if ext == 'xspf':
                ET.SubElement(root_el, "title").text = name
                tl = ET.SubElement(root_el, "trackList")
                for t in tracks: ET.SubElement(ET.SubElement(tl, "track"), "location").text = t
            else:
                h = ET.SubElement(root_el, "head")
                ET.SubElement(h, "title").text = name
                seq = ET.SubElement(ET.SubElement(root_el, "body"), "seq")
                for t in tracks: ET.SubElement(seq, "media", src=t)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(minidom.parseString(ET.tostring(root_el)).toprettyxml(indent="  "))
        print(f"{Colors.GREEN}[+] {Colors.END}Создан: {os.path.basename(path)} ({len(tracks)})")
    except Exception as e:
        print(f"{Colors.RED}[x] Ошибка записи: {e}{Colors.END}")


def find_match(query, db):
    """Улучшенный поиск: точное совпадение -> вхождение -> пословный поиск"""
    q_n = normalize_name(query)

    # 1. Попытка прямого вхождения (как было раньше)
    for n, p in db:
        if q_n == n or q_n in n or n in q_n:
            return p

    # 2. Пословный поиск (Keywords Match)
    # Разбиваем запрос на значимые слова (длиннее 1 символа)
    words = [w for w in q_n.split() if len(w) > 1]
    if not words: return None

    for n, p in db:
        # Проверяем, что ВСЕ слова из запроса есть в названии файла
        if all(word in n for word in words):
            return p

    return None


def process_list(list_file, db, ext, save_dir, absolute):
    if not os.path.exists(list_file):
        print(f"{Colors.RED}[x] Файл не найден: {list_file}{Colors.END}")
        return

    with open(list_file, 'r', encoding='utf-8') as f:
        queries = [l.strip() for l in f if l.strip()]

    found = []
    for q in queries:
        match = find_match(q, db)
        if match:
            found.append(match)
        else:
            print(f"{Colors.YELLOW}    —{Colors.END} Не найден: {q}")

    pl_base = os.path.splitext(os.path.basename(list_file))[0]
    save_playlist(os.path.join(save_dir, f"{pl_base}.{ext}"), found, ext, pl_base)


def main():
    args = get_args()
    ext = args.format or choose_format()
    music_exts = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.ape', '.dsf', '.dff')

    if args.from_list or args.mass:
        s_dir = os.path.abspath(args.searchdir or os.getcwd())
        save_dir = os.path.abspath(args.savedir or s_dir)
        if not os.path.exists(save_dir): os.makedirs(save_dir)

        print(f"{Colors.CYAN}Индексация файлов в {s_dir}...{Colors.END}")
        db = []
        for r, _, fs in os.walk(s_dir):
            for f in fs:
                if f.lower().endswith(music_exts):
                    full_p = os.path.join(r, f)
                    path_to_save = full_p if args.absolute else os.path.relpath(full_p, s_dir)
                    db.append((normalize_name(f), path_to_save))

        if args.mass:
            mass_path = os.path.abspath(args.mass)
            if not os.path.isdir(mass_path):
                print(f"{Colors.RED}[x] Папка не найдена: {mass_path}{Colors.END}");
                sys.exit(1)

            txt_files = [os.path.join(mass_path, f) for f in os.listdir(mass_path) if f.lower().endswith('.txt')]
            for txt in txt_files:
                print(f"{Colors.CYAN}Обработка: {os.path.basename(txt)}{Colors.END}")
                process_list(txt, db, ext, save_dir, args.absolute)
        else:
            process_list(args.from_list, db, ext, save_dir, args.absolute)

    else:
        raw_p = args.path or args.savedir or input(f"{Colors.YELLOW}Путь к папке с музыке: {Colors.END}").strip()
        root_dir = os.path.abspath(raw_p)
        save_dir = os.path.abspath(args.savedir or root_dir)

        if not os.path.isdir(root_dir):
            print(f"{Colors.RED}[x] Путь не найден.{Colors.END}");
            sys.exit(1)
        if not os.path.exists(save_dir): os.makedirs(save_dir)

        for entry in os.scandir(root_dir):
            if entry.is_dir() and os.path.abspath(entry.path) != save_dir:
                tracks = []
                for r, _, fs in os.walk(entry.path):
                    for f in fs:
                        if f.lower().endswith(music_exts):
                            full_p = os.path.join(r, f)
                            tracks.append(full_p if args.absolute else os.path.relpath(full_p, root_dir))
                if tracks:
                    tracks.sort()
                    save_playlist(os.path.join(save_dir, f"{entry.name}.{ext}"), tracks, ext, entry.name)


if __name__ == "__main__":
    main()
