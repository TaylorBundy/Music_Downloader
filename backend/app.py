import os
import re
import uuid
import json
import shutil
import threading
import subprocess
import pathlib
from pathlib import Path
from queue import Queue, Empty
from urllib.parse import urlparse

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import yt_dlp

# Obtenemos la ruta del usuario
root_start_path = pathlib.Path.home()
BASE_DIR = Path(__file__).resolve().parent
# print(BASE_DIR.parent)
# cambiamos el working directory al la ruta del usuario
os.chdir(root_start_path)
# print("New Working Directory:", os.getcwd())
BASE_DIR2 = Path(os.getcwd())
DOWNLOAD_ROOT = BASE_DIR2
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# print(root_start_path)
# ruta_origen = r"C:\Users\juan carlos\Music\Taylor"
# ruta = os.path.join(ruta_origen, nombre)

app = Flask(__name__)
CORS(app)

jobs = {}
jobs_lock = threading.Lock()

AUDIO_FORMATS = {"mp3", "flac", "ogg"}
VIDEO_FORMATS = {"mp4", "flv", "mov"}
ALLOWED_TYPES = {"audio", "video"}

ALLOWED_DOWNLOAD_ROOTS = [
    Path(r"C:\ytdlp\downloads").resolve(),
    Path(r"C:\Users\juan carlos\Music\Taylor").resolve(),
]


def safe_filename(name: str) -> str:

    name = (name or "").strip()

    if not name:
        return ""

    # Eliminar solamente una extensión existente
    name = Path(name).stem

    # Caracteres realmente inválidos para nombres de Windows
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)

    # Windows no permite terminar con espacio o punto
    name = name.rstrip(" .")

    return name


def normalize_time(value: str) -> str:
    """
    Valida HH:MM:SS o H:MM:SS.
    Devuelve siempre HH:MM:SS.
    """
    value = (value or "").strip()

    if not value:
        return ""

    match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})", value)

    if not match:
        raise ValueError("Los tiempos deben utilizar el formato HH:MM:SS.")

    hours, minutes, seconds = map(int, match.groups())

    if minutes > 59 or seconds > 59:
        raise ValueError("Minutos y segundos deben estar entre 00 y 59.")

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def time_to_seconds(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def validate_cookies_file(file_storage):
    if not file_storage:
        return None

    filename = (file_storage.filename or "").lower()

    if not filename.endswith(".txt"):
        raise ValueError("El archivo de cookies debe ser un .txt.")

    return file_storage


def safe_destination(destination: str):
    destination = (destination or "").strip()

    if not destination:
        raise ValueError("No se especificó una ruta de destino.")

    destination = destination.replace("\\", "/")

    # Convertir a Path
    path = Path(destination).expanduser().resolve()

    # Verificar que esté dentro de una ruta permitida
    permitido = False

    for root in ALLOWED_DOWNLOAD_ROOTS:
        if path == root or root in path.parents:
            permitido = True
            break

    if not permitido:
        raise ValueError("Ruta de destino no permitida.")

    path.mkdir(parents=True, exist_ok=True)

    return path


def safe_destination2(destination: str):
    """
    Evita que el usuario pueda escribir fuera de DOWNLOAD_ROOT.
    La ruta enviada por el frontend es relativa al directorio downloads.
    """
    destination = (destination or "downloads").strip()

    destination = destination.replace("\\", "/")
    destination = destination.lstrip("/")

    parts = [part for part in Path(destination).parts if part not in ("", ".", "..")]

    relative = Path(*parts) if parts else Path()

    final = (DOWNLOAD_ROOT / relative).resolve()

    if (
        DOWNLOAD_ROOT.resolve() not in final.parents
        and final != DOWNLOAD_ROOT.resolve()
    ):
        raise ValueError("Ruta de destino no permitida.")

    final.mkdir(parents=True, exist_ok=True)
    return final


def update_job(job_id, **values):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(values)


def get_job(job_id):
    with jobs_lock:
        return dict(jobs.get(job_id, {}))


def get_media_duration(file_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError("No se pudo obtener la duración del archivo.")

    try:
        return float(result.stdout.strip())

    except ValueError:
        raise RuntimeError("La duración obtenida por ffprobe no es válida.")


def format_seconds(seconds):
    return f"{seconds:.3f}"


def push_event(job_id, data):
    with jobs_lock:
        job = jobs.get(job_id)

    if job:
        job["queue"].put(data)


def parse_percent(line):
    match = re.search(r"(\d+(?:\.\d+)?)%", line)
    return float(match.group(1)) if match else None


def parse_speed(line):
    match = re.search(r"at\s+([\d.]+\s*[KMG]?iB/s)", line)
    return match.group(1) if match else None


def parse_eta(line):
    match = re.search(r"ETA\s+([0-9:]+)", line)
    return match.group(1) if match else None


def parse_speed2(line):
    match = re.search(r"at\\s+([\\d.]+\\s*[KMG]?iB/s)", line)
    return match.group(1) if match else None


def parse_eta2(line):
    match = re.search(r"ETA\\s+([0-9:]+)", line)
    return match.group(1) if match else None


def run_job(
    job_id,
    url,
    media_type,
    output_format,
    filename,
    destination,
    start_time="",
    end_time="",
    cookies_path=None,
):
    job_dir = destination / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        update_job(job_id, status="downloading")

        output_template = str(job_dir / "%(title)s.%(ext)s")

        def progress_hook(data):
            status = data.get("status")

            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                downloaded = data.get("downloaded_bytes", 0)

                percent = (downloaded / total * 100) if total else 0

                speed = data.get("_speed_str") or ""
                eta = data.get("_eta_str") or ""

                update_job(job_id, progress=percent)

                push_event(
                    job_id,
                    {
                        "status": "downloading",
                        "progress": percent,
                        "speed": speed,
                        "eta": eta,
                    },
                )

            elif status == "finished":
                update_job(job_id, progress=100)

                push_event(
                    job_id,
                    {"status": "converting", "progress": 100, "speed": "", "eta": ""},
                )

        # ydl_opts = {
        #     "outtmpl": output_template,
        #     "progress_hooks": [progress_hook],
        #     "noplaylist": True,
        #     "quiet": True,
        #     "no_warnings": True,
        #     "restrictfilenames": True,
        # }
        ydl_opts = {
            "outtmpl": output_template,
            "progress_hooks": [progress_hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
            "extractor_args": {"youtube": {"player_client": ["default"]}},
        }

        # Cookies opcionales. Equivale a:
        # --cookies /ruta/cookies.txt
        if cookies_path:
            ydl_opts["cookiefile"] = cookies_path

        # Si se indicó un intervalo, utiliza el equivalente de:
        # --download-sections "*00:10:01-00:15:23"
        if start_time or end_time:
            section_start = start_time or "00:00:00"
            section_end = end_time or "inf"
            ydl_opts["download_sections"] = [f"*{section_start}-{section_end}"]
            ydl_opts["force_keyframes_at_cuts"] = True

        if media_type == "audio":
            ydl_opts["format"] = "bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo*+bestaudio/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))

        if not downloaded_path.exists():
            candidates = list(job_dir.iterdir())
            if not candidates:
                raise FileNotFoundError("yt-dlp no generó ningún archivo.")
            downloaded_path = candidates[0]

        output_name = filename or safe_filename(info.get("title")) or "video"
        output_path = destination / f"{output_name}.{output_format}"

        push_event(
            job_id, {"status": "converting", "progress": 100, "speed": "", "eta": ""}
        )

        command = ["ffmpeg", "-y", "-i", str(downloaded_path)]

        if media_type == "audio":
            if output_format == "mp3":
                command += ["-vn", "-codec:a", "libmp3lame", "-q:a", "2"]
            elif output_format == "flac":
                command += ["-vn", "-codec:a", "flac"]
            elif output_format == "ogg":
                command += ["-vn", "-codec:a", "libvorbis", "-q:a", "5"]
        else:
            if output_format == "mp4":
                command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                ]
            elif output_format == "flv":
                command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                ]
            elif output_format == "mov":
                command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                ]

        command.append(str(output_path))

        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        update_job(job_id, process=process)

        while True:
            if get_job(job_id).get("cancel_requested"):
                process.terminate()

                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

                raise RuntimeError("cancelled")

            line = process.stderr.readline()

            if not line and process.poll() is not None:
                break

        return_code = process.wait()

        if return_code != 0:
            raise RuntimeError("FFmpeg terminó con código de error.")

        if not output_path.exists():
            raise FileNotFoundError("FFmpeg no generó el archivo final.")

        shutil.rmtree(job_dir, ignore_errors=True)

        update_job(
            job_id,
            status="finished",
            progress=100,
            output_path=str(output_path),
            filename=output_path.name,
        )

        push_event(
            job_id,
            {"status": "finished", "progress": 100, "filename": output_path.name},
        )

    except RuntimeError as exc:
        if str(exc) == "cancelled":
            update_job(job_id, status="cancelled")
            shutil.rmtree(job_dir, ignore_errors=True)

            push_event(job_id, {"status": "cancelled", "progress": 0})
        else:
            update_job(job_id, status="error", error=str(exc))
            shutil.rmtree(job_dir, ignore_errors=True)

            push_event(job_id, {"status": "error", "message": str(exc)})

    except Exception as exc:
        update_job(job_id, status="error", error=str(exc))
        shutil.rmtree(job_dir, ignore_errors=True)

        push_event(job_id, {"status": "error", "message": str(exc)})

    finally:
        if cookies_path:
            try:
                Path(cookies_path).unlink(missing_ok=True)
            except Exception:
                pass


