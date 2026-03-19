import os
import sys
import re
import time
import requests
import argparse
from yandex_music import Client
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, TYER
from mutagen.flac import FLAC, Picture  # Добавлено для FLAC

# ================== НАСТРОЙКИ ==================
VER = '1.3.2'


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    BLACK = '\033[30m'
    BG_YELLOW = '\033[43m'
    END = '\033[0m'


def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


def write_tags(filepath, track, timeout):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.mp3':
            audio = MP3(filepath, ID3=ID3)
            try:
                audio.add_tags()
            except:
                pass
            audio.tags.add(TIT2(encoding=3, text=track.title))
            artists = ", ".join([a.name for a in track.artists])
            audio.tags.add(TPE1(encoding=3, text=artists))
            if track.albums:
                audio.tags.add(TALB(encoding=3, text=track.albums[0].title))
                if track.albums[0].year:
                    audio.tags.add(TYER(encoding=3, text=str(track.albums[0].year)))
            if track.cover_uri:
                try:
                    cover_url = "https://" + track.cover_uri.replace("%%", "600x600")
                    img_data = requests.get(cover_url, timeout=timeout).content
                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_data))
                except:
                    pass
            audio.save()
        elif ext == '.flac':
            audio = FLAC(filepath)
            audio["title"] = track.title
            audio["artist"] = ", ".join([a.name for a in track.artists])
            if track.albums:
                audio["album"] = track.albums[0].title
                if track.albums[0].year:
                    audio["date"] = str(track.albums[0].year)
            if track.cover_uri:
                try:
                    cover_url = "https://" + track.cover_uri.replace("%%", "600x600")
                    img_data = requests.get(cover_url, timeout=timeout).content
                    image = Picture()
                    image.type = 3
                    image.mime = "image/jpeg"
                    image.desc = "Cover"
                    image.data = img_data
                    audio.add_picture(image)
                except:
                    pass
            audio.save()
    except Exception:
        pass


def verify_report(target_dir, original_list, downloaded_list):
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- ОТЧЕТ О НЕСООТВЕТСТВИЯХ ---{Colors.END}")
    missing = [item for item in original_list if item not in downloaded_list]
    report_path = os.path.join(target_dir, "!missing_tracks.txt")
    if not missing:
        print(f"{Colors.GREEN}Все треки из файла обработаны успешно{Colors.END}")
        if os.path.exists(report_path): os.remove(report_path)
    else:
        print(f"{Colors.YELLOW}Не скачано: {len(missing)} треков. Список в !missing_tracks.txt{Colors.END}")
        with open(report_path, 'w', encoding='utf-8') as f:
            for track in missing: f.write(f"{track}\n")
    print(f"Итого: {len(downloaded_list)} из {len(original_list)} треков.")


