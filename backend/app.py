# import os
# import re
# import uuid
# import json
# import shutil
# import threading
# import subprocess
# from pathlib import Path
# from queue import Queue, Empty

# from flask import Flask, request, jsonify, Response, send_file
# from flask_cors import CORS
# import yt_dlp


# BASE_DIR = Path(__file__).resolve().parent
# DOWNLOAD_ROOT = BASE_DIR / "downloads"
# DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# app = Flask(__name__)
# CORS(app)

# jobs = {}
# jobs_lock = threading.Lock()

# AUDIO_FORMATS = {"mp3", "flac", "ogg"}
# VIDEO_FORMATS = {"mp4", "flv", "mov"}
# ALLOWED_TYPES = {"audio", "video"}


# def safe_filename(name: str) -> str:
#     name = (name or "").strip()

#     if not name:
#         return ""

#     name = Path(name).stem
#     name = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1f]', "_", name)
#     name = name.strip(" .")

#     return name[:180]


# def normalize_time(value: str) -> str:
#     """
#     Valida HH:MM:SS o H:MM:SS.
#     Devuelve siempre HH:MM:SS.
#     """
#     value = (value or "").strip()

#     if not value:
#         return ""

#     match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})", value)

#     if not match:
#         raise ValueError("Los tiempos deben utilizar el formato HH:MM:SS.")

#     hours, minutes, seconds = map(int, match.groups())

#     if minutes > 59 or seconds > 59:
#         raise ValueError("Minutos y segundos deben estar entre 00 y 59.")

#     return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# def time_to_seconds(value: str) -> int:
#     hours, minutes, seconds = map(int, value.split(":"))
#     return hours * 3600 + minutes * 60 + seconds


# def safe_destination(destination: str) -> Path:
#     """
#     Evita que el usuario pueda escribir fuera de DOWNLOAD_ROOT.
#     La ruta enviada por el frontend es relativa al directorio downloads.
#     """
#     destination = (destination or "downloads").strip()

#     destination = destination.replace("\\", "/")
#     destination = destination.lstrip("/")

#     parts = [
#         part for part in Path(destination).parts
#         if part not in ("", ".", "..")
#     ]

#     relative = Path(*parts) if parts else Path()

#     final = (DOWNLOAD_ROOT / relative).resolve()

#     if DOWNLOAD_ROOT.resolve() not in final.parents and final != DOWNLOAD_ROOT.resolve():
#         raise ValueError("Ruta de destino no permitida.")

#     final.mkdir(parents=True, exist_ok=True)
#     return final


# def update_job(job_id, **values):
#     with jobs_lock:
#         if job_id in jobs:
#             jobs[job_id].update(values)


# def get_job(job_id):
#     with jobs_lock:
#         return dict(jobs.get(job_id, {}))


# def push_event(job_id, data):
#     with jobs_lock:
#         job = jobs.get(job_id)

#     if job:
#         job["queue"].put(data)


# def parse_percent(line):
#     match = re.search(r"(\d+(?:\.\d+)?)%", line)
#     return float(match.group(1)) if match else None


# def parse_speed(line):
#     match = re.search(r"at\\s+([\\d.]+\\s*[KMG]?iB/s)", line)
#     return match.group(1) if match else None


# def parse_eta(line):
#     match = re.search(r"ETA\\s+([0-9:]+)", line)
#     return match.group(1) if match else None


# def run_job(
#     job_id,
#     url,
#     media_type,
#     output_format,
#     filename,
#     destination,
#     start_time="",
#     end_time=""
# ):
#     job_dir = destination / job_id
#     job_dir.mkdir(parents=True, exist_ok=True)

#     try:
#         update_job(job_id, status="downloading")

#         output_template = str(job_dir / "%(title)s.%(ext)s")

#         def progress_hook(data):
#             status = data.get("status")

#             if status == "downloading":
#                 total = data.get("total_bytes") or data.get("total_bytes_estimate")
#                 downloaded = data.get("downloaded_bytes", 0)

#                 percent = (downloaded / total * 100) if total else 0

#                 speed = data.get("_speed_str") or ""
#                 eta = data.get("_eta_str") or ""

#                 update_job(job_id, progress=percent)

#                 push_event(job_id, {
#                     "status": "downloading",
#                     "progress": percent,
#                     "speed": speed,
#                     "eta": eta
#                 })

#             elif status == "finished":
#                 update_job(job_id, progress=100)

#                 push_event(job_id, {
#                     "status": "converting",
#                     "progress": 100,
#                     "speed": "",
#                     "eta": ""
#                 })

