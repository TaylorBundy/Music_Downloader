FROM python:3.11-slim

# Instalar FFmpeg y dependencias del sistema
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias de Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tanto el backend como el frontend al contenedor
COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 10000

# Cambiamos el directorio de ejecución a /app/backend para que corra app.py
WORKDIR /app/backend
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