def run_jobLocal(
    job_id,
    url,
    media_type,
    output_format,
    filename,
    destination,
    start_time="",
    end_time="",
    cookies_path=None,
):
    # ============================================================
    # CONFIGURACIÓN
    # ============================================================

    YTDLP_PATH = Path(r"C:\ytdlp\yt-dlp.exe")

    job_dir = destination / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ========================================================
        # VERIFICAR YT-DLP
        # ========================================================

        if not YTDLP_PATH.exists():
            raise FileNotFoundError(f"No se encontró yt-dlp en: {YTDLP_PATH}")

        update_job(
            job_id,
            status="downloading",
            progress=0,
        )

        # ========================================================
        # ARCHIVO TEMPORAL
        # ========================================================

        output_template = str(job_dir / "%(title)s.%(ext)s")

        # ========================================================
        # CONSTRUIR COMANDO YT-DLP
        # ========================================================

        command = [
            str(YTDLP_PATH),
            "--no-playlist",
            "--newline",
            "--progress",
            "--restrict-filenames",
            "-o",
            output_template,
        ]

        # ========================================================
        # FORMATO
        # ========================================================

        if media_type == "audio":

            command += [
                "-f",
                "bestaudio/best",
            ]

        else:

            command += [
                "-f",
                "bestvideo*+bestaudio/best",
            ]

        # ========================================================
        # CLIENTE YOUTUBE
        # ========================================================

        command += [
            "--extractor-args",
            "youtube:player_client=default",
        ]

        # ========================================================
        # COOKIES
        # ========================================================

        if cookies_path:

            command += [
                "--cookies",
                str(cookies_path),
            ]

        # ========================================================
        # INTERVALO DE TIEMPO
        # ========================================================

        if start_time or end_time:

            section_start = start_time if start_time else "00:00:00"

            section_end = end_time if end_time else "inf"

            command += [
                "--download-sections",
                f"*{section_start}-{section_end}",
                "--force-keyframes-at-cuts",
            ]

        # ========================================================
        # URL
        # ========================================================

        command.append(url)

        # ========================================================
        # EJECUTAR YT-DLP
        # ========================================================

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        update_job(
            job_id,
            process=process,
        )

        # ========================================================
        # LEER PROGRESO
        # ========================================================

        downloaded_path = None

        for line in process.stdout:

            line = line.strip()

            if not line:
                continue

            # ----------------------------------------------------
            # CANCELACIÓN
            # ----------------------------------------------------

            if get_job(job_id).get("cancel_requested"):

                try:
                    process.terminate()

                    try:
                        process.wait(timeout=5)

                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

                except Exception:
                    pass

                raise RuntimeError("cancelled")

            # ----------------------------------------------------
            # MOSTRAR ERROR
            # ----------------------------------------------------

            if "ERROR:" in line:

                # No lanzamos inmediatamente la excepción porque
                # yt-dlp puede continuar en algunos casos.
                push_event(
                    job_id,
                    {
                        "status": "downloading",
                        "progress": 0,
                        "speed": "",
                        "eta": "",
                        "message": line,
                    },
                )

            # ----------------------------------------------------
            # PROGRESO
            # ----------------------------------------------------

            percent = parse_percent(line)

            speed = parse_speed(line)

            eta = parse_eta(line)
            total_size = parse_total_size(line)
            total_bytes = parse_size_to_bytes(total_size)
            if total_bytes is not None and percent is not None:
                downloaded_bytes = total_bytes * (percent / 100)
                remaining_bytes = total_bytes - downloaded_bytes

            if percent is not None:

                update_job(
                    job_id,
                    progress=percent,
                )

                push_event(
                    job_id,
                    {
                        "status": "downloading",
                        "progress": percent,
                        "speed": speed or "",
                        "eta": eta or "",
                        "total_size": total_size or "",
                        "downloaded_bytes": downloaded_bytes,
                        "remaining_bytes": remaining_bytes,
                    },
                )

            # ----------------------------------------------------
            # ARCHIVO DESCARGADO
            # ----------------------------------------------------

            if "[download] Destination:" in line:

                try:

                    path_text = line.split("[download] Destination:", 1)[1].strip()

                    downloaded_path = Path(path_text)

                except Exception:
                    pass

            # ----------------------------------------------------
            # ARCHIVO YA EXISTENTE / MERGE
            # ----------------------------------------------------

            if "Merging formats into" in line:

                try:

                    path_text = line.split("Merging formats into", 1)[1].strip()

                    path_text = path_text.strip('"')

                    downloaded_path = Path(path_text)

                except Exception:
                    pass

        # ========================================================
        # ESPERAR YT-DLP
        # ========================================================

        return_code = process.wait()

        update_job(
            job_id,
            process=None,
        )

        # ========================================================
        # ERROR DE YT-DLP
        # ========================================================

        if return_code != 0:

            raise RuntimeError("yt-dlp terminó con código de error.")

        # ========================================================
        # BUSCAR ARCHIVO DESCARGADO
        # ========================================================

        if downloaded_path is None or not downloaded_path.exists():

            candidates = [p for p in job_dir.iterdir() if p.is_file()]

            if not candidates:

                raise FileNotFoundError(
                    "yt-dlp terminó correctamente, "
                    "pero no se encontró ningún archivo descargado."
                )

            # Preferir archivos multimedia
            multimedia = [
                p
                for p in candidates
                if p.suffix.lower()
                in {
                    ".mp4",
                    ".webm",
                    ".mkv",
                    ".m4a",
                    ".mp3",
                    ".opus",
                    ".flac",
                    ".ogg",
                    ".wav",
                }
            ]

            if multimedia:
                downloaded_path = multimedia[0]
            else:
                downloaded_path = candidates[0]

        # ========================================================
        # OBTENER NOMBRE
        # ========================================================
        if filename:

            output_name = safe_filename(filename)

        else:

            output_name = safe_filename(downloaded_path.stem)

        if not output_name:

            output_name = "video"

        # ========================================================
        # ARCHIVO FINAL
        # ========================================================

        output_path = destination / f"{output_name}.{output_format}"

        # ========================================================
        # AVISAR QUE COMIENZA CONVERSIÓN
        # ========================================================

        push_event(
            job_id,
            {
                "status": "converting",
                "progress": 100,
                "speed": "",
                "eta": "",
            },
        )

        # ========================================================
        # FFMPEG
        # ========================================================

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-i",
            str(downloaded_path),
        ]

        # ========================================================
        # AUDIO
        # ========================================================

        if media_type == "audio":

            if output_format == "mp3":

                ffmpeg_command += [
                    "-vn",
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                ]

            elif output_format == "flac":

                ffmpeg_command += [
                    "-vn",
                    "-codec:a",
                    "flac",
                ]

            elif output_format == "ogg":

                ffmpeg_command += [
                    "-vn",
                    "-codec:a",
                    "libvorbis",
                    "-q:a",
                    "5",
                ]

        # ========================================================
        # VIDEO
        # ========================================================

        else:

            if output_format == "mp4":

                ffmpeg_command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                ]

            elif output_format == "flv":

                ffmpeg_command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                ]

            elif output_format == "mov":

                ffmpeg_command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                ]

        # ========================================================
        # SALIDA
        # ========================================================

        ffmpeg_command.append(str(output_path))

        # ========================================================
        # EJECUTAR FFMPEG
        # ========================================================

        ffmpeg_process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        update_job(
            job_id,
            process=ffmpeg_process,
        )

        # ========================================================
        # CONTROL DE FFMPEG
        # ========================================================

        while True:

            # ----------------------------------------------------
            # CANCELACIÓN
            # ----------------------------------------------------

            if get_job(job_id).get("cancel_requested"):

                try:

                    ffmpeg_process.terminate()

                    try:

                        ffmpeg_process.wait(timeout=5)

                    except subprocess.TimeoutExpired:

                        ffmpeg_process.kill()

                        ffmpeg_process.wait()

                except Exception:
                    pass

                raise RuntimeError("cancelled")

            # ----------------------------------------------------
            # LEER SALIDA
            # ----------------------------------------------------

            line = ffmpeg_process.stderr.readline()

            if not line and ffmpeg_process.poll() is not None:
                break

        # ========================================================
        # ESPERAR FFMPEG
        # ========================================================

        return_code = ffmpeg_process.wait()

        update_job(
            job_id,
            process=None,
        )

        # ========================================================
        # ERROR
        # ========================================================

        if return_code != 0:

            raise RuntimeError("FFmpeg terminó con código de error.")

        # ========================================================
        # COMPROBAR ARCHIVO
        # ========================================================

        if not output_path.exists():

            raise FileNotFoundError("FFmpeg no generó el archivo final.")

        # ========================================================
        # ELIMINAR TEMPORAL
        # ========================================================

        shutil.rmtree(
            job_dir,
            ignore_errors=True,
        )

        # ========================================================
        # JOB FINALIZADO
        # ========================================================

        update_job(
            job_id,
            status="finished",
            progress=100,
            output_path=str(output_path),
            filename=output_path.name,
        )

        push_event(
            job_id,
            {
                "status": "finished",
                "progress": 100,
                "filename": output_path.name,
            },
        )

    # ============================================================
    # CANCELACIÓN
    # ============================================================

    except RuntimeError as exc:

        if str(exc) == "cancelled":

            update_job(
                job_id,
                status="cancelled",
            )

            shutil.rmtree(
                job_dir,
                ignore_errors=True,
            )

            # Eliminar archivo final parcial
            try:

                if "output_path" in locals():
                    Path(output_path).unlink(missing_ok=True)

            except Exception:
                pass

            push_event(
                job_id,
                {
                    "status": "cancelled",
                    "progress": 0,
                },
            )

        else:

            update_job(
                job_id,
                status="error",
                error=str(exc),
            )

            shutil.rmtree(
                job_dir,
                ignore_errors=True,
            )

            push_event(
                job_id,
                {
                    "status": "error",
                    "message": str(exc),
                },
            )

    # ============================================================
    # OTROS ERRORES
    # ============================================================

    except Exception as exc:

        update_job(
            job_id,
            status="error",
            error=str(exc),
        )

        shutil.rmtree(
            job_dir,
            ignore_errors=True,
        )

        push_event(
            job_id,
            {
                "status": "error",
                "message": str(exc),
            },
        )

    # ============================================================
    # LIMPIAR COOKIES
    # ============================================================

    finally:

        if cookies_path:

            try:

                Path(cookies_path).unlink(missing_ok=True)

            except Exception:
                pass


