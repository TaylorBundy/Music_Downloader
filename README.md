# Media Downloader — yt-dlp + FFmpeg + Render

Aplicación web minimalista para descargar contenido mediante `yt-dlp` y convertirlo con `FFmpeg`.

## Características

- Frontend HTML/CSS/JavaScript separado.
- Backend Flask.
- Descarga mediante yt-dlp.
- Conversión mediante FFmpeg.
- Audio:
  - MP3
  - FLAC
  - OGG
- Video:
  - MP4
  - FLV
  - MOV
- Nombre personalizado.
- Ruta relativa de destino en el servidor.
- Progreso mediante Server-Sent Events (SSE).
- Cancelación de trabajos.
- Descarga del archivo terminado.
- Preparado para Render.

## Estructura

```text
media-downloader/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   └── downloads/
├── install-ffmpeg.sh
├── render.yaml
├── .gitignore
└── README.md
```

## 1. Backend local

Windows:

```cmd
cd backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Necesitás tener FFmpeg instalado y disponible en PATH.

Ejecutar:

```cmd
python app.py
```

El backend quedará disponible normalmente en:

```text
http://127.0.0.1:5000
```

## 2. Configurar frontend

Abrí:

```text
frontend/app.js
```

y modificá:

```javascript
const API_BASE = "https://TU-SERVICIO.onrender.com";
```

por la URL real de tu servicio Render.

Para pruebas locales:

```javascript
const API_BASE = "http://127.0.0.1:5000";
```

## 3. Subir a GitHub

Desde la carpeta del proyecto:

```cmd
git init
git add .
git commit -m "Proyecto inicial Media Downloader"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

## 4. Crear servicio en Render

En Render:

1. New + Web Service.
2. Seleccionar el repositorio.
3. Render detectará `render.yaml`.
4. Crear el servicio.

El backend utilizará:

```text
gunicorn
Flask
yt-dlp
FFmpeg
```

## 5. Importante sobre la ruta de destino

La ruta introducida en la interfaz es relativa al directorio:

```text
backend/downloads/
```

Por ejemplo:

```text
downloads
```

genera:

```text
backend/downloads/
```

y:

```text
videos
```

genera:

```text
backend/downloads/videos/
```

No es posible que Render escriba directamente en:

```text
C:\Users\Taylor\Videos
```

porque esa carpeta está en la PC del usuario, no en el servidor.

El navegador recibe finalmente el archivo mediante:

```text
GET /download/<job_id>
```

## 6. Limitación importante de Render

El almacenamiento local de un servicio Render no debe considerarse almacenamiento permanente.

El archivo se genera temporalmente, se descarga al navegador y luego puede eliminarse.

Para una aplicación de uso personal esto puede ser suficiente.

Para archivos grandes o uso frecuente conviene agregar almacenamiento externo, por ejemplo S3, Cloudflare R2 u otro almacenamiento compatible.

## 7. API

### POST /download

Ejemplo:

```json
{
  "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
  "type": "audio",
  "format": "mp3",
  "filename": "mi_audio",
  "destination": "downloads"
}
```

Respuesta:

```json
{
  "job_id": "xxxxxxxxxxxxxxxx"
}
```

### GET /progress/<job_id>

Devuelve eventos SSE:

```json
{
  "status": "downloading",
  "progress": 52.4,
  "speed": "2.4MiB/s",
  "eta": "00:18"
}
```

### POST /cancel/<job_id>

Cancela el proceso.

### GET /download/<job_id>

Descarga el archivo final.

## 8. Seguridad

El backend restringe la ruta de destino para impedir que el usuario utilice rutas como:

```text
../../
```

o intente escribir fuera del directorio permitido.

El nombre de archivo también se limpia antes de utilizarlo.

## 9. Desarrollo recomendado

Para una versión pública conviene agregar:

- límite de tamaño;
- autenticación;
- límite de trabajos simultáneos;
- limpieza automática de archivos antiguos;
- límite de tiempo;
- rate limiting;
- almacenamiento externo;
- lista blanca de sitios si corresponde.

## 10. Licencias y sitios compatibles

`yt-dlp` soporta numerosos sitios, pero la disponibilidad depende del sitio, sus cambios técnicos y sus condiciones de uso.

El usuario debe tener derecho a descargar o procesar el contenido solicitado y respetar las condiciones aplicables.
