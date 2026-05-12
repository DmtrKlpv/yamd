#!/usr/bin/env python3
"""
Утилита для удаления поля Genre (Жанр) из ID3-тегов MP3 файлов.
Рекурсивно обрабатывает указанную папку и все вложенные подпапки.
"""

import argparse
import sys
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen import MutagenError


def remove_genre_from_mp3(directory, verbose=True, dry_run=False):
    dir_path = Path(directory).resolve()
    if not dir_path.is_dir():
        print(f"Ошибка: '{directory}' не является существующей папкой.")
        sys.exit(1)

    # Ищем все MP3 файлы (без учёта регистра)
    mp3_files = [p for p in dir_path.rglob('*') if p.is_file() and p.suffix.lower() == '.mp3']
    if not mp3_files:
        print("MP3 файлы не найдены.")
        return

    processed = 0
    skipped = 0
    errors = 0

    print(f"Найдено MP3 файлов: {len(mp3_files)}\n")

    for file_path in mp3_files:
        try:
            tags = EasyID3(file_path)
            if 'genre' in tags:
                del tags['genre']
                if not dry_run:
                    tags.save()
                    print(f"Жанр удалён: {file_path}") if verbose else None
                else:
                    print(f"(dry-run) Жанр был бы удалён: {file_path}") if verbose else None
                processed += 1
            else:
                print(f"Жанр отсутствует: {file_path.name}") if verbose else None
                skipped += 1
        except MutagenError as e:
            print(f"Ошибка чтения тегов {file_path.name}: {e}")
            errors += 1
        except PermissionError:
            print(f"Нет прав на запись: {file_path.name}")
            errors += 1
        except Exception as e:
            print(f"Неизвестная ошибка с {file_path.name}: {e}")
            errors += 1

    print(f"\nИтог:")
    print(f"   Файлов с изменениями: {processed}")
    print(f"   Пропущено (нет жанра): {skipped}")
    print(f"   Ошибки: {errors}")
    if dry_run:
        print("Запущен режим dry-run. Реальные изменения не вносились.")


def main():
    parser = argparse.ArgumentParser(
        description="Удаляет поле Genre (Жанр) из ID3-тегов MP3 файлов рекурсивно."
    )
    parser.add_argument(
        "directory",
        help="Путь к папке с MP3 файлами"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Тихий режим (вывод только итогов)"
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Тестовый запуск: показать, что будет удалено, без сохранения изменений"
    )
    args = parser.parse_args()

    print("Внимание: Утилита изменяет файлы. Рекомендуется сделать резервную копию папки перед запуском.\n")
    remove_genre_from_mp3(args.directory, verbose=not args.quiet, dry_run=args.dry_run)


if __name__ == "__main__":
    main()