#         ydl_opts = {
#             "outtmpl": output_template,
#             "progress_hooks": [progress_hook],
#             "noplaylist": True,
#             "quiet": True,
#             "no_warnings": True,
#             "restrictfilenames": True,
#         }

#         # Si se indicó un intervalo, utiliza el equivalente de:
#         # --download-sections "*00:10:01-00:15:23"
#         if start_time or end_time:
#             section_start = start_time or "00:00:00"
#             section_end = end_time or "inf"
#             ydl_opts["download_sections"] = [
#                 f"*{section_start}-{section_end}"
#             ]
#             ydl_opts["force_keyframes_at_cuts"] = True

#         if media_type == "audio":
#             ydl_opts["format"] = "bestaudio/best"
#         else:
#             ydl_opts["format"] = "bestvideo+bestaudio/best"

#         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#             info = ydl.extract_info(url, download=True)
#             downloaded_path = Path(ydl.prepare_filename(info))

#         if not downloaded_path.exists():
#             candidates = list(job_dir.iterdir())
#             if not candidates:
#                 raise FileNotFoundError("yt-dlp no generó ningún archivo.")
#             downloaded_path = candidates[0]

#         output_name = filename or safe_filename(info.get("title")) or "video"
#         output_path = destination / f"{output_name}.{output_format}"

#         push_event(job_id, {
#             "status": "converting",
#             "progress": 100,
#             "speed": "",
#             "eta": ""
#         })

#         command = [
#             "ffmpeg",
#             "-y",
#             "-i", str(downloaded_path)
#         ]

#         if media_type == "audio":
#             if output_format == "mp3":
#                 command += ["-vn", "-codec:a", "libmp3lame", "-q:a", "2"]
#             elif output_format == "flac":
#                 command += ["-vn", "-codec:a", "flac"]
#             elif output_format == "ogg":
#                 command += ["-vn", "-codec:a", "libvorbis", "-q:a", "5"]
#         else:
#             if output_format == "mp4":
#                 command += [
#                     "-c:v", "libx264",
#                     "-preset", "veryfast",
#                     "-crf", "23",
#                     "-c:a", "aac",
#                     "-movflags", "+faststart"
#                 ]
#             elif output_format == "flv":
#                 command += [
#                     "-c:v", "libx264",
#                     "-preset", "veryfast",
#                     "-crf", "23",
#                     "-c:a", "aac"
#                 ]
#             elif output_format == "mov":
#                 command += [
#                     "-c:v", "libx264",
#                     "-preset", "veryfast",
#                     "-crf", "23",
#                     "-c:a", "aac"
#                 ]

#         command.append(str(output_path))

#         process = subprocess.Popen(
#             command,
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding="utf-8",
#             errors="replace"
#         )

#         update_job(job_id, process=process)

#         while True:
#             if get_job(job_id).get("cancel_requested"):
#                 process.terminate()

#                 try:
#                     process.wait(timeout=5)
#                 except subprocess.TimeoutExpired:
#                     process.kill()

#                 raise RuntimeError("cancelled")

#             line = process.stderr.readline()

#             if not line and process.poll() is not None:
#                 break

#         return_code = process.wait()

#         if return_code != 0:
#             raise RuntimeError("FFmpeg terminó con código de error.")

#         if not output_path.exists():
#             raise FileNotFoundError("FFmpeg no generó el archivo final.")

#         shutil.rmtree(job_dir, ignore_errors=True)

#         update_job(
#             job_id,
#             status="finished",
#             progress=100,
#             output_path=str(output_path),
#             filename=output_path.name
#         )

#         push_event(job_id, {
#             "status": "finished",
#             "progress": 100,
#             "filename": output_path.name
#         })

#     except RuntimeError as exc:
#         if str(exc) == "cancelled":
#             update_job(job_id, status="cancelled")
#             shutil.rmtree(job_dir, ignore_errors=True)

#             push_event(job_id, {
#                 "status": "cancelled",
#                 "progress": 0
#             })
#         else:
#             update_job(job_id, status="error", error=str(exc))
#             shutil.rmtree(job_dir, ignore_errors=True)

#             push_event(job_id, {
#                 "status": "error",
#                 "message": str(exc)
#             })

#     except Exception as exc:
#         update_job(job_id, status="error", error=str(exc))
#         shutil.rmtree(job_dir, ignore_errors=True)

#         push_event(job_id, {
#             "status": "error",
#             "message": str(exc)
#         })


