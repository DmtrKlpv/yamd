#!/usr/bin/env python3
import os
import argparse
from mutagen.mp3 import MP3
from mutagen.id3 import Encoding

# Словарь для перевода ID кодов в понятные названия
FRAME_NAMES = {
    "TIT2": "Title", "TPE1": "Artist", "TPE2": "Album Artist",
    "TALB": "Album", "TDRC": "Year", "TRCK": "Track",
    "TCON": "Genre", "COMM": "Comment", "USLT": "Lyrics",
    "TCOM": "Composer", "TPOS": "Disc", "TPUB": "Publisher",
    "TORY": "Original Year", "TSOP": "Sort Artist", "TSO2": "Sort Album Artist",
    "TSOA": "Sort Album", "TSOT": "Sort Title"
}


def fix_mojibake(text: str) -> str:
    """Исправляет типичные кракозябры (CP1251, прочитанный как Latin-1)"""
    if not isinstance(text, str) or not text.strip():
        return text

    # Проверяем наличие символов, характерных для ошибки декодирования
    if any(ord(c) > 127 for c in text):
        try:
            # Пытаемся "развернуть" ошибку: Latin-1 -> CP1251 -> UTF-8
            fixed = text.encode('latin-1').decode('cp1251')
            # Убеждаемся, что фикс вернул кириллицу, а не мусор
            if any('\u0400' <= c <= '\u04FF' for c in fixed):
                return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def process_file(filepath: str, dry_run: bool = False) -> bool:
    """Обрабатывает один MP3-файл. Возвращает True, если были изменения."""
    try:
        audio = MP3(filepath)
        if audio.tags is None:
            return False

        changes = []
        for frame_id, frame in audio.tags.items():
            # Работаем только с текстовыми полями
            if hasattr(frame, 'text') and frame.text:
                old_texts = list(frame.text)
                new_texts = [fix_mojibake(t) for t in old_texts]

                if new_texts != old_texts:
                    frame.text = new_texts
                    frame.encoding = Encoding.UTF8

                    readable_name = FRAME_NAMES.get(frame_id, frame_id)
                    old_str = " | ".join(str(t) for t in old_texts)
                    new_str = " | ".join(str(t) for t in new_texts)
                    changes.append((readable_name, old_str, new_str))

        if changes:
            print(f"File: {os.path.basename(filepath)}")
            for field, old, new in changes:
                print(f"  {field}: '{old}' -> '{new}'")

            if dry_run:
                print(f"  [DRY-RUN] Will save ({len(changes)} changes)\n")
            else:
                # v2_version=4 (целое число) вместо кортежа
                # v1=0 предотвращает создание тегов v1 (они не поддерживают кириллицу)
                audio.tags.save(filepath, v1=0, v2_version=4)
                print(f"  Saved ({len(changes)} changes)\n")
            return True
        return False

    except Exception as e:
        print(f"  Error in {os.path.basename(filepath)}: {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Fixing ID3 tag encoding in MP3 files (UTF-8 + ID3v2.4)"
    )
    parser.add_argument("directory", help="Path to music folder")
    parser.add_argument("--dry-run", action="store_true", help="Show changes only (do not save)")
    parser.add_argument("--ext", default=".mp3", help="File extension (default .mp3)")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: Folder not found: {args.directory}")
        return

    print(f"Search for {args.ext} in: {args.directory}")
    mode = "DRY-RUN (view only)" if args.dry_run else "WRITE (apply fixes)"
    print(f"Mode: {mode}\n")

    processed = fixed = 0
    for root, _, files in os.walk(args.directory):
        for file in files:
            if file.lower().endswith(args.ext):
                filepath = os.path.join(root, file)
                processed += 1
                if process_file(filepath, args.dry_run):
                    fixed += 1

    print(f"Done! Processed: {processed}, Fixed: {fixed}")


if __name__ == "__main__":
    main()