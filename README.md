# Meme Studio & IA Background Remover (Refactorizado)

Este proyecto ha sido reestructurado para funcionar de forma distribuida, gratuita y escalable:
1. **Servidor Backend (FastAPI)**: Carga el modelo de segmentación de imágenes `ZhengPeng7/BiRefNet` y expone un endpoint para eliminar el fondo. Se despliega en **Hugging Face Spaces** usando un contenedor Docker optimizado para CPU.
2. **Cliente Frontend (React + Vite)**: Una aplicación web moderna que replica la interfaz de escritorio original (Quitar Fondo y Generador de Capas/Memes) y permite exportar memes en alta resolución con tamaño de lienzo personalizable. Se hospeda en **Vercel**.

---

## Estructura del Proyecto

```text
SASGenerator/
├── backend/            # Código de Python (FastAPI + Docker)
│   ├── app.py          # Servidor y lógica de eliminación de fondo con BiRefNet
│   ├── requirements.txt# Dependencias de Python
│   └── Dockerfile      # Configuración del contenedor Docker para Hugging Face
│
├── frontend/           # Código Web (React + Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx     # Lógica interactiva del lienzo y el cargador de imágenes
│   │   ├── App.css     # Estilos de componentes
│   │   ├── index.css   # Sistema de diseño, variables y tema oscuro premium
│   │   └── main.tsx    # Punto de entrada de React
│   ├── index.html      # Página HTML con fuentes tipográficas
│   └── ...
│
└── SASgenerator.py     # Código original de escritorio (PyQt6) intacto
```

---

## 🚀 Guía de Despliegue

### Paso 1: Desplegar el Backend en Hugging Face Spaces (Gratis)

Hugging Face nos permite levantar contenedores Docker con **16 GB de RAM y 2 vCPUs de forma gratuita**.

1. Inicia sesión en [Hugging Face](https://huggingface.co/) y haz clic en **New Space** (Nuevo Espacio).
2. Configura los siguientes parámetros:
   - **Space Name**: El nombre que tú quieras (ej. `mi-remover-birefnet`).
   - **License**: `mit` o la que prefieras.
   - **SDK**: Selecciona **Docker**.
   - **Docker Template**: Elige **Blank** (En blanco).
   - **Space Hardware**: Elige **CPU basic • 2 vCPU • 16 GB • Free** (el predeterminado).
   - **Visibility**: **Public** (Público, obligatorio para que el frontend pueda consumirlo).
3. Crea el Space.
4. Hugging Face te dará un repositorio Git para ese Space. Sube a ese repositorio **únicamente** los archivos que se encuentran dentro de la carpeta `backend/` de tu proyecto local:
   - `app.py`
   - `requirements.txt`
   - `Dockerfile`
5. Al subirlos, Hugging Face detectará el `Dockerfile`, compilará la imagen de Docker (esto toma unos 5-8 minutos la primera vez) y pondrá el servidor en estado **Running**.
6. Para obtener la URL de tu API, copia la dirección del Space. Normalmente tiene la estructura:
   `https://<tu-nombre-de-usuario>-<nombre-del-space>.hf.space`
   *(Por ejemplo: `https://cevin-mi-remover-birefnet.hf.space`)*

---

### Paso 2: Desplegar el Frontend en Vercel (Gratis)

Vercel compilará la web estática de React y la servirá de manera ultra rápida.

1. Sube tu proyecto a un repositorio en **GitHub** (asegúrate de que incluya tanto `frontend/` como `backend/`).
2. Entra en tu panel de [Vercel](https://vercel.com/) y haz clic en **Add New** > **Project**.
3. Importa el repositorio de GitHub que acabas de subir.
4. En la configuración del proyecto en Vercel:
   - **Framework Preset**: Selecciona **Vite**.
   - **Root Directory**: Haz clic en *Edit* y selecciona la carpeta **`frontend`** (muy importante, para que Vercel compile solo la web y no el backend de Python).
   - **Environment Variables** (Variables de Entorno):
     - Añade una variable llamada **`VITE_API_URL`**.
     - En el valor, pega la URL de tu Space de Hugging Face obtenida en el Paso 1 (ej. `https://cevin-mi-remover-birefnet.hf.space`).
5. Haz clic en **Deploy**.
6. En un par de minutos, Vercel te entregará una URL pública para acceder a tu aplicación web.

---

## ⚙️ Desarrollo Local (Opcional)

Si deseas correr todo en tu computadora para probar antes de subirlo:

### Ejecutar el Backend localmente:
1. Abre una terminal dentro de la carpeta `backend/`.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   # (Opcional) Si quieres la versión liviana de PyTorch para CPU:
   # pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   ```
3. Inicia el servidor:
   ```bash
   uvicorn app:app --reload --port 7860
   ```
   *El servidor estará disponible en `http://localhost:7860`.*

### Ejecutar el Frontend localmente:
1. Abre otra terminal dentro de la carpeta `frontend/`.
2. Instala las dependencias de Node:
   ```bash
   npm install
   ```
3. Ejecuta el servidor de desarrollo:
   ```bash
   npm run dev
   ```
   *La web abrirá en `http://localhost:5173`. Haz clic en el icono de engranaje (⚙️) e introduce `http://localhost:7860` como URL del servidor para apuntar a tu backend local.*
