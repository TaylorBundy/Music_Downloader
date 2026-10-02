FROM python:3.11-slim

# Instalar FFmpeg y dependencias del sistema
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias de Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Render asigna dinámicamente un puerto mediante la variable PORT (por defecto 10000)
EXPOSE 10000

# Comando para ejecutar tu aplicación (ejemplo con FastAPI/Uvicorn)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