def run_jobLocal_time(
    job_id,
    url,
    media_type,
    output_format,
    filename,
    destination,
    start_time="",
    end_time="",
    cookies_path=None,
):
    """
    Descarga un archivo cuando se especificó un intervalo de tiempo.

    Flujo:

        yt-dlp
           ↓
        archivo temporal completo
           ↓
        FFmpeg
           ↓
        archivo final recortado

    El progreso de yt-dlp se muestra durante la descarga.
    El progreso de FFmpeg se muestra durante el recorte.
    """

    YTDLP_PATH = Path(r"C:\ytdlp\yt-dlp.exe")

    job_dir = destination / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    downloaded_path = None
    cookies_temp = cookies_path

    try:

        # ========================================================
        # VERIFICAR YT-DLP
        # ========================================================

        if not YTDLP_PATH.exists():
            raise FileNotFoundError(f"No se encontró yt-dlp en: {YTDLP_PATH}")

        # ========================================================
        # ESTADO INICIAL
        # ========================================================

        update_job(
            job_id,
            status="downloading",
            progress=0,
        )

        # ========================================================
        # ARCHIVO TEMPORAL
        # ========================================================

        output_template = str(job_dir / "%(title)s.%(ext)s")

        # ========================================================
        # COMANDO YT-DLP
        # ========================================================

        command = [
            str(YTDLP_PATH),
            "--no-playlist",
            "--newline",
            "--progress",
            "--restrict-filenames",
            "-o",
            output_template,
        ]

        # ========================================================
        # FORMATO
        # ========================================================

        if media_type == "audio":

            command += [
                "-f",
                "bestaudio/best",
            ]

        else:

            command += [
                "-f",
                "bestvideo*+bestaudio/best",
            ]

        # ========================================================
        # YOUTUBE
        # ========================================================

        command += [
            "--extractor-args",
            "youtube:player_client=default",
        ]

        # ========================================================
        # COOKIES
        # ========================================================

        if cookies_temp:

            command += [
                "--cookies",
                str(cookies_temp),
            ]

        # ========================================================
        # IMPORTANTE
        #
        # ACÁ NO USAMOS --download-sections
        #
        # Descargamos primero el archivo completo.
        # Después FFmpeg realiza el corte.
        # ========================================================

        command.append(url)

        print("")
        print("==========================================")
        print("YT-DLP CON INTERVALO")
        print("==========================================")
        print("INICIO:", start_time)
        print("FINAL :", end_time)
        print("COMANDO:")
        print(command)
        print("==========================================")
        print("")

        # ========================================================
        # EJECUTAR YT-DLP
        # ========================================================

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        update_job(
            job_id,
            process=process,
        )

        # ========================================================
        # LEER PROGRESO DE YT-DLP
        # ========================================================

        for line in process.stdout:

            line = line.strip()

            if not line:
                continue

            print("YT-DLP:", line)

            # ----------------------------------------------------
            # CANCELACIÓN
            # ----------------------------------------------------

            if get_job(job_id).get("cancel_requested"):

                try:
                    process.terminate()

                    try:
                        process.wait(timeout=5)

                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

                except Exception:
                    pass

                raise RuntimeError("cancelled")

            # ----------------------------------------------------
            # PROGRESO
            # ----------------------------------------------------

            percent = parse_percent(line)
            speed = parse_speed(line)
            eta = parse_eta(line)
            total_size = parse_total_size(line)
            total_bytes = parse_size_to_bytes(total_size)
            if total_bytes is not None and percent is not None:
                downloaded_bytes = total_bytes * (percent / 100)
                remaining_bytes = total_bytes - downloaded_bytes

            if percent is not None:

                update_job(
                    job_id,
                    progress=percent,
                )

                push_event(
                    job_id,
                    {
                        "status": "downloading",
                        "progress": percent,
                        "speed": speed or "",
                        "eta": eta or "",
                        "total_size": total_size or "",
                        "downloaded_bytes": downloaded_bytes,
                        "remaining_bytes": remaining_bytes,
                    },
                )

        # ========================================================
        # ESPERAR YT-DLP
        # ========================================================

        return_code = process.wait()

        update_job(
            job_id,
            process=None,
        )

        if return_code != 0:

            raise RuntimeError("yt-dlp terminó con código de error.")

        # ========================================================
        # BUSCAR ARCHIVO DESCARGADO
        # ========================================================

        candidates = [p for p in job_dir.iterdir() if p.is_file()]

        if not candidates:

            raise FileNotFoundError(
                "yt-dlp terminó correctamente, "
                "pero no se encontró el archivo descargado."
            )

        multimedia = [
            p
            for p in candidates
            if p.suffix.lower()
            in {
                ".mp4",
                ".webm",
                ".mkv",
                ".m4a",
                ".mp3",
                ".opus",
                ".flac",
                ".ogg",
                ".wav",
            }
        ]

        if multimedia:

            downloaded_path = multimedia[0]

        else:

            downloaded_path = candidates[0]

        print("ARCHIVO DESCARGADO:")
        print(downloaded_path)

        # ========================================================
        # NOMBRE FINAL
        # ========================================================

        if filename:

            output_name = safe_filename(filename)

        else:

            output_name = safe_filename(downloaded_path.stem)

        if not output_name:

            output_name = "video"

        output_path = destination / f"{output_name}.{output_format}"

        # ========================================================
        # DURACIÓN DEL INTERVALO
        # ========================================================

        start_seconds = time_to_seconds(start_time) if start_time else 0

        if end_time:

            end_seconds = time_to_seconds(end_time)

            duration_seconds = end_seconds - start_seconds

        else:

            # Si no hay final, necesitamos obtener
            # la duración del archivo.
            duration_seconds = get_media_duration(downloaded_path)

            duration_seconds -= start_seconds

        if duration_seconds <= 0:

            raise ValueError("La duración del intervalo no es válida.")

        print("DURACIÓN DEL INTERVALO:")
        print(duration_seconds)

        # ========================================================
        # AVISAR AL FRONTEND
        # ========================================================

        push_event(
            job_id,
            {
                "status": "converting",
                "progress": 0,
                "speed": "",
                "eta": "",
            },
        )

        # ========================================================
        # FFMPEG
        # ========================================================

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-ss",
            start_time if start_time else "00:00:00",
            "-i",
            str(downloaded_path),
        ]

        # ========================================================
        # DURACIÓN DEL CORTE
        # ========================================================

        ffmpeg_command += [
            "-t",
            format_seconds(duration_seconds),
        ]

        # ========================================================
        # AUDIO
        # ========================================================

        if media_type == "audio":

            if output_format == "mp3":

                ffmpeg_command += [
                    "-vn",
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                ]

            elif output_format == "flac":

                ffmpeg_command += [
                    "-vn",
                    "-codec:a",
                    "flac",
                ]

            elif output_format == "ogg":

                ffmpeg_command += [
                    "-vn",
                    "-codec:a",
                    "libvorbis",
                    "-q:a",
                    "5",
                ]

        # ========================================================
        # VIDEO
        # ========================================================

        else:

            if output_format == "mp4":

                ffmpeg_command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                ]

            elif output_format == "flv":

                ffmpeg_command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                ]

            elif output_format == "mov":

                ffmpeg_command += [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                ]

        # ========================================================
        # ARCHIVO SALIDA
        # ========================================================

        ffmpeg_command += [str(output_path)]

        # ========================================================
        # PROGRESO FFMPEG
        # ========================================================

        ffmpeg_command += [
            "-progress",
            "pipe:1",
            "-nostats",
        ]

        print("")
        print("==========================================")
        print("FFMPEG")
        print("==========================================")
        print(ffmpeg_command)
        print("==========================================")
        print("")

        process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        update_job(
            job_id,
            process=process,
        )

        # ========================================================
        # LEER PROGRESO FFMPEG
        # ========================================================

        current_seconds = 0

        for line in process.stdout:

            line = line.strip()

            if not line:
                continue

            print("FFMPEG:", line)

            # ----------------------------------------------------
            # CANCELACIÓN
            # ----------------------------------------------------

            if get_job(job_id).get("cancel_requested"):

                try:

                    process.terminate()

                    try:
                        process.wait(timeout=5)

                    except subprocess.TimeoutExpired:

                        process.kill()
                        process.wait()

                except Exception:
                    pass

                raise RuntimeError("cancelled")

            # ----------------------------------------------------
            # TIEMPO PROCESADO
            # ----------------------------------------------------

            if line.startswith("out_time_us="):

                try:

                    current_seconds = int(line.split("=", 1)[1]) / 1_000_000

                except ValueError:

                    continue

                progress = (current_seconds / duration_seconds) * 100

                progress = max(0, min(100, progress))

                update_job(
                    job_id,
                    progress=progress,
                )

                push_event(
                    job_id,
                    {
                        "status": "converting",
                        "progress": progress,
                        "speed": "",
                        "eta": "",
                    },
                )

        # ========================================================
        # ESPERAR FFMPEG
        # ========================================================

        return_code = process.wait()

        update_job(
            job_id,
            process=None,
        )

        if return_code != 0:

            raise RuntimeError("FFmpeg terminó con código de error.")

        # ========================================================
        # VERIFICAR ARCHIVO
        # ========================================================

        if not output_path.exists():

            raise FileNotFoundError("FFmpeg no generó el archivo final.")

        # ========================================================
        # ELIMINAR TEMPORAL
        # ========================================================

        try:

            downloaded_path.unlink(missing_ok=True)

        except Exception:

            pass

        # ========================================================
        # ELIMINAR DIRECTORIO TEMPORAL
        # ========================================================

        try:

            job_dir.rmdir()

        except Exception:

            pass

        # ========================================================
        # FINALIZADO
        # ========================================================

        update_job(
            job_id,
            status="finished",
            progress=100,
            output_path=str(output_path),
            filename=output_path.name,
        )

        push_event(
            job_id,
            {
                "status": "finished",
                "progress": 100,
                "filename": output_path.name,
            },
        )

    except RuntimeError as exc:

        if str(exc) == "cancelled":

            update_job(
                job_id,
                status="cancelled",
            )

            shutil.rmtree(
                job_dir,
                ignore_errors=True,
            )

            push_event(
                job_id,
                {
                    "status": "cancelled",
                    "progress": 0,
                },
            )

        else:

            update_job(
                job_id,
                status="error",
                error=str(exc),
            )

            shutil.rmtree(
                job_dir,
                ignore_errors=True,
            )

            push_event(
                job_id,
                {
                    "status": "error",
                    "message": str(exc),
                },
            )

    except Exception as exc:

        update_job(
            job_id,
            status="error",
            error=str(exc),
        )

        shutil.rmtree(
            job_dir,
            ignore_errors=True,
        )

        push_event(
            job_id,
            {
                "status": "error",
                "message": str(exc),
            },
        )

    finally:

        if cookies_path:

            try:

                Path(cookies_path).unlink(missing_ok=True)

            except Exception:

                pass


