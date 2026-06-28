import os
import glob
import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SASDownloader Legacy API")

# Habilitar CORS para permitir llamadas desde el frontend en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carpeta temporal dentro del contenedor Linux para almacenar descargas
TMP_DIR = "/tmp/downloads"
os.makedirs(TMP_DIR, exist_ok=True)

# El nombre del archivo que subiremos a Hugging Face
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")

if os.path.exists(COOKIES_PATH):
    print(f"[SASDownloader] COOKIES.TXT ENCONTRADO EN {COOKIES_PATH}")
    with open(COOKIES_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        print(f"[SASDownloader] Primera línea del cookie: {f.readline().strip()}")
else:
    print(f"[SASDownloader] ATENCION: cookies.txt NO ENCONTRADO EN {COOKIES_PATH}")

@app.get("/")
def read_root():
    return {"status": "ready", "service": "SASDownloader Legacy"}

@app.get("/diagnose")
def diagnose(url: str = Query(...)):
    import sys
    import io
    
    # Redirigir stdout/stderr para capturar logs internos de yt-dlp
    output = io.StringIO()
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = output
    sys.stderr = output
    
    results = {}
    try:
        # Test 1: Con cookies y con impersonate, default clients
        print("=== TEST 1: Chrome impersonate + default clients ===")
        ydl_opts_1 = {
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            'impersonate': ImpersonateTarget.from_str('chrome'),
        }
        if os.path.exists(COOKIES_PATH):
            ydl_opts_1['cookiefile'] = COOKIES_PATH
        try:
            with yt_dlp.YoutubeDL(ydl_opts_1) as ydl:
                info = ydl.extract_info(url, download=False)
                print(f"SUCCESS. Formats found: {len(info.get('formats', []))}")
                results["test1"] = "SUCCESS"
        except Exception as e:
            print(f"FAILED: {str(e)}")
            results["test1"] = f"FAILED: {str(e)}"

        # Test 2: Con cookies y con impersonate, restricted clients (android, tv, ios)
        print("\n=== TEST 2: Chrome impersonate + restricted clients (android, ios, tv) ===")
        ydl_opts_2 = {
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            'impersonate': ImpersonateTarget.from_str('chrome'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv']
                }
            }
        }
        if os.path.exists(COOKIES_PATH):
            ydl_opts_2['cookiefile'] = COOKIES_PATH
        try:
            with yt_dlp.YoutubeDL(ydl_opts_2) as ydl:
                info = ydl.extract_info(url, download=False)
                print(f"SUCCESS. Formats found: {len(info.get('formats', []))}")
                results["test2"] = "SUCCESS"
        except Exception as e:
            print(f"FAILED: {str(e)}")
            results["test2"] = f"FAILED: {str(e)}"

        # Test 3: SIN cookies, con impersonate, restricted clients
        print("\n=== TEST 3: Chrome impersonate + restricted clients, NO COOKIES ===")
        ydl_opts_3 = {
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            'impersonate': ImpersonateTarget.from_str('chrome'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv']
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts_3) as ydl:
                info = ydl.extract_info(url, download=False)
                print(f"SUCCESS. Formats found: {len(info.get('formats', []))}")
                results["test3"] = "SUCCESS"
        except Exception as e:
            print(f"FAILED: {str(e)}")
            results["test3"] = f"FAILED: {str(e)}"

        # Test 4: SIN cookies, SIN impersonate (urllib default), restricted clients
        print("\n=== TEST 4: Urllib default + restricted clients, NO COOKIES ===")
        ydl_opts_4 = {
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv']
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts_4) as ydl:
                info = ydl.extract_info(url, download=False)
                print(f"SUCCESS. Formats found: {len(info.get('formats', []))}")
                results["test4"] = "SUCCESS"
        except Exception as e:
            print(f"FAILED: {str(e)}")
            results["test4"] = f"FAILED: {str(e)}"

        # Test 5: Pytubefix sin OAuth (Parchado con curl_cffi)
        print("\n=== TEST 5: Pytubefix sin OAuth (Parchado con curl_cffi) ===")
        import urllib.request
        original_urlopen = urllib.request.urlopen
        
        def patched_urlopen(url, data=None, timeout=None, cafile=None, capath=None, cadefault=False, context=None):
            import curl_cffi.requests as cffi
            headers = {}
            method = "GET"
            url_str = url
            
            if isinstance(url, urllib.request.Request):
                url_str = url.get_full_url()
                headers = dict(url.headers)
                method = url.get_method()
                data = url.data
                
            try:
                # Usar curl_cffi para saltar el handshake bloqueado
                r = cffi.request(
                    method=method,
                    url=url_str,
                    headers=headers,
                    data=data,
                    timeout=timeout or 30,
                    impersonate="chrome",
                    verify=False
                )
                
                class FakeResponse:
                    def __init__(self, r):
                        self.r = r
                    def read(self, amt=None):
                        return self.r.content
                    def getcode(self):
                        return self.r.status_code
                    def info(self):
                        import email
                        headers_str = "\n".join([f"{k}: {v}" for k, v in self.r.headers.items()])
                        return email.message_from_string(headers_str)
                    def geturl(self):
                        return self.r.url
                        
                return FakeResponse(r)
            except Exception as e:
                # Fallback al urllib original en caso de error
                return original_urlopen(url, data, timeout, cafile, capath, cadefault, context)

        urllib.request.urlopen = patched_urlopen
        try:
            from pytubefix import YouTube
            yt = YouTube(url)
            print(f"SUCCESS. Title: {yt.title}")
            # Intentar listar los streams
            streams = yt.streams
            print(f"Streams found: {len(streams)}")
            results["test5"] = "SUCCESS"
        except Exception as e:
            print(f"FAILED: {str(e)}")
            results["test5"] = f"FAILED: {str(e)}"
        finally:
            urllib.request.urlopen = original_urlopen

        # Test 6: curl_cffi directo con verify=False
        print("\n=== TEST 6: curl_cffi directo a YouTube (verify=False) ===")
        try:
            import curl_cffi.requests as cffi
            resp = cffi.get(
                url,
                impersonate="chrome",
                verify=False
            )
            print(f"SUCCESS. Status: {resp.status_code}, Size: {len(resp.text)}")
            results["test6"] = f"SUCCESS (Status: {resp.status_code}, Size: {len(resp.text)})"
        except Exception as e:
            print(f"FAILED: {str(e)}")
            results["test6"] = f"FAILED: {str(e)}"

        # Test NodeJS: Verificar si NodeJS está en el PATH
        print("\n=== TEST NODEJS PATH ===")
        import subprocess
        try:
            node_version = subprocess.check_output(["node", "-v"], text=True).strip()
            print(f"NodeJS is installed: {node_version}")
            results["nodejs"] = f"Installed: {node_version}"
        except Exception as e:
            print(f"NodeJS not found in PATH: {str(e)}")
            results["nodejs"] = f"Not found: {str(e)}"

    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
    return {
        "results": results,
        "logs": output.getvalue()
    }

@app.get("/fetch-formats")
def fetch_formats(url: str = Query(..., description="URL del video de YouTube u otro portal")):
    """
    Obtiene los formatos y resoluciones de video disponibles
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'impersonate': ImpersonateTarget.from_str('chrome'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv', '-web', '-mweb', '-web_safari']
                }
            }
        }
        
        if os.path.exists(COOKIES_PATH):
            ydl_opts['cookiefile'] = COOKIES_PATH
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            resolutions = set()
            
            for f in info.get('formats', []):
                # Validar que tenga pista de video (vcodec != 'none') y una altura definida
                if f.get('vcodec') != 'none' and f.get('height') is not None:
                    resolutions.add(f'{f["height"]}p')
            
            # Ordenar resoluciones de mayor a menor (1080p, 720p, etc.)
            sorted_resolutions = sorted(
                list(resolutions), 
                key=lambda x: int(x.replace('p', '')), 
                reverse=True
            )
            
            return {
                "title": info.get('title', 'Video'),
                "duration": info.get('duration', 0),
                "formats": ["Mejor calidad disponible"] + sorted_resolutions
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al obtener formatos del video: {str(e)}")

@app.get("/download")
def download_video(
    url: str = Query(...), 
    format_type: str = Query(...), # "Video" o "Audio"
    quality: str = Query(...),     # "Mejor calidad disponible", "1080p", "720p"...
    custom_name: str = Query(None)  # Nombre personalizado de salida
):
    """
    Descarga el recurso, realiza la conversión/fusión con FFmpeg y lo envía como FileResponse
    """
    # 1. Limpieza de archivos temporales anteriores (evita saturar el almacenamiento del Space)
    for f in glob.glob(os.path.join(TMP_DIR, "*")):
        try:
            os.remove(f)
        except Exception:
            pass

    # 2. Definir el nombre del archivo de salida
    filename_base = custom_name.strip() if custom_name and custom_name.strip() else '%(title)s'
    output_template = os.path.join(TMP_DIR, f"{filename_base}.%(ext)s")
    
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'impersonate': ImpersonateTarget.from_str('chrome'),
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'tv', '-web', '-mweb', '-web_safari']
            }
        }
    }
    
    if os.path.exists(COOKIES_PATH):
        ydl_opts['cookiefile'] = COOKIES_PATH

    # 3. Configurar calidades y codecs
    final_extension = ''
    if format_type == "Video":
        if quality != "Mejor calidad disponible":
            res = quality.replace('p', '')
            # Descarga el mejor video menor o igual a la resolución elegida + mejor audio, o lo mejor que haya por debajo
            ydl_opts['format'] = f'bestvideo[height<={res}]+bestaudio/best[height<={res}]'
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            
        ydl_opts['merge_output_format'] = 'mp4'
        final_extension = '.mp4'
    else:
        # Configuración de solo audio (MP3 192kbps)
        ydl_opts['format'] = 'best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }]
        final_extension = '.mp3'

    try:
        # 4. Iniciar descarga en el servidor
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Si yt-dlp re-empaquetó en mp4 o convirtió en mp3, la extensión real puede variar del template inicial
            base_path = os.path.splitext(filename)[0]
            filename_real = base_path + final_extension

        # 5. Enviar el archivo procesado de vuelta al navegador
        if os.path.exists(filename_real):
            return FileResponse(
                filename_real, 
                media_type='application/octet-stream', 
                filename=os.path.basename(filename_real)
            )
        else:
            raise HTTPException(status_code=500, detail="El archivo se descargó pero no se encuentra en el servidor temporal.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante el procesamiento/descarga: {str(e)}")
