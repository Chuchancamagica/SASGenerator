import customtkinter as ctk
from tkinter import filedialog
import yt_dlp
import threading
import queue
import os
import glob
import subprocess
import ctypes 

# --- Configuración de la Apariencia ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

myappid = 'sas.downloader.youtube.1.0' # Puedes usar cualquier cadena única
try:
    if os.name == 'nt': # Solo para Windows
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception as e:
    print(f"Advertencia: No se pudo establecer el AppID para la barra de tareas. Error: {e}")

class YouTubeDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Ventana Principal ---
        self.title("SAS Downloader - YouTube")
        self.geometry("630x690")
        self.resizable(True, True)
        try:
            self.iconbitmap('C:/Users/gbasc/Desktop/Downloader/xuxis.ico')
        except:
            pass

        # --- Variables de Estado ---
        self.download_thread = None
        self.cancel_download_event = threading.Event()
        self.message_queue = queue.Queue()
        self.downloaded_file_path = None  # Para almacenar la ruta del archivo descargado

        # --- Crear los Widgets ---
        self.create_widgets()

        # --- Iniciar el procesador de mensajes ---
        self.process_messages()

    def create_widgets(self):
        # --- Título ---
        title_label = ctk.CTkLabel(self, text="🎥 SAS Downloader", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=(20, 20))

        # --- Contenedor Principal ---
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(padx=20, pady=0, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)

        # URL y Botón de Búsqueda
        ctk.CTkLabel(main_frame, text="URL del Video:").grid(row=0, column=0, sticky="w", padx=5)
        url_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        url_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        url_frame.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.search_button = ctk.CTkButton(url_frame, text="Cargar Resoluciones", width=160, command=self.fetch_formats)
        self.search_button.grid(row=0, column=1, padx=(10, 0))

        # Ruta de Descarga
        ctk.CTkLabel(main_frame, text="Carpeta de Descarga:").grid(row=2, column=0, sticky="w", padx=5)
        path_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        path_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        path_frame.grid_columnconfigure(0, weight=1)
        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="Selecciona una carpeta...")
        self.path_entry.grid(row=0, column=0, sticky="ew")
        self.path_button = ctk.CTkButton(path_frame, text="Examinar", width=100, command=self.browse_path)
        self.path_button.grid(row=0, column=1, padx=(10, 0))

        # Formato de Descarga
        ctk.CTkLabel(main_frame, text="Formato de Descarga:").grid(row=4, column=0, sticky="w", padx=5)
        format_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        format_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self.format_var = ctk.StringVar(value="Video")
        self.video_radio = ctk.CTkRadioButton(format_frame, text="Video (MP4)", variable=self.format_var, value="Video", command=self.toggle_quality_selector)
        self.video_radio.grid(row=0, column=0, padx=(5, 0))
        self.quality_combo = ctk.CTkComboBox(format_frame, values=["Mejor calidad disponible"], state="normal", width=180)
        self.quality_combo.grid(row=0, column=1, padx=10)
        self.audio_radio = ctk.CTkRadioButton(format_frame, text="Solo Audio (MP3)", variable=self.format_var, value="Audio", command=self.toggle_quality_selector)
        self.audio_radio.grid(row=0, column=2, padx=10)

        # Nombre del archivo
        ctk.CTkLabel(main_frame, text="Nombre del archivo:").grid(row=6, column=0, sticky="w", padx=5)
        self.filename_entry = ctk.CTkEntry(main_frame, placeholder_text="Ingresa el nombre del archivo...")
        self.filename_entry.grid(row=7, column=0, sticky="ew", pady=(0, 10))

        # --- Botones de Acción y Estado ---
        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.grid(row=8, column=0, pady=(20, 10))
        self.status_label = ctk.CTkLabel(action_frame, text="Listo para descargar", text_color="gray")
        self.status_label.pack()

        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.grid(row=9, column=0, pady=10)
        self.start_button = ctk.CTkButton(buttons_frame, text="Iniciar Descarga", command=self.start_download, height=40, width=200, text_color_disabled="white")
        self.start_button.pack(side="left", padx=5)
        font_bold = ("Arial", 12, "bold")
        self.cancel_button = ctk.CTkButton(
            buttons_frame,
            text="Cancelar",
            command=self.cancel_download,
            height=40,
            width=70,
            fg_color="#FF1E1E",
            hover_color="#B80404",
            text_color="white",
            text_color_disabled="white",
            font=font_bold
        )
        self.cancel_button.pack(side="left", padx=5)

        # --- Ventana de Log y Limpiar ---
        ctk.CTkLabel(main_frame, text="Log de Descarga:").grid(row=10, column=0, sticky="w", padx=5, pady=(10, 0))
        self.log_textbox = ctk.CTkTextbox(main_frame, height=150, state="disabled")
        self.log_textbox.grid(row=11, column=0, sticky="ew", pady=5)

        # Frame para los botones inferiores
        bottom_buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_buttons_frame.grid(row=12, column=0, pady=(5, 10))
        self.clear_log_button = ctk.CTkButton(bottom_buttons_frame, text="Limpiar Log", command=self.clear_log, fg_color="#555555", hover_color="#444444")
        self.clear_log_button.pack(side="left", padx=5)

        self.open_location_button = ctk.CTkButton(
            bottom_buttons_frame,
            text="Abrir ubicación",
            command=self.open_file_location,
            fg_color="#444444",  # Fondo gris oscuro cuando deshabilitado
            hover_color="#ADAD00",  # Color hover cuando habilitado
            height=30,
            width=30,
            text_color="#FFFFFF",  # Texto blanco cuando habilitado
            text_color_disabled="#888888",  # Texto gris claro cuando deshabilitado
            state="disabled",  # Inicialmente deshabilitado
            font=font_bold
        )
        self.open_location_button.pack(side="left", padx=5)

    def clear_log(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)
            self.log_message(f"Ruta de descarga establecida: {path}")

    def toggle_quality_selector(self):
        if self.format_var.get() == "Video":
            self.quality_combo.configure(state="normal")
        else:
            self.quality_combo.configure(state="disabled")

    def log_message(self, msg):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{msg}\n")
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")

    def process_messages(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                msg_type = message.get("type")
                msg_data = message.get("data")

                if msg_type == "log":
                    self.log_message(msg_data)
                elif msg_type == "status":
                    self.status_label.configure(text=msg_data)
                elif msg_type == "formats":
                    formats_data = msg_data if msg_data else ["No se encontraron formatos de video"]
                    self.quality_combo.configure(values=["Mejor calidad disponible"] + formats_data)
                    self.quality_combo.set("Mejor calidad disponible")
                    self.log_message("Resoluciones de video cargadas.")
                elif msg_type == "download_complete":
                    self.reset_ui()
                    self.log_message("¡Descarga completada con éxito!")
                    self.downloaded_file_path = msg_data
                    if self.downloaded_file_path:
                        self.open_location_button.configure(state="normal", fg_color="#CECE02")  # Habilitar y cambiar a amarillo
                elif msg_type == "download_error":
                    self.reset_ui()
                    self.log_message(f"ERROR: {msg_data}")
        except queue.Empty:
            pass
        self.after(100, self.process_messages)

    def reset_ui(self):
        self.start_button.configure(state="normal", text="Iniciar Descarga")
        self.cancel_button.configure(state="disabled")
        self.search_button.configure(state="normal")
        self.open_location_button.configure(state="disabled", fg_color="#444444")  # Deshabilitar y cambiar a gris
        self.downloaded_file_path = None  # Limpiar la ruta del archivo
        self.status_label.configure(text="Listo para descargar")

    def fetch_formats(self):
        url = self.url_entry.get()
        if not url:
            self.log_message("Por favor, ingresa una URL primero.")
            return
        self.log_message("Cargando resoluciones...")
        self.status_label.configure(text="Buscando...")
        self.search_button.configure(state="disabled")
        threading.Thread(target=self._fetch_formats_worker, args=(url,), daemon=True).start()

    def _fetch_formats_worker(self, url):
        try:
            ydl_opts = {'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                resolutions = set()
                for f in info.get('formats', []):
                    if f.get('vcodec') != 'none' and f.get('height') is not None:
                        resolutions.add(f'{f["height"]}p')
                sorted_resolutions = sorted(list(resolutions), key=lambda x: int(x.replace('p', '')), reverse=True)
                self.message_queue.put({"type": "formats", "data": sorted_resolutions})
        except Exception as e:
            self.message_queue.put({"type": "log", "data": f"Error al obtener calidades: {e}"})
        finally:
            self.message_queue.put({"type": "status", "data": "Resoluciones cargadas"})
            self.search_button.configure(state="normal")

    def start_download(self):
        url = self.url_entry.get()
        path = self.path_entry.get()
        if not url or not path:
            self.log_message("Error: La URL y la ruta de descarga no pueden estar vacías.")
            return

        self.cancel_download_event.clear()
        self.start_button.configure(state="disabled", text="Descargando...")
        self.cancel_button.configure(state="normal")
        self.search_button.configure(state="disabled")
        self.open_location_button.configure(state="disabled", fg_color="#444444")  # Deshabilitar y cambiar a gris
        self.status_label.configure(text="Iniciando descarga...")
        self.log_message("Iniciando descarga...")
        self.download_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.download_thread.start()

    def cancel_download(self):
        self.log_message("Solicitando cancelación...")
        self.cancel_download_event.set()

    def _download_worker(self):
        url = self.url_entry.get()
        path = self.path_entry.get()
        download_format = self.format_var.get()
        filename_base = self.filename_entry.get() or '%(title)s'

        try:
            ydl_opts = {
                'progress_hooks': [self.progress_hook],
                'noprogress': True,
                'updatetime': False,
                # Usamos una plantilla que NO incluye la extensión todavía
                'outtmpl': os.path.join(path, filename_base) 
            }

            final_extension = ''
            if download_format == "Video":
                selected_quality = self.quality_combo.get()
                if selected_quality != "Mejor calidad disponible":
                    res = selected_quality.replace('p', '')
                    ydl_opts['format'] = f'bestvideo[height<={res}]+bestaudio/best[height<={res}]'
                    self.log_message(f"Descargando en la mejor calidad hasta {res}p...")
                else:
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                    self.log_message("Descargando en la mejor calidad disponible en general...")
                ydl_opts['merge_output_format'] = 'mp4'
                final_extension = '.mp4'

            elif download_format == "Audio":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                final_extension = '.mp3'

            # Obtener el nombre de archivo final REAL antes de descargar
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                # Construimos la ruta final completa que tendrá el archivo
                final_filepath = ydl.prepare_filename(info) + final_extension
            
            # Ahora sí, ejecutar la descarga
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not self.cancel_download_event.is_set():
                # Enviamos la ruta final que construimos, no la que reporta el hook.
                self.message_queue.put({"type": "download_complete", "data": final_filepath})

        except Exception as e:
            if self.cancel_download_event.is_set():
                # Para la limpieza, necesitamos obtener el nombre base del archivo
                with yt_dlp.YoutubeDL({'outtmpl': '%(title)s', 'quiet': True}) as ydl_name:
                    info_cleanup = ydl_name.extract_info(url, download=False)
                    base_filename_cleanup = ydl_name.prepare_filename(info_cleanup)

                self.message_queue.put({"type": "log", "data": "Descarga cancelada. Limpiando archivos..."})
                threading.Timer(0.5, self._cleanup_files, args=[path, os.path.basename(base_filename_cleanup)]).start()
                self.message_queue.put({"type": "status", "data": "Cancelado"})
                self.reset_ui()
            else:
                self.message_queue.put({"type": "download_error", "data": str(e)})

    def _cleanup_files(self, path, base_filename):
        try:
            search_pattern = os.path.join(path, f"{base_filename}*")
            partial_files = glob.glob(search_pattern)
            if not partial_files:
                self.message_queue.put({"type": "log", "data": "No se encontraron archivos parciales para limpiar."})
                return
            for f in partial_files:
                try:
                    os.remove(f)
                    self.message_queue.put({"type": "log", "data": f"Archivo eliminado: {os.path.basename(f)}"})
                except OSError as err:
                    self.message_queue.put({"type": "log", "data": f"Error al eliminar {os.path.basename(f)}: {err}"})
        except Exception as e:
            self.message_queue.put({"type": "log", "data": f"Error inesperado durante la limpieza: {e}"})

    def progress_hook(self, d):
        if self.cancel_download_event.is_set():
            raise yt_dlp.utils.DownloadError("Descarga cancelada por el usuario.")
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0.0%').strip()
            speed_str = d.get('_speed_str', 'N/A').strip()
            self.message_queue.put({"type": "log", "data": f"Progreso: {percent_str} | Velocidad: {speed_str}"})
            self.message_queue.put({"type": "status", "data": f"Descargando... {percent_str}"})
        elif d['status'] == 'finished':
            self.message_queue.put({"type": "log", "data": "Procesando archivo (merge/conversión)..."})
            self.message_queue.put({"type": "status", "data": "Finalizando..."})

    def open_file_location(self):
        if self.downloaded_file_path:
            if os.name == 'nt':  # Windows
                subprocess.Popen(f'explorer /select,"{self.downloaded_file_path}"')
                print(f"Abriendo ubicación del archivo: {self.downloaded_file_path}")
            elif os.name == 'posix':  # macOS or Linux
                subprocess.Popen(['xdg-open', os.path.dirname(self.downloaded_file_path)])

if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()