def parse_total_size(line):
    match = re.search(r"\bof\s+([\d.]+\s*[KMGTP]?i?B)", line, re.IGNORECASE)

    return match.group(1) if match else None


def parse_size_to_bytes(size_text):
    if not size_text:
        return None

    match = re.match(r"([\d.]+)\s*([KMGTP]?i?B)", size_text, re.IGNORECASE)

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).lower()

    units = {
        "b": 1,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
    }

    multiplier = units.get(unit)

    if multiplier is None:
        return None

    return value * multiplier


@app.get("/")
def index():
    return jsonify({"service": "Media Downloader", "status": "online"})


# @app.get("/health")
# def health():
#     return jsonify({"status": "ok"})


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "music-downloader",
            "version": "1.0",
            "server": "rifz",
        }
    )


# @app.post("/download")
# def start_download():
#     # El endpoint utiliza multipart/form-data porque puede recibir
#     # opcionalmente un archivo cookies.txt.
#     data = request.form

#     url = (data.get("url") or "").strip()
#     media_type = (data.get("type") or "").lower()
#     output_format = (data.get("format") or "").lower()
#     filename = safe_filename(data.get("filename"))
#     destination_value = data.get("destination") or "downloads"
#     cookies_upload = request.form.get("cookies")

#     try:
#         start_time = normalize_time(data.get("start_time"))
#         end_time = normalize_time(data.get("end_time"))
#     except ValueError as exc:
#         return jsonify({"error": str(exc)}), 400

