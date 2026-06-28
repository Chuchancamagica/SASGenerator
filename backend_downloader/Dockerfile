FROM python:3.10-slim

# Configurar variables de entorno y evitar prompts interactivos
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Instalar FFmpeg y dependencias básicas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Configurar usuario con UID 1000 para cumplir las políticas de Hugging Face
RUN useradd -m -u 1000 user
WORKDIR $HOME/app

# Copiar e instalar dependencias
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente del backend
COPY --chown=user:user . .

# Cambiar al usuario con permisos limitados
USER user

# Hugging Face expone y escucha en el puerto 7860
EXPOSE 7860

# Levantar el servidor ASGI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
