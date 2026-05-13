#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FLAC/APE + CUE to MP3 Converter
Нарезает аудио (FLAC/APE) по временным меткам из CUE, кодирует в MP3,
прописывает ID3v2.4 теги (UTF-8) и встраивает обложку.
"""

import os
import sys
import re
import shutil
import subprocess
import urllib.request
import argparse
from pathlib import Path
from zipfile import ZipFile
import tarfile

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC
    from mutagen.flac import FLAC
    from mutagen.apev2 import APEv2
except ImportError:
    print("[ERROR] Отсутствует библиотека mutagen.")
    print("Установите: pip install mutagen")
    sys.exit(1)


def create_parser():
    parser = argparse.ArgumentParser(
        description="Конвертер FLAC/APE+CUE -> MP3 с тегами ID3v2.4 и обложкой.",
        epilog="Примеры:\n"
               "  python cue2mp3.py -i release.cue\n"
               "  python cue2mp3.py -i \"D:\\Music\\Album\" -o ./mp3 -q 320"
    )
    parser.add_argument("-i", "--input", required=True, help="Путь к .cue файлу или папке с альбомом")
    parser.add_argument("-o", "--output", default="mp3_output", help="Папка вывода (по умолчанию: mp3_output)")
    parser.add_argument("-q", "--quality", choices=["v0", "320"], default="v0",
                        help="Качество: v0 (LAME VBR V0) или 320 (CBR 320kbps)")
    parser.add_argument("--debug", action="store_true", help="Включить отладочный вывод")
    return parser


def resolve_ffmpeg():
    ff = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ff:
        return str(Path(ff).resolve())

    local_dir = Path("ffmpeg_bin")
    ff_local = local_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if ff_local.exists():
        return str(ff_local.resolve())

    print("[INFO] FFmpeg не найден. Загрузка портативной версии...")
    local_dir.mkdir(exist_ok=True)

    try:
        if sys.platform == "win32":
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            _download_and_extract_zip(url, local_dir)
        elif sys.platform == "darwin":
            url = "https://evermeet.cx/ffmpeg/ffmpeg-12.1.2.zip"
            _download_and_extract_zip(url, local_dir)
        else:
            url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            _download_and_extract_tarxz(url, local_dir)
    except Exception as e:
        sys.exit(f"[ERROR] Не удалось загрузить FFmpeg: {e}")

    for root, _, files in os.walk(local_dir):
        for f in files:
            if f.startswith("ffmpeg") and not f.endswith((".md", ".txt", ".zip", ".xz")):
                src = Path(root) / f
                shutil.move(str(src), str(ff_local))
                return str(ff_local.resolve())

    sys.exit("[ERROR] Исполняемый файл FFmpeg не найден после распаковки.")


def _download_and_extract_zip(url, dest_dir):
    archive_path = dest_dir / "temp.zip"
    print(f"[INFO] Загрузка: {url}")
    urllib.request.urlretrieve(url, archive_path)
    with ZipFile(archive_path, "r") as z:
        z.extractall(dest_dir)
    archive_path.unlink()


def _download_and_extract_tarxz(url, dest_dir):
    archive_path = dest_dir / "temp.tar.xz"
    print(f"[INFO] Загрузка: {url}")
    urllib.request.urlretrieve(url, archive_path)
    with tarfile.open(archive_path, "r:xz") as t:
        t.extractall(dest_dir)
    archive_path.unlink()


def read_cue_file(cue_path: Path):
    for enc in ["utf-8-sig", "utf-8", "cp1251", "iso-8859-1", "windows-1251"]:
        try:
            with open(cue_path, "r", encoding=enc) as f:
                content = f.read()
            if "FILE" in content.upper() and "TRACK" in content.upper():
                return content, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    sys.exit("[ERROR] Не удалось прочитать CUE файл в поддерживаемой кодировке.")


def parse_cue_content(content: str):
    album_meta = {}
    tracks = []
    current_track = None

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(";") or line.upper().startswith("REM"):
            continue

        m = re.match(r'(PERFORMER|TITLE|DATE|GENRE)\s+"(.*)"', line, re.IGNORECASE)
        if m:
            key, val = m.group(1).upper(), m.group(2)
            if current_track is None:
                album_meta[key] = val
            else:
                current_track[key] = val
            continue

        m = re.match(r'FILE\s+"(.+)"', line, re.IGNORECASE)
        if m:
            album_meta["SOURCE_FILE"] = m.group(1)
            continue

        m = re.match(r'TRACK\s+(\d+)\s+AUDIO', line, re.IGNORECASE)
        if m:
            if current_track:
                tracks.append(current_track)
            current_track = {"NUM": int(m.group(1))}
            continue

        m = re.match(r'INDEX\s+01\s+(.+)', line)
        if m:
            if current_track:
                current_track["TIME"] = m.group(1).strip()

    if current_track:
        tracks.append(current_track)

    for t in tracks:
        t.setdefault("TITLE", album_meta.get("TITLE", "Unknown Track"))
        t.setdefault("PERFORMER", album_meta.get("PERFORMER", "Unknown Artist"))
        t.setdefault("NUM", tracks.index(t) + 1)

    return album_meta, tracks


def time_to_seconds(time_str: str) -> float:
    m = re.match(r'(\d+):(\d+):(\d+)', time_str)
    if not m:
        return 0.0
    minutes, seconds, frames = map(int, m.groups())
    return minutes * 60 + seconds + frames / 75.0


def extract_cover(audio_path: Path, base_dir: Path):
    """Пытается извлечь обложку из тегов (FLAC/APE) или найти в папке."""
    # 1. Проверка встроенных тегов
    try:
        suffix = audio_path.suffix.lower()
        if suffix == ".flac":
            audio = FLAC(audio_path)
            if audio.pictures:
                return audio.pictures[0].data
        elif suffix == ".ape":
            audio = APEv2(audio_path)
            # В APE обложка часто лежит в поле 'Cover Art (Front)' или просто 'Cover Art'
            for key in audio.keys():
                if "Cover Art" in key:
                    return audio[key].value
    except Exception:
        pass

    # 2. Поиск внешнего файла
    for fname in ["cover.jpg", "folder.jpg", "cover.png", "front.jpg", "albumart.jpg"]:
        for f in base_dir.glob("*"):
            if f.name.lower() == fname:
                return f.read_bytes()
    return None


def get_mime_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return "image/jpeg"


def main():
    parser = create_parser()
    args = parser.parse_args()

    cue_path = Path(args.input).resolve()
    if not cue_path.exists():
        parser.error(f"Указанный путь не существует: {cue_path}")

    if cue_path.is_dir():
        cue_files = list(cue_path.glob("*.cue"))
        if not cue_files:
            parser.error(f"В папке не найден .cue файл: {cue_path}")
        cue_path = cue_files[0]
        print(f"[INFO] Найден CUE файл: {cue_path.name}")

    cue_content, detected_enc = read_cue_file(cue_path)
    album_meta, tracks = parse_cue_content(cue_content)
    cue_dir = cue_path.parent

    source_name = album_meta.get("SOURCE_FILE", "")
    source_path = cue_dir / source_name if source_name else None

    # Поиск аудиофайла, если указанный в CUE не найден
    if not source_path or not source_path.exists():
        print(f"[WARN] Исходный файл не найден. Поиск альтернатив...")
        valid_exts = [".flac", ".ape", ".wav", ".wv"]
        found_audio = [f for f in cue_dir.glob("*") if f.suffix.lower() in valid_exts]
        if found_audio:
            source_path = found_audio[0]
            print(f"[INFO] Использую аудио: {source_path.name}")
        else:
            sys.exit("[ERROR] Аудиофайл (FLAC/APE) не найден в папке.")

    ffmpeg_path = resolve_ffmpeg()
    out_dir = Path(args.output).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.quality == "v0":
        enc_args = ["-c:a", "libmp3lame", "-q:a", "0"]
    else:
        enc_args = ["-c:a", "libmp3lame", "-b:a", "320k"]

    total_tracks = len(tracks)
    print(f"\n[INFO] Обработка: {source_path.name} -> MP3")
    print("-" * 60)

    for i, track in enumerate(tracks, start=1):
        track_title = track.get("TITLE", f"Track {i}")
        track_performer = track.get("PERFORMER", album_meta.get("PERFORMER", "Unknown Artist"))
        start_sec = time_to_seconds(track.get("TIME", "00:00:00"))
        end_sec = time_to_seconds(tracks[i]["TIME"]) if i < total_tracks else None

        print(f"{i:02d}/{total_tracks}: {track_performer} - {track_title}")

        cmd = [ffmpeg_path, "-i", str(source_path)]
        if start_sec > 0:
            cmd.extend(["-ss", f"{start_sec:.3f}"])
        if end_sec is not None:
            cmd.extend(["-to", f"{end_sec:.3f}"])
        cmd.extend([*enc_args, "-y", "-loglevel", "error", str(out_dir / f"track_{i:02d}.mp3")])

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  [FAIL] Ошибка FFmpeg на треке {i}")
            continue

    cover_data = extract_cover(source_path, cue_dir)
    cover_mime = get_mime_type(cover_data) if cover_data else "image/jpeg"

    print("-" * 60)
    print("[INFO] Запись метаданных...")

    for i, track in enumerate(tracks, start=1):
        mp3_file = out_dir / f"track_{i:02d}.mp3"
        if not mp3_file.exists(): continue

        audio = MP3(mp3_file)
        if audio.tags is None: audio.add_tags()
        audio.tags.version = (2, 4, 0)

        enc = 3  # UTF-8
        audio.tags.add(TIT2(encoding=enc, text=[track.get("TITLE", "")]))
        audio.tags.add(TPE1(encoding=enc, text=[track.get("PERFORMER", "")]))
        audio.tags.add(TALB(encoding=enc, text=[album_meta.get("TITLE", "")]))
        audio.tags.add(TDRC(encoding=enc, text=[album_meta.get("DATE", "")]))
        audio.tags.add(TCON(encoding=enc, text=[album_meta.get("GENRE", "")]))
        audio.tags.add(TRCK(encoding=enc, text=[f"{i:02d}"]))

        if cover_data:
            audio.tags.add(APIC(encoding=enc, mime=cover_mime, type=3, desc="Cover", data=cover_data))

        audio.save(v2_version=4)

        # Переименование
        clean_title = re.sub(r'[<>:"/\\|?*]', "", track.get("TITLE", "Track")).strip()
        new_name = f"{i:02d} - {clean_title}.mp3"
        final_path = out_dir / new_name
        os.replace(mp3_file, final_path)

    print(f"[DONE] Альбом готов в: {out_dir}")


if __name__ == "__main__":
    main()