#     try:
#         cookies_upload = validate_cookies_file(cookies_upload)
#     except ValueError as exc:
#         return jsonify({"error": str(exc)}), 400

#     if start_time and end_time:
#         if time_to_seconds(end_time) <= time_to_seconds(start_time):
#             return (
#                 jsonify(
#                     {"error": "El tiempo final debe ser mayor que el tiempo de inicio."}
#                 ),
#                 400,
#             )

#     if not url:
#         return jsonify({"error": "La URL es obligatoria."}), 400

#     if media_type not in ALLOWED_TYPES:
#         return jsonify({"error": "Tipo de salida inválido."}), 400

#     allowed = AUDIO_FORMATS if media_type == "audio" else VIDEO_FORMATS

#     if output_format not in allowed:
#         return jsonify({"error": "Formato de salida inválido."}), 400

#     try:
#         destination = safe_destination(destination_value)
#     except ValueError as exc:
#         return jsonify({"error": str(exc)}), 400

#     job_id = uuid.uuid4().hex

#     cookies_path = None

#     if cookies_upload:
#         cookie_dir = destination / ".cookies"
#         cookie_dir.mkdir(parents=True, exist_ok=True)

#         cookies_path = cookie_dir / f"{job_id}.txt"

#         try:
#             cookies_upload.save(cookies_path)

