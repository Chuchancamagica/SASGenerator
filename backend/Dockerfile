FROM python:3.10-slim

# Evitar escritura de archivos bytecode y configurar buffers de salida
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Instalar dependencias esenciales del sistema operativo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Crear un usuario "user" con UID 1000 por motivos de seguridad en Hugging Face Spaces
RUN useradd -m -u 1000 user
WORKDIR $HOME/app

# Instalar PyTorch para CPU (esto reduce drásticamente el peso de la imagen Docker de ~5GB a ~1.5GB)
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copiar e instalar dependencias de Python
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del backend
COPY --chown=user:user . .

# Cambiar al usuario con permisos limitados
USER user

# Exponer el puerto por defecto de Hugging Face Spaces
EXPOSE 7860

# Ejecutar el servidor ASGI en el puerto 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
