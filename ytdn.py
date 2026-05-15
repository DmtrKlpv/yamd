#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
import yt_dlp

def check_ffmpeg() -> bool:
    """Проверяет, доступен ли FFmpeg в системном PATH."""
    if not shutil.which("ffmpeg"):
        print("FFmpeg не найден в PATH. Для конвертации в MP3 он необходим.")
        print("Установка:")
        print("   • Windows: https://ffmpeg.org/download.html (распакуйте и добавьте bin в PATH)")
        print("   • macOS:   brew install ffmpeg")
        print("   • Linux:   sudo apt install ffmpeg  или  sudo dnf install ffmpeg")
        return False
    return True

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Скачивает аудио с YouTube в максимальном качестве и конвертирует в MP3"
    )
    parser.add_argument("url", help="Ссылка на YouTube видео или плейлист")
    parser.add_argument(
        "--savedir", "-d",
        default=".",
        help="Папка для сохранения (по умолчанию: текущая директория)"
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Разрешить загрузку всего плейлиста (по умолчанию отключено)"
    )
    args = parser.parse_args()

    if not check_ffmpeg():
        sys.exit(1)

    # Создаём папку, если её нет
    os.makedirs(args.savedir, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio',                     # Максимальное качество аудио
        'outtmpl': os.path.join(args.savedir, '%(title)s.%(ext)s'),
        'noplaylist': not args.playlist,           # По умолчанию только 1 видео
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320'              # Битрейт MP3
        }],
        'quiet': False,
        'no_warnings': False,
        'concurrent_downloads': 4,                 # Ускоряет загрузку
    }

    print(f"Загрузка: {args.url}")
    print(f"Папка сохранения: {os.path.abspath(args.savedir)}\n")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([args.url])
        print("\nЗагрузка и конвертация в MP3 завершены!")
    except yt_dlp.utils.DownloadError as e:
        print(f"\nшибка yt-dlp: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nНеожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()