#             # Validación básica del formato Netscape/Mozilla.
#             content_start = cookies_path.read_text(encoding="utf-8", errors="replace")[
#                 :100
#             ]

#             if not (
#                 content_start.startswith("# HTTP Cookie File")
#                 or content_start.startswith("# Netscape HTTP Cookie File")
#             ):
#                 cookies_path.unlink(missing_ok=True)
#                 return (
#                     jsonify(
#                         {
#                             "error": "El cookies.txt no parece estar en formato Netscape/Mozilla."
#                         }
#                     ),
#                     400,
#                 )

#         except Exception as exc:
#             if cookies_path:
#                 cookies_path.unlink(missing_ok=True)
#             return (
#                 jsonify({"error": f"No se pudo guardar el archivo de cookies: {exc}"}),
#                 500,
#             )

#     with jobs_lock:
#         jobs[job_id] = {
#             "status": "queued",
#             "progress": 0,
#             "queue": Queue(),
#             "process": None,
#             "cancel_requested": False,
#             "output_path": None,
#             "filename": None,
#         }

#     thread = threading.Thread(
#         target=run_job,
#         args=(
#             job_id,
#             url,
#             media_type,
#             output_format,
#             filename,
#             destination,
#             start_time,
#             end_time,
#             str(cookies_path) if cookies_path else None,
#         ),
#         daemon=True,
#     )

