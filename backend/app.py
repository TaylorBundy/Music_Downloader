import os
import re
import uuid
import json
import shutil
import threading
import subprocess
from pathlib import Path
from queue import Queue, Empty

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


def safe_destination(destination: str) -> Path:
    """
    Evita que el usuario pueda escribir fuera de DOWNLOAD_ROOT.
    La ruta enviada por el frontend es relativa al directorio downloads.
    """
    destination = (destination or "downloads").strip()

    destination = destination.replace("\\", "/")
    destination = destination.lstrip("/")

    parts = [
        part for part in Path(destination).parts
        if part not in ("", ".", "..")
    ]

    relative = Path(*parts) if parts else Path()

    final = (DOWNLOAD_ROOT / relative).resolve()

    if DOWNLOAD_ROOT.resolve() not in final.parents and final != DOWNLOAD_ROOT.resolve():
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


def run_job(job_id, url, media_type, output_format, filename, destination):
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

                push_event(job_id, {
                    "status": "downloading",
                    "progress": percent,
                    "speed": speed,
                    "eta": eta
                })

            elif status == "finished":
                update_job(job_id, progress=100)

                push_event(job_id, {
                    "status": "converting",
                    "progress": 100,
                    "speed": "",
                    "eta": ""
                })

        ydl_opts = {
            "outtmpl": output_template,
            "progress_hooks": [progress_hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
        }

        if media_type == "audio":
            ydl_opts["format"] = "bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"

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

        push_event(job_id, {
            "status": "converting",
            "progress": 100,
            "speed": "",
            "eta": ""
        })

        command = [
            "ffmpeg",
            "-y",
            "-i", str(downloaded_path)
        ]

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
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-movflags", "+faststart"
                ]
            elif output_format == "flv":
                command += [
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-c:a", "aac"
                ]
            elif output_format == "mov":
                command += [
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-c:a", "aac"
                ]

        command.append(str(output_path))

        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
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
            filename=output_path.name
        )

        push_event(job_id, {
            "status": "finished",
            "progress": 100,
            "filename": output_path.name
        })

    except RuntimeError as exc:
        if str(exc) == "cancelled":
            update_job(job_id, status="cancelled")
            shutil.rmtree(job_dir, ignore_errors=True)

            push_event(job_id, {
                "status": "cancelled",
                "progress": 0
            })
        else:
            update_job(job_id, status="error", error=str(exc))
            shutil.rmtree(job_dir, ignore_errors=True)

            push_event(job_id, {
                "status": "error",
                "message": str(exc)
            })

    except Exception as exc:
        update_job(job_id, status="error", error=str(exc))
        shutil.rmtree(job_dir, ignore_errors=True)

        push_event(job_id, {
            "status": "error",
            "message": str(exc)
        })


@app.get("/")
def index():
    return jsonify({
        "service": "Media Downloader",
        "status": "online"
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/download")
def start_download():
    data = request.get_json(silent=True) or {}

    url = (data.get("url") or "").strip()
    media_type = (data.get("type") or "").lower()
    output_format = (data.get("format") or "").lower()
    filename = safe_filename(data.get("filename"))
    destination_value = data.get("destination") or "downloads"

    if not url:
        return jsonify({"error": "La URL es obligatoria."}), 400

    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": "Tipo de salida inválido."}), 400

    allowed = AUDIO_FORMATS if media_type == "audio" else VIDEO_FORMATS

    if output_format not in allowed:
        return jsonify({"error": "Formato de salida inválido."}), 400

    try:
        destination = safe_destination(destination_value)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    job_id = uuid.uuid4().hex

    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "queue": Queue(),
            "process": None,
            "cancel_requested": False,
            "output_path": None,
            "filename": None
        }

    thread = threading.Thread(
        target=run_job,
        args=(
            job_id,
            url,
            media_type,
            output_format,
            filename,
            destination
        ),
        daemon=True
    )

    thread.start()

    return jsonify({
        "job_id": job_id
    })


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

                if data.get("status") in {
                    "finished",
                    "error",
                    "cancelled"
                }:
                    break

            except Empty:
                yield ": keep-alive\n\n"

                current = get_job(job_id)

                if current.get("status") in {
                    "finished",
                    "error",
                    "cancelled"
                }:
                    break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
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
        download_name=job.get("filename") or output_path.name
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