def main():
    if os.name == 'nt': os.system('color')

    # Парсинг аргументов перенесен в начало, чтобы флаг -h работал без запроса токена
    parser = argparse.ArgumentParser(description="Yandex Music Downloader")
    parser.add_argument("-playlist", help="Путь к txt-файлу плейлиста")
    parser.add_argument("-dir", help="Папка для скачивания")
    parser.add_argument("-timeout", type=int, help="Таймаут соединения")
    parser.add_argument("-maxtr", type=int, help="Макс. количество попыток")
    parser.add_argument("-flac", action="store_true", help="Скачивать FLAC, если доступно")
    args = parser.parse_args()

    print(f"{Colors.BG_YELLOW}{Colors.BLACK}{Colors.BOLD} Yamd ver. {VER} {Colors.END}\n")

    config_file = 'init.tok'
    config = {}

    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line: continue
                key, val = line.split('=', 1)
                config[key.strip()] = val.strip()

    token = config.get('TOKEN')
    client = None

    while True:
        if not token:
            print(f'{Colors.YELLOW}Токен не найден.{Colors.END}')
            token = input(f" Введите ваш Яндекс.Музыка токен: {Colors.END}").strip()
        try:
            client = Client(token).init()
            print(f"{Colors.GREEN}[+] Авторизация успешна{Colors.END}")
            config['TOKEN'] = token
            with open(config_file, 'w', encoding='utf-8') as f:
                for k, v in config.items(): f.write(f"{k}={v}\n")
            break
        except Exception as e:
            print(f"{Colors.RED}[-] Ошибка токена или сети: {e}{Colors.END}")
            token = None

    DOWNLOAD_DIR = args.dir or config.get('DOWNLOAD_DIR', 'downloads')
    TIMEOUT = args.timeout or int(config.get('TIMEOUT', 15))
    MAX_RETRIES = args.maxtr or int(config.get('MAX_RETRIES', 3))

    input_file = args.playlist or input("Путь к txt-файлу плейлиста: ")

    if not os.path.exists(input_file):
        print(f"{Colors.RED}[-] Файл плейлиста не найден{Colors.END}")
        return

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    target_dir = os.path.join(DOWNLOAD_DIR, sanitize(base_name))
    if not os.path.exists(target_dir): os.makedirs(target_dir)

    with open(input_file, 'r', encoding='utf-8') as f:
        original_tracks = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    successfully_processed = []
    print(f"В директории: {DOWNLOAD_DIR} создана папка /{base_name}, Таймаут: {TIMEOUT}, Попыток: {MAX_RETRIES}")
    print(f"{Colors.BOLD}Коллекция:{Colors.END} {base_name} | {len(original_tracks)} треков")
    print("-" * 80)

    trackCounter = 0
    for query in original_tracks:
        trackCounter += 1
        display_name = (query[:67] + '...') if len(query) > 70 else query
        print(f"{display_name:<70} | {trackCounter}", end=" ", flush=True)

        try:
            search = client.search(query)
            if not search.tracks or not search.tracks.results:
                print(f"{Colors.RED}НЕ НАЙДЕНО{Colors.END}")
                continue

            track = search.tracks.results[0]
            info = track.get_download_info(get_direct_links=True)

            # Логика выбора качества
            selected_info = None
            if args.flac:
                flac_options = [i for i in info if i.codec == 'flac']
                if flac_options: selected_info = flac_options[0]

            if not selected_info:
                mp3_options = [i for i in info if i.codec == 'mp3']
                mp3_options.sort(key=lambda x: x.bitrate_in_kbps, reverse=True)
                selected_info = mp3_options[0] if mp3_options else info[0]

            ext = f".{selected_info.codec}"
            artists_str = ", ".join([a.name for a in track.artists])
            filename = f"{sanitize(artists_str)} - {sanitize(track.title)}{ext}"
            filepath = os.path.join(target_dir, filename)

            if os.path.exists(filepath):
                sys.stdout.write(f"\r{display_name:<70} {trackCounter:<8} | {Colors.YELLOW}ПРОПУЩЕНО (Существует){Colors.END}\n")
                successfully_processed.append(query)
                continue

            link = selected_info.get_direct_link()
            downloaded = False
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.get(link, stream=True, timeout=TIMEOUT)
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))

                    with open(filepath, 'wb') as f:
                        current_size = 0
                        for data in response.iter_content(chunk_size=32768):
                            current_size += len(data)
                            f.write(data)
                            if total_size > 0:
                                percent = int(100 * current_size / total_size)
                                sys.stdout.write(f'\r{display_name:<70} {Colors.CYAN}ЗАГРУЗКА{Colors.END} | {Colors.CYAN}{percent}%{Colors.END}')
                                sys.stdout.flush()
                    downloaded = True
                    break
                except Exception:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(1)
                        continue
                    else:
                        raise

            if downloaded:
                write_tags(filepath, track, TIMEOUT)
                successfully_processed.append(query)
                q_label = "FLAC" if selected_info.codec == 'flac' else f"MP3 {selected_info.bitrate_in_kbps}k"
                sys.stdout.write(f"\r{display_name:<70} {trackCounter:<8} | {Colors.GREEN}OK ({q_label}){Colors.END}\n")

        except Exception as e:
            sys.stdout.write(f"\r{display_name:<70} {trackCounter:<8} | {Colors.RED}ОШИБКА{Colors.END} ({type(e).__name__})\n")

    print("-" * 80)
    verify_report(target_dir, original_tracks, successfully_processed)


if __name__ == "__main__":
    main()
