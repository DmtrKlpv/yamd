#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FLAC + CUE to MP3 Converter
Нарезает FLAC по временным меткам из CUE, кодирует в MP3,
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
except ImportError:
    print("[ERROR] Отсутствует библиотека mutagen.")
    print("Установите: pip install mutagen")
    sys.exit(1)


def create_parser():
    parser = argparse.ArgumentParser(
        description="Конвертер FLAC+CUE -> MP3 с тегами ID3v2.4 и обложкой.",
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
            album_meta["FLAC_NAME"] = m.group(1)
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
    """Преобразует MM:SS:FF (75 кадров/сек) в секунды."""
    m = re.match(r'(\d+):(\d+):(\d+)', time_str)
    if not m:
        return 0.0
    minutes, seconds, frames = map(int, m.groups())
    return minutes * 60 + seconds + frames / 75.0


def extract_cover(flac_path: Path, base_dir: Path):
    try:
        audio = FLAC(flac_path)
        if audio.pictures:
            return audio.pictures[0].data
    except Exception:
        pass

    for fname in ["cover.jpg", "folder.jpg", "cover.png", "front.jpg", "albumart.jpg"]:
        img_path = base_dir / fname
        if img_path.exists():
            return img_path.read_bytes()
    return None


def get_mime_type(data: bytes) -> str:
    """Определяет MIME-тип изображения по заголовку."""
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
        if len(cue_files) > 1:
            print(f"[WARN] Найдено несколько .cue файлов. Использую: {cue_path.name}")
        print(f"[INFO] Найден CUE файл: {cue_path.name}")

    if not cue_path.is_file():
        parser.error(f"Путь не является файлом: {cue_path}")

    print(f"[INFO] Чтение CUE файла: {cue_path}")
    cue_content, detected_enc = read_cue_file(cue_path)
    print(f"[INFO] Кодировка CUE: {detected_enc}")

    album_meta, tracks = parse_cue_content(cue_content)
    cue_dir = cue_path.parent

    flac_name = album_meta.get("FLAC_NAME", "")
    print(f"[INFO] FLAC файл из CUE: {flac_name}")

    flac_path = cue_dir / flac_name if flac_name else None
    if not flac_path or not flac_path.exists():
        print(f"[WARN] Указанный FLAC не найден. Поиск в папке...")
        flac_files = list(cue_dir.glob("*.flac"))
        if flac_files:
            flac_path = flac_files[0]
            print(f"[INFO] Найден FLAC: {flac_path.name}")
        else:
            sys.exit("[ERROR] FLAC файл не найден.")

    ffmpeg_path = resolve_ffmpeg()
    out_dir = Path(args.output).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Выходная папка: {out_dir}")
    print(f"[INFO] Качество: {args.quality}")
    print(f"[INFO] Треков: {len(tracks)}")

    if args.quality == "v0":
        enc_args = ["-c:a", "libmp3lame", "-q:a", "0"]
    else:
        enc_args = ["-c:a", "libmp3lame", "-b:a", "320k"]

    total_tracks = len(tracks)
    print("\n[INFO] Нарезка и кодирование треков...")
    print("-" * 60)

    for i, track in enumerate(tracks, start=1):
        track_title = track.get("TITLE", f"Track {i}")
        track_performer = track.get("PERFORMER", album_meta.get("PERFORMER", "Unknown Artist"))
        start_sec = time_to_seconds(track.get("TIME", "00:00:00"))
        end_sec = time_to_seconds(tracks[i]["TIME"]) if i < total_tracks else None

        print(f"{i:02d} из {total_tracks}: {track_performer} - {track_title}")
        if args.debug:
            print(f"      Время: {track.get('TIME', 'N/A')} ({start_sec:.2f}s - {end_sec:.2f}s)")

        cmd = [ffmpeg_path, "-i", str(flac_path)]
        if start_sec > 0:
            cmd.extend(["-ss", f"{start_sec:.3f}"])
        if end_sec is not None:
            cmd.extend(["-to", f"{end_sec:.3f}"])
        cmd.extend([*enc_args, "-y", "-loglevel", "error", str(out_dir / f"track_{i:02d}.mp3")])

        if args.debug:
            print(f"[DEBUG] Команда: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            stderr_msg = e.stderr.decode(errors='replace') if e.stderr else "Без вывода"
            print(f"  [FAIL] Ошибка кодирования: {stderr_msg}")
            continue

    cover_data = extract_cover(flac_path, cue_dir)
    cover_mime = get_mime_type(cover_data) if cover_data else "image/jpeg"

    print("-" * 60)
    print("[INFO] Применение тегов ID3v2.4 (UTF-8) и обложки...")
    print("-" * 60)

    for i, track in enumerate(tracks, start=1):
        mp3_file = out_dir / f"track_{i:02d}.mp3"
        if not mp3_file.exists():
            print(f"[WARN] Пропущен трек {i}")
            continue

        track_title = track.get("TITLE", f"Track {i}")
        track_performer = track.get("PERFORMER", album_meta.get("PERFORMER", ""))

        audio = MP3(mp3_file)
        if audio.tags is None:
            audio.add_tags()

        audio.tags.version = (2, 4, 0)
        enc = 3

        audio.tags.add(TIT2(encoding=enc, text=[track_title]))
        audio.tags.add(TPE1(encoding=enc, text=[track_performer]))
        audio.tags.add(TALB(encoding=enc, text=[album_meta.get("TITLE", "")]))
        audio.tags.add(TDRC(encoding=enc, text=[album_meta.get("DATE", "")]))
        audio.tags.add(TCON(encoding=enc, text=[album_meta.get("GENRE", "")]))
        audio.tags.add(TRCK(encoding=enc, text=[f"{i:02d}"]))

        # ИСПРАВЛЕНО: полное условие if cover_data:
        if cover_data:
            for fid in list(audio.tags.keys()):
                if fid.startswith("APIC"):
                    del audio.tags[fid]
            audio.tags.add(APIC(
                encoding=enc,
                mime=cover_mime,
                type=3,
                desc="Cover",
                data=cover_data
            ))

        audio.save(v2_version=4)

        clean_title = re.sub(r'[<>:"/\\|?*]', "", track_title).strip()
        new_name = f"{i:02d} - {clean_title}.mp3"
        final_path = out_dir / new_name
        if mp3_file != final_path:
            os.rename(mp3_file, final_path)

        print(f"[{i:02d}] {track_title} [meta: {album_meta.get('DATE', '')}]")

    print("-" * 60)
    print(f"[DONE] Готово! Файлы сохранены в: {out_dir}")
    print(f"[INFO] Все теги записаны в кодировке UTF-8 (ID3v2.4)")


if __name__ == "__main__":
    main()