#     thread.start()

#     return jsonify({"job_id": job_id})


@app.post("/downloadLocal")
def start_download_Local():
    # ============================================================
    # CONFIGURACIÓN DE YT-DLP LOCAL
    # ============================================================

    YTDLP_PATH = Path(r"C:\ytdlp\yt-dlp.exe")

    if not YTDLP_PATH.exists():
        return jsonify({"error": f"No se encontró yt-dlp en: {YTDLP_PATH}"}), 500

    # ============================================================
    # DATOS DEL FORMULARIO
    # ============================================================

    data = request.form

    url = (data.get("url") or "").strip()
    media_type = (data.get("type") or "").lower()
    output_format = (data.get("format") or "").lower()

    filename = safe_filename(data.get("filename"))

    destination_value = data.get("destination") or "downloads"

    # ============================================================
    # COOKIES
    # ============================================================

    cookies_json = (data.get("cookies") or "").strip()

    # ============================================================
    # TIEMPOS
    # ============================================================

    try:
        start_time = normalize_time(data.get("start_time"))
        end_time = normalize_time(data.get("end_time"))

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if start_time and end_time:

        if time_to_seconds(end_time) <= time_to_seconds(start_time):

            return (
                jsonify(
                    {
                        "error": (
                            "El tiempo final debe ser mayor " "que el tiempo de inicio."
                        )
                    }
                ),
                400,
            )

    # ============================================================
    # VALIDACIONES
    # ============================================================

    if not url:
        return jsonify({"error": "La URL es obligatoria."}), 400

    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": "Tipo de salida inválido."}), 400

    allowed = AUDIO_FORMATS if media_type == "audio" else VIDEO_FORMATS

    if output_format not in allowed:
        return jsonify({"error": "Formato de salida inválido."}), 400

    # ============================================================
    # DESTINO
    # ============================================================

    try:

        destination = safe_destination2(destination_value)

    except ValueError as exc:

        return jsonify({"error": str(exc)}), 400

    # ============================================================
    # VALIDACIÓN DE COOKIES
    # ============================================================

    if cookies_json:

        hostname = (urlparse(url).hostname or "").lower()

        es_youtube = (
            hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
            or hostname == "youtu.be"
        )

        if not es_youtube:

            return (
                jsonify(
                    {
                        "error": (
                            "Las cookies de YouTube solamente "
                            "pueden utilizarse con URLs de YouTube."
                        )
                    }
                ),
                400,
            )

        # Verificar JSON

        try:

            json.loads(cookies_json)

        except json.JSONDecodeError as exc:

            return jsonify({"error": (f"El JSON de cookies no es válido: {exc}")}), 400

    # ============================================================
    # CREAR JOB
    # ============================================================

    job_id = uuid.uuid4().hex

    cookies_path = None

    # ============================================================
    # CONVERTIR COOKIES JSON -> NETSCAPE
    # ============================================================

    if cookies_json:

        cookie_dir = destination / ".cookies"

        cookie_dir.mkdir(parents=True, exist_ok=True)

        cookies_path = cookie_dir / f"{job_id}.txt"

        try:

            cantidad = cookies_json_to_netscape(cookies_json, cookies_path)

            if cantidad == 0:

                cookies_path.unlink(missing_ok=True)

                return (
                    jsonify(
                        {
                            "error": (
                                "No se encontraron cookies " "válidas dentro del JSON."
                            )
                        }
                    ),
                    400,
                )

        except ValueError as exc:

            cookies_path.unlink(missing_ok=True)

            return jsonify({"error": str(exc)}), 400

        except Exception as exc:

            cookies_path.unlink(missing_ok=True)

            return (
                jsonify({"error": ("No se pudieron procesar " f"las cookies: {exc}")}),
                500,
            )

    # ============================================================
    # CREAR JOB EN MEMORIA
    # ============================================================

    with jobs_lock:

        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "queue": Queue(),
            "process": None,
            "cancel_requested": False,
            "output_path": None,
            "filename": None,
            # Ruta de yt-dlp local
            "ytdlp_path": str(YTDLP_PATH),
        }

    # ============================================================
    # INICIAR THREAD
    # ============================================================
    if start_time or end_time:
        worker = run_jobLocal_time
    else:
        worker = run_jobLocal

    thread = threading.Thread(
        target=worker,
        args=(
            job_id,
            url,
            media_type,
            output_format,
            filename,
            destination,
            start_time,
            end_time,
            str(cookies_path) if cookies_path else None,
        ),
        daemon=True,
    )

    thread.start()

    # ============================================================
    # RESPUESTA
    # ============================================================

    return jsonify({"job_id": job_id})


