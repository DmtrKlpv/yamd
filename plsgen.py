import argparse
import sys
import re
import os
from yandex_music import Client


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    BLACK = '\033[30m'
    BG_YELLOW = '\033[43m'
    END = '\033[0m'


def get_playlist_tracks(iframe_code, custom_filename):
    # 1. Извлекаем данные из строки iframe
    match = re.search(r'playlist/([^/]+)/(\d+)', iframe_code)
    if not match:
        print(f"{Colors.RED}[x] Не удалось найти данные плейлиста в переданном тексте.{Colors.END}")
        print("")
        return

    username, playlist_id = match.groups()
    client = Client().init()

    try:
        # 2. Получаем объект плейлиста
        playlist = client.users_playlists(playlist_id, username)
        tracks = playlist.fetch_tracks()

        raw_count = len(tracks)
        print ('---------------------------------')
        print(f"Найдено треков в плейлисте: {raw_count}")

        # 3. Формируем список строк
        track_list = []
        for item in tracks:
            track = item.track if hasattr(item, 'track') else item
            artists = ", ".join([a.name for a in track.artists])
            track_list.append(f"{artists} - {track.title}")

        # 4. Проверка и удаление дубликатов
        unique_tracks = list(dict.fromkeys(track_list))
        final_count = len(unique_tracks)

        if raw_count != final_count:
            print(f"Внимание: Удалено дубликатов: {raw_count - final_count}")
        else:
            print("Дубликатов не обнаружено.")

        # 5. Работа с директорией и именем файла
        target_dir = "pls"
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            print(f"Создана директория: {target_dir}")

        if not custom_filename or not custom_filename.strip():
            custom_filename = "playlist_export"

        if not custom_filename.endswith(".txt"):
            custom_filename += ".txt"

        # Формируем полный путь к файлу
        file_path = os.path.join(target_dir, custom_filename)

        # 6. Запись в файл
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(unique_tracks))

        print(f"Готово! Файл сохранен в: {file_path}")
        print(f"Итого строк в файле: {final_count}")
        print('---------------------------------')
    except Exception as e:
        print(f"{Colors.RED}[x] Произошла ошибка при получении данных: {e}{Colors.END}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Экспорт плейлиста Яндекс Музыки в папку 'pls'")
    parser.add_argument("-file", type=str, help="Имя файла (сохранится в папку pls)")
    parser.add_argument("-iframe", type=str, help="Строка iframe. Используйте одинарные кавычки")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        iframe_input = input("Вставьте HTML-код (iframe): ")
        file_name_input = input("Введите имя файла (Enter для 'playlist_export.txt'): ")
    else:
        iframe_input = args.iframe if args.iframe else input("Вставьте HTML-код (iframe): ")
        file_name_input = args.file

    get_playlist_tracks(iframe_input, file_name_input)
