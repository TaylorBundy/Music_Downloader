#!/usr/bin/env bash
set -e

echo "Render native runtime ya proporciona FFmpeg."
ffmpeg -version | head -n 1

echo "Instalando Deno para yt-dlp EJS..."

if command -v deno >/dev/null 2>&1; then
    echo "Deno ya está disponible:"
    deno --version
    exit 0
fi

curl -fsSL https://deno.land/install.sh | sh

export DENO_INSTALL="$HOME/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"

echo "Deno instalado:"
deno --version
