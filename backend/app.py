import io
import torch
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps
from torchvision import transforms
from transformers import AutoModelForImageSegmentation
from contextlib import asynccontextmanager

MODEL_NAME = "ZhengPeng7/BiRefNet"
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print(f"Cargando modelo {MODEL_NAME}...")
    try:
        model = AutoModelForImageSegmentation.from_pretrained(MODEL_NAME, trust_remote_code=True)
        model.to(device='cpu', dtype=torch.float32)
        model.eval()
        print("Modelo cargado con éxito.")
    except Exception as e:
        print(f"Error al cargar el modelo: {e}")
        raise e
    yield

app = FastAPI(lifespan=lifespan)

# Habilitar CORS para permitir llamadas desde el frontend en Vercel y local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ready", "model": MODEL_NAME, "device": "cpu"}

@app.post("/remove-bg")
async def remove_bg(file: UploadFile = File(...)):
    # Validar formato de archivo
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo enviado no es una imagen válida.")
    
    try:
        # Leer archivo subido
        contents = await file.read()
        input_image = Image.open(io.BytesIO(contents))
        input_image = ImageOps.exif_transpose(input_image)
        
        # Conversión a RGB para asegurar 3 canales (eliminando alpha si la imagen ya tiene)
        image_rgb = input_image.convert("RGB")
        
        # 1. Pre-procesamiento (Alta Resolución 1024x1024)
        image_size = (1024, 1024)
        transform_image = transforms.Compose([
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        input_images = transform_image(image_rgb).unsqueeze(0)
        
        # 2. Inferencia en CPU con Float32
        with torch.no_grad():
            input_tensor = input_images.to(device='cpu', dtype=torch.float32)
            preds = model(input_tensor)[-1].sigmoid().cpu()
        
        # 3. Post-procesamiento
        pred = preds[0].squeeze()
        pred_pil = transforms.ToPILImage()(pred)
        
        # Redimensionar la máscara al tamaño original
        mask = pred_pil.resize(input_image.size, Image.Resampling.LANCZOS)
        
        # Aplicar la máscara a la imagen original
        no_bg_image = input_image.copy()
        no_bg_image.putalpha(mask)
        
        # Guardar imagen en buffer en formato PNG
        output_buffer = io.BytesIO()
        no_bg_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        
        return StreamingResponse(output_buffer, media_type="image/png")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno durante la remoción de fondo: {str(e)}")
