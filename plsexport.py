import re
import os
from yandex_music import Client


def get_client():
    token = "y0_AgAEA7qkBFzBAAG8XgAAAAEDCV-yAADiveG8Pu9II53p0-XW8ZYx5rr7FQ"
    return Client(token).init()


def export_playlist(url):
    client = get_client()

    # Извлекаем GUID
    guid_match = re.search(r'playlists/([a-f0-9\-]+)', url)
    if not guid_match:
        print("[-] Ошибка в ссылке.")
        return

    playlist_guid = guid_match.group(1)
    print(f"[*] Запрос данных для: {playlist_guid}...")

    try:
        # В библиотеке yandex-music для GUID ссылок используем этот метод:
        # Он возвращает список, берем первый элемент [0]
        playlists = client.playlists_list(playlist_guid)

        if not playlists:
            print("[-] Плейлист не найден. Возможно, он приватный.")
            return

        playlist = playlists[0]
        title = playlist.title or "Exported_Playlist"
        filename = re.sub(r'[\\/*?:"<>|]', "", title) + ".txt"

        print(f"[*] Плейлист: '{title}' | Треков: {playlist.track_count}")

        # Загружаем треки
        tracks = playlist.fetch_tracks()

        with open(filename, 'w', encoding='utf-8') as f:
            for item in tracks:
                # В объекте ответа трек может быть вложенным
                track = item.track if hasattr(item, 'track') else item

                if track and track.artists:
                    artists = ", ".join([a.name for a in track.artists])
                    f.write(f"{artists} - {track.title}\n")

        print("-" * 30)
        print(f"[+] ГОТОВО! Файл сохранен: {os.path.abspath(filename)}")

    except Exception as e:
        print(f"[-] Ошибка: {e}")


if __name__ == "__main__":
    url = input("Введите ссылку: ").strip()
    export_playlist(url)