@app.post("/download")
def start_download():
    # Los datos llegan como multipart/form-data porque el frontend
    # utiliza FormData. Las cookies ahora llegan como TEXTO JSON,
    # no como archivo.
    data = request.form

    url = (data.get("url") or "").strip()
    media_type = (data.get("type") or "").lower()
    output_format = (data.get("format") or "").lower()
    filename = safe_filename(data.get("filename"))
    destination_value = data.get("destination") or "downloads"

    # ============================================================
    # COOKIES DESDE EL TEXTAREA
    # ============================================================

    cookies_json = (data.get("cookies") or "").strip()

    # ============================================================
    # TIEMPOS
    # ============================================================

    try:
        start_time = normalize_time(data.get("start_time"))
        end_time = normalize_time(data.get("end_time"))

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if start_time and end_time:
        if time_to_seconds(end_time) <= time_to_seconds(start_time):
            return (
                jsonify(
                    {
                        "error": (
                            "El tiempo final debe ser mayor " "que el tiempo de inicio."
                        )
                    }
                ),
                400,
            )

    # ============================================================
    # VALIDACIONES
    # ============================================================

    if not url:
        return jsonify({"error": "La URL es obligatoria."}), 400

    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": "Tipo de salida inválido."}), 400

    allowed = AUDIO_FORMATS if media_type == "audio" else VIDEO_FORMATS

    if output_format not in allowed:
        return jsonify({"error": "Formato de salida inválido."}), 400

    # ============================================================
    # DESTINO
    # ============================================================

    try:
        destination = safe_destination2(destination_value)

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # ============================================================
    # VALIDACIÓN DE COOKIES
    # ============================================================

    if cookies_json:

        # Las cookies solamente se permiten para YouTube.
        hostname = (urlparse(url).hostname or "").lower()

        es_youtube = (
            hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
            or hostname == "youtu.be"
        )

        if not es_youtube:
            return (
                jsonify(
                    {
                        "error": (
                            "Las cookies de YouTube solamente pueden "
                            "utilizarse con URLs de YouTube."
                        )
                    }
                ),
                400,
            )

        # Verificar que realmente sea JSON antes de crear el job.
        try:
            json.loads(cookies_json)

        except json.JSONDecodeError as exc:
            return jsonify({"error": f"El JSON de cookies no es válido: {exc}"}), 400

    # ============================================================
    # CREAR JOB
    # ============================================================

    job_id = uuid.uuid4().hex

    # Este archivo NO viene del usuario.
    #
    # Se genera temporalmente en el servidor para que yt-dlp
    # pueda utilizar las cookies.
    cookies_path = None

    # ============================================================
    # CONVERTIR JSON -> NETSCAPE
    # ============================================================

    if cookies_json:

        cookie_dir = destination / ".cookies"
        cookie_dir.mkdir(parents=True, exist_ok=True)

        cookies_path = cookie_dir / f"{job_id}.txt"

        try:
            cantidad = cookies_json_to_netscape(cookies_json, cookies_path)

            if cantidad == 0:
                cookies_path.unlink(missing_ok=True)

                return (
                    jsonify(
                        {
                            "error": (
                                "No se encontraron cookies válidas " "dentro del JSON."
                            )
                        }
                    ),
                    400,
                )

        except ValueError as exc:

            cookies_path.unlink(missing_ok=True)

            return jsonify({"error": str(exc)}), 400

        except Exception as exc:

            cookies_path.unlink(missing_ok=True)

            return (
                jsonify({"error": ("No se pudieron procesar las cookies: " f"{exc}")}),
                500,
            )

    # ============================================================
    # CREAR ESTRUCTURA DEL JOB
    # ============================================================

    with jobs_lock:

        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "queue": Queue(),
            "process": None,
            "cancel_requested": False,
            "output_path": None,
            "filename": None,
        }

    # ============================================================
    # INICIAR DESCARGA
    # ============================================================

    thread = threading.Thread(
        target=run_job,
        args=(
            job_id,
            url,
            media_type,
            output_format,
            filename,
            destination,
            start_time,
            end_time,
            # Acá se pasa el archivo temporal generado
            # a partir del textarea.
            str(cookies_path) if cookies_path else None,
        ),
        daemon=True,
    )

    thread.start()

    return jsonify({"job_id": job_id})


@app.get("/progress/<job_id>")
def progress(job_id):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Trabajo no encontrado."}), 404

    def generate():
        queue = job["queue"]

        while True:
            try:
                data = queue.get(timeout=20)
                yield f"data: {json.dumps(data)}\n\n"

                if data.get("status") in {"finished", "error", "cancelled"}:
                    break

            except Empty:
                yield ": keep-alive\n\n"

                current = get_job(job_id)

                if current.get("status") in {"finished", "error", "cancelled"}:
                    break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/cancel/<job_id>")
def cancel_download(job_id):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Trabajo no encontrado."}), 404

    update_job(job_id, cancel_requested=True)

    process = job.get("process")

    if process and process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass

    return jsonify({"status": "cancelling"})


@app.get("/download/<job_id>")
def download_file(job_id):
    job = get_job(job_id)

    if not job:
        return jsonify({"error": "Trabajo no encontrado."}), 404

    if job.get("status") != "finished":
        return jsonify({"error": "El archivo todavía no está listo."}), 409

    output_path = Path(job["output_path"])

    if not output_path.exists():
        return jsonify({"error": "El archivo ya no existe en el servidor."}), 404

    return send_file(
        output_path,
        as_attachment=True,
        download_name=job.get("filename") or output_path.name,
    )


def cookies_json_to_netscape(cookies_json, output_path):
    data = json.loads(cookies_json)

    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated temporarily by Media Downloader",
        "",
    ]

    def process_cookie(cookie):
        domain = cookie.get("domain", "")
        path = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        expiration = cookie.get("expirationDate", 0)

        try:
            expiration = int(float(expiration))
        except (ValueError, TypeError):
            expiration = 0

        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"

        lines.append(
            "\t".join(
                [domain, include_subdomains, path, secure, str(expiration), name, value]
            )
        )

    def walk(obj):
        if isinstance(obj, dict):

            # Cookie individual
            if "name" in obj and "value" in obj and "domain" in obj:
                process_cookie(obj)
                return

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
