#!/usr/bin/env bash
set -e

echo "Instalando FFmpeg..."

mkdir -p "$HOME/bin"

if command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg ya está instalado."
    ffmpeg -version | head -n 1
    exit 0
fi

apt-get update
apt-get install -y ffmpeg

ffmpeg -version | head -n 1