# @app.get("/")
# def index():
#     return jsonify({
#         "service": "Media Downloader",
#         "status": "online"
#     })


# @app.get("/health")
# def health():
#     return jsonify({"status": "ok"})


# @app.post("/download")
# def start_download():
#     data = request.get_json(silent=True) or {}

#     url = (data.get("url") or "").strip()
#     media_type = (data.get("type") or "").lower()
#     output_format = (data.get("format") or "").lower()
#     filename = safe_filename(data.get("filename"))
#     destination_value = data.get("destination") or "downloads"

#     try:
#         start_time = normalize_time(data.get("start_time"))
#         end_time = normalize_time(data.get("end_time"))
#     except ValueError as exc:
#         return jsonify({"error": str(exc)}), 400

#     if start_time and end_time:
#         if time_to_seconds(end_time) <= time_to_seconds(start_time):
#             return jsonify({
#                 "error": "El tiempo final debe ser mayor que el tiempo de inicio."
#             }), 400

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

#     with jobs_lock:
#         jobs[job_id] = {
#             "status": "queued",
#             "progress": 0,
#             "queue": Queue(),
#             "process": None,
#             "cancel_requested": False,
#             "output_path": None,
#             "filename": None
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
#             end_time
#         ),
#         daemon=True
#     )

#     thread.start()

#     return jsonify({
#         "job_id": job_id
#     })


# @app.get("/progress/<job_id>")
# def progress(job_id):
#     with jobs_lock:
#         job = jobs.get(job_id)

#     if not job:
#         return jsonify({"error": "Trabajo no encontrado."}), 404

#     def generate():
#         queue = job["queue"]

#         while True:
#             try:
#                 data = queue.get(timeout=20)
#                 yield f"data: {json.dumps(data)}\n\n"

#                 if data.get("status") in {
#                     "finished",
#                     "error",
#                     "cancelled"
#                 }:
#                     break

#             except Empty:
#                 yield ": keep-alive\n\n"

#                 current = get_job(job_id)

#                 if current.get("status") in {
#                     "finished",
#                     "error",
#                     "cancelled"
#                 }:
#                     break

#     return Response(
#         generate(),
#         mimetype="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no"
#         }
#     )


# @app.post("/cancel/<job_id>")
# def cancel_download(job_id):
#     with jobs_lock:
#         job = jobs.get(job_id)

#     if not job:
#         return jsonify({"error": "Trabajo no encontrado."}), 404

#     update_job(job_id, cancel_requested=True)

#     process = job.get("process")

#     if process and process.poll() is None:
#         try:
#             process.terminate()
#         except Exception:
#             pass

#     return jsonify({"status": "cancelling"})


# @app.get("/download/<job_id>")
# def download_file(job_id):
#     job = get_job(job_id)

#     if not job:
#         return jsonify({"error": "Trabajo no encontrado."}), 404

#     if job.get("status") != "finished":
#         return jsonify({"error": "El archivo todavía no está listo."}), 409

#     output_path = Path(job["output_path"])

#     if not output_path.exists():
#         return jsonify({"error": "El archivo ya no existe en el servidor."}), 404

#     return send_file(
#         output_path,
#         as_attachment=True,
#         download_name=job.get("filename") or output_path.name
#     )


# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5000))
#     app.run(host="0.0.0.0", port=port, threaded=True)

import os
import re
import uuid
import json
import shutil
import threading
import subprocess
from pathlib import Path
from queue import Queue, Empty
from urllib.parse import urlparse

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_ROOT = BASE_DIR / "downloads"
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
CORS(app)

jobs = {}
jobs_lock = threading.Lock()

AUDIO_FORMATS = {"mp3", "flac", "ogg"}
VIDEO_FORMATS = {"mp4", "flv", "mov"}
ALLOWED_TYPES = {"audio", "video"}


def safe_filename(name: str) -> str:
    name = (name or "").strip()

    if not name:
        return ""

    name = Path(name).stem
    name = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1f]', "_", name)
    name = name.strip(" .")

    return name[:180]


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


def push_event(job_id, data):
    with jobs_lock:
        job = jobs.get(job_id)

    if job:
        job["queue"].put(data)


def parse_percent(line):
    match = re.search(r"(\d+(?:\.\d+)?)%", line)
    return float(match.group(1)) if match else None


def parse_speed(line):
    match = re.search(r"at\\s+([\\d.]+\\s*[KMG]?iB/s)", line)
    return match.group(1) if match else None


def parse_eta(line):
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
        destination = safe_destination(destination_value)

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
