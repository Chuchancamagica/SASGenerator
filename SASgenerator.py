import sys
import os
import platform
import io
import math

# --- 1. FIX PARA WINDOWS (Intacto de tu código original) ---
if platform.system() == "Windows":
    import ctypes
    from importlib.util import find_spec
    try:
        # Intenta buscar dónde está instalado torch y cargar la DLL a la fuerza
        if (spec := find_spec("torch")) and spec.origin:
            lib_path = os.path.join(os.path.dirname(spec.origin), "lib", "c10.dll")
            if os.path.exists(lib_path):
                ctypes.CDLL(os.path.normpath(lib_path))
    except Exception as e:
        print(f"Advertencia: No se pudo pre-cargar c10.dll: {e}")

import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation
from PIL import Image, ImageQt, ImageOps

from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QMessageBox, QPushButton, 
                             QFileDialog, QGraphicsView, QGraphicsScene, QTabWidget,
                             QListWidget, QListWidgetItem, QAbstractItemView,
                             QGraphicsTextItem, QStyle, QGraphicsView, QGraphicsItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QBuffer, QIODevice, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QTransform, QPen, QColor, QPainterPath
from PyQt6.QtWidgets import QGraphicsPixmapItem


# --- 2. LÓGICA DE IA (Intacta de tu código original) ---
MODEL_NAME = "ZhengPeng7/BiRefNet"
global_model = None

def load_global_model():
    global global_model
    if global_model is None:
        print(f"Cargando modelo {MODEL_NAME}...")
        try:
            # Cargar arquitectura
            global_model = AutoModelForImageSegmentation.from_pretrained(MODEL_NAME, trust_remote_code=True)
            # Forzar Float32 para CPU (Vital para evitar errores de Half/Float)
            global_model.to(device='cpu', dtype=torch.float32) 
            global_model.eval()
        except Exception as e:
            print(f"Error cargando modelo: {e}")
            raise e
    return global_model

class RemoverFondoWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, input_image):
        super().__init__()
        self.input_image = input_image

    def run(self):
        try:
            model = load_global_model()
            
            # --- CRUCIAL: CORRECCIÓN DEL ERROR "TENSOR 4 vs 3" ---
            image_rgb = self.input_image.convert("RGB")
            
            # 1. Pre-procesamiento (Alta Resolución 1024x1024)
            image_size = (1024, 1024)
            transform_image = transforms.Compose([
                transforms.Resize(image_size),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])
            
            input_images = transform_image(image_rgb).unsqueeze(0)
            
            # 2. Inferencia
            with torch.no_grad():
                input_tensor = input_images.to(device='cpu', dtype=torch.float32)
                preds = model(input_tensor)[-1].sigmoid().cpu()
            
            # 3. Post-procesamiento
            pred = preds[0].squeeze()
            pred_pil = transforms.ToPILImage()(pred)
            
            # Redimensionar máscara al tamaño original usando LANCZOS
            mask = pred_pil.resize(self.input_image.size, Image.Resampling.LANCZOS)
            
            # Aplicar máscara a la imagen original
            no_bg_image = self.input_image.copy()
            no_bg_image.putalpha(mask)
            
            self.finished.emit(no_bg_image)
            
        except Exception as e:
            self.error.emit(f"Error Técnico:\n{str(e)}")


# --- 3. PESTAÑA: QUITAR FONDO (Tu interfaz adaptada) ---
class DropLabel(QLabel):
    # ADAPTACIÓN: Señal para comunicarse con la pestaña en lugar de usar self.window()
    fileDropped = pyqtSignal(str) 

    def __init__(self, title="ANTES", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_text = f"\n\n{title}\nArrastra o pega (Ctrl+V)\n\n"
        self.setText(self.default_text)
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 10px;
                color: #555;
                font-size: 14px;
                font-weight: bold;
                background-color: #f9f9f9;
            }
            QLabel:hover {
                background-color: #e6e6e6;
                border-color: #666;
            }
        """)
        self.setAcceptDrops(True)
        self.setMinimumSize(300, 400)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            # ADAPTACIÓN: Emitimos la señal con la ruta del archivo
            self.fileDropped.emit(files[0])

class ResultLabel(QLabel):
    def __init__(self, title="DESPUÉS", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(f"\n\n{title}\n(El resultado aparecerá aquí)\n\n")
        self.setStyleSheet("""
            QLabel {
                border: 3px solid #ddd;
                border-radius: 10px;
                color: #888;
                font-size: 14px;
                background-color: #eee;
            }
        """)
        self.setMinimumSize(300, 400)

class BackgroundRemoverTab(QWidget): 
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self.main_layout = QVBoxLayout(self)

        self.image_layout = QHBoxLayout()
        self.lbl_before = DropLabel("ORIGINAL")
        self.lbl_after = ResultLabel("SIN FONDO")
        
        self.lbl_before.fileDropped.connect(self.cargar_imagen_desde_ruta)
        
        self.image_layout.addWidget(self.lbl_before)
        self.image_layout.addWidget(self.lbl_after)
        self.main_layout.addLayout(self.image_layout)

        self.button_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Reiniciar")
        self.btn_reset.setFixedHeight(45)
        self.btn_reset.setStyleSheet("padding: 0px 20px; font-size: 14px;")
        self.btn_reset.clicked.connect(self.reiniciar_interfaz)
        
        # --- NUEVO: Botón de copiar al portapapeles ---
        self.btn_copy = QPushButton("📋 Copiar al Portapapeles")
        self.btn_copy.setFixedHeight(45)
        self.btn_copy.setStyleSheet("padding: 0px 20px; font-size: 14px; background-color: #007bff; color: white; font-weight: bold;")
        self.btn_copy.clicked.connect(self.copiar_al_portapapeles)
        self.btn_copy.setEnabled(False)

        self.btn_save = QPushButton("Guardar Resultado")
        self.btn_save.setFixedHeight(45)
        self.btn_save.setStyleSheet("padding: 0px 20px; font-size: 14px; background-color: #572364; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self.guardar_imagen)
        self.btn_save.setEnabled(False)

        self.button_layout.addWidget(self.btn_reset)
        self.button_layout.addWidget(self.btn_copy)
        self.button_layout.addWidget(self.btn_save)
        self.main_layout.addLayout(self.button_layout)

        self.current_pil_image = None
        self.result_pil_image = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_V and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            if mime_data.hasImage():
                self.procesar_qimage(mime_data.imageData())
            elif mime_data.hasUrls():
                self.cargar_imagen_desde_ruta(mime_data.urls()[0].toLocalFile())

    def cargar_imagen_desde_ruta(self, file_path):
        try:
            pil_img = Image.open(file_path)
            pil_img = ImageOps.exif_transpose(pil_img) 
            self.mostrar_en_label(pil_img, self.lbl_before)
            self.iniciar_procesamiento(pil_img)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar: {e}")

    def procesar_qimage(self, qimage):
        if qimage.isNull(): return
        ba = QBuffer()
        ba.open(QIODevice.OpenModeFlag.ReadWrite)
        qimage.save(ba, "PNG")
        buffer = io.BytesIO(ba.data().data())
        pil_img = Image.open(buffer)
        self.mostrar_en_label(pil_img, self.lbl_before)
        self.iniciar_procesamiento(pil_img)

    def mostrar_en_label(self, pil_img, label_widget):
        im_qt = ImageQt.ImageQt(pil_img)
        pixmap = QPixmap.fromImage(im_qt)
        label_widget.setPixmap(pixmap.scaled(
            label_widget.width(), label_widget.height(), Qt.AspectRatioMode.KeepAspectRatio
        ))

    def iniciar_procesamiento(self, pil_img):
        self.current_pil_image = pil_img
        
        self.lbl_after.setText("PROCESANDO...")
        self.lbl_after.setStyleSheet("border: 3px solid #2196F3; color: #2196F3;")
        self.btn_reset.setEnabled(False)

        self.worker = RemoverFondoWorker(pil_img)
        self.worker.finished.connect(self.finalizar_procesamiento)
        self.worker.error.connect(self.mostrar_error)
        self.worker.start()

    def finalizar_procesamiento(self, pil_output):
        self.result_pil_image = pil_output
        self.mostrar_en_label(pil_output, self.lbl_after)
        self.lbl_after.setStyleSheet("border: 3px solid #4CAF50; background-color: #eee;")
        
        # --- ACTIVAMOS LOS DOS BOTONES AL TERMINAR ---
        self.btn_copy.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.btn_reset.setEnabled(True)

    def mostrar_error(self, error_msg):
        self.lbl_after.setText("❌ ERROR")
        self.btn_reset.setEnabled(True)
        QMessageBox.critical(self, "Error Fatal", error_msg)

    # --- NUEVA FUNCIÓN DE COPIADO ---
    def copiar_al_portapapeles(self):
        if self.result_pil_image:
            from PyQt6.QtGui import QPixmap
            
            # 1. Convertir la imagen de Pillow a formato Qt temporal
            im_qt = ImageQt.ImageQt(self.result_pil_image)
            
            # 2. CRUCIAL: Convertir a QPixmap. 
            # Esto obliga a Qt a crear una copia segura en su propia memoria, evitando el crasheo.
            pixmap_seguro = QPixmap.fromImage(im_qt)
            
            # 3. Enviar el Pixmap seguro al portapapeles
            QApplication.clipboard().setPixmap(pixmap_seguro)
            
            # Cambiamos el texto brevemente para dar feedback visual
            original_text = self.btn_copy.text()
            self.btn_copy.setText("¡Copiado! ✔️")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy.setText(original_text))

    def guardar_imagen(self):
        if not self.result_pil_image: return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Imagen", "sin_fondo_birefnet.png", "PNG Files (*.png)")
        if path:
            self.result_pil_image.save(path)
            QMessageBox.information(self, "Éxito", "Imagen guardada correctamente.")

    def reiniciar_interfaz(self):
        self.lbl_before.clear()
        self.lbl_before.setText(self.lbl_before.default_text)
        self.lbl_after.clear()
        self.lbl_after.setText("\n\nDESPUÉS\nResultados aquí\n\n")
        self.lbl_after.setStyleSheet("border: 3px solid #ddd; border-radius: 10px; color: #888; background-color: #fff;")
        self.current_pil_image = None
        self.result_pil_image = None
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False) # Apagamos el botón de copiar


class ResizableItemMixin:
    """Hitbox visible, redimensionado con trigonometría, Bordes Pegajosos limpios y ROTACIÓN CON IMÁN."""
    def setup_resizing(self):
        self.setAcceptHoverEvents(True)
        self.is_resizing = False
        self.is_rotating = False
        self.resize_dir = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.setTransformOriginPoint(super().boundingRect().center())

    def boundingRect(self):
        rect = QRectF(super().boundingRect())
        
        scale_x = abs(self.transform().m11()) if self.transform().m11() != 0 else 1
        scale_y = abs(self.transform().m22()) if self.transform().m22() != 0 else 1
        
        offset_y = 35 / scale_y
        handle_radius = 25 / scale_y
        handle_size = 15 / max(scale_x, scale_y)
        
        rect.adjust(-handle_size, -(offset_y + handle_radius), handle_size, handle_size)
        return rect

    def shape(self):
        path = QPainterPath()
        rect = super().boundingRect()
        path.addRect(rect)
        
        if self.isSelected():
            scale_y = abs(self.transform().m22()) if self.transform().m22() != 0 else 1
            offset_y = 35 / scale_y
            handle_radius = 20 / scale_y
            path.addEllipse(QPointF(rect.center().x(), rect.top() - offset_y), handle_radius, handle_radius)
            
        return path

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if getattr(self, 'is_resizing', False) or getattr(self, 'is_rotating', False):
                return super().itemChange(change, value)
                
            new_pos = value
            scene_rect = self.sceneBoundingRect()
            x, y = new_pos.x(), new_pos.y()
            
            RESIST_ZONE = 40 
            
            offset_x = scene_rect.left() - self.pos().x()
            offset_y = scene_rect.top() - self.pos().y()
            
            if -RESIST_ZONE < (x + offset_x) < 0: 
                x = -offset_x
            right_edge = 1000 - scene_rect.width()
            if right_edge < (x + offset_x) < right_edge + RESIST_ZONE: 
                x = right_edge - offset_x
                
            if -RESIST_ZONE < (y + offset_y) < 0: 
                y = -offset_y
            bottom_edge = 700 - scene_rect.height()
            if bottom_edge < (y + offset_y) < bottom_edge + RESIST_ZONE: 
                y = bottom_edge - offset_y
                
            return QPointF(x, y)
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        is_selected = option.state & QStyle.StateFlag.State_Selected
        if is_selected:
            option.state &= ~QStyle.StateFlag.State_Selected
            
        super().paint(painter, option, widget)
        
        if is_selected:
            scale_x = abs(self.transform().m11()) if self.transform().m11() != 0 else 1
            scale_y = abs(self.transform().m22()) if self.transform().m22() != 0 else 1
            pen_width = 2 / max(scale_x, scale_y)
            handle_size = 12 / max(scale_x, scale_y)
            
            rect = super().boundingRect()
            
            painter.setPen(QPen(QColor("#00a8ff"), pen_width, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            
            painter.setBrush(QColor("#00a8ff"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(rect.left(), rect.top(), handle_size, handle_size))
            painter.drawRect(QRectF(rect.right() - handle_size, rect.top(), handle_size, handle_size))
            painter.drawRect(QRectF(rect.left(), rect.bottom() - handle_size, handle_size, handle_size))
            painter.drawRect(QRectF(rect.right() - handle_size, rect.bottom() - handle_size, handle_size, handle_size))

            center_x = rect.center().x()
            offset_y = 35 / scale_y
            rot_point = QPointF(center_x, rect.top() - offset_y)
            
            painter.setPen(QPen(QColor("#00a8ff"), pen_width, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(center_x, rect.top()), rot_point)
            
            painter.setBrush(QColor("#ffaa00"))
            painter.setPen(QPen(Qt.GlobalColor.white, pen_width * 1.5))
            rot_radius = 12 / max(scale_x, scale_y)
            painter.drawEllipse(rot_point, rot_radius, rot_radius)


    def hoverMoveEvent(self, event):
        if hasattr(self, 'textInteractionFlags') and self.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction:
            super().hoverMoveEvent(event)
            return

        current_sx = abs(self.transform().m11()) if self.transform().m11() != 0 else 1
        current_sy = abs(self.transform().m22()) if self.transform().m22() != 0 else 1
        margin_x = 15 / current_sx
        margin_y = 15 / current_sy

        rect = super().boundingRect()
        pos = event.pos()
        x, y = pos.x(), pos.y()

        center_x = rect.center().x()
        offset_y = 35 / current_sy
        dist_to_rot = math.hypot(x - center_x, y - (rect.top() - offset_y))
        rot_threshold = 20 / max(current_sx, current_sy)

        if dist_to_rot <= rot_threshold:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.resize_dir = 'rotate'
        else:
            on_left = (rect.left() <= x <= rect.left() + margin_x)
            on_right = (rect.right() - margin_x <= x <= rect.right())
            on_top = (rect.top() <= y <= rect.top() + margin_y)
            on_bottom = (rect.bottom() - margin_y <= y <= rect.bottom())

            if on_left and on_top: self.setCursor(Qt.CursorShape.SizeFDiagCursor); self.resize_dir = 'tl'
            elif on_right and on_bottom: self.setCursor(Qt.CursorShape.SizeFDiagCursor); self.resize_dir = 'br'
            elif on_right and on_top: self.setCursor(Qt.CursorShape.SizeBDiagCursor); self.resize_dir = 'tr'
            elif on_left and on_bottom: self.setCursor(Qt.CursorShape.SizeBDiagCursor); self.resize_dir = 'bl'
            elif on_left: self.setCursor(Qt.CursorShape.SizeHorCursor); self.resize_dir = 'l'
            elif on_right: self.setCursor(Qt.CursorShape.SizeHorCursor); self.resize_dir = 'r'
            elif on_top: self.setCursor(Qt.CursorShape.SizeVerCursor); self.resize_dir = 't'
            elif on_bottom: self.setCursor(Qt.CursorShape.SizeVerCursor); self.resize_dir = 'b'
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.resize_dir = None
            
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.resize_dir = None
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if hasattr(self, 'textInteractionFlags') and self.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction:
            super().mousePressEvent(event)
            return

        if self.resize_dir == 'rotate' and event.button() == Qt.MouseButton.LeftButton:
            self.is_rotating = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            
            self.center_scene_pos = self.mapToScene(super().boundingRect().center())
            mouse_scene_pos = event.scenePos()
            
            dy = mouse_scene_pos.y() - self.center_scene_pos.y()
            dx = mouse_scene_pos.x() - self.center_scene_pos.x()
            self.start_angle = math.degrees(math.atan2(dy, dx))
            self.start_rotation = self.rotation()
            event.accept()
            
        elif self.resize_dir and event.button() == Qt.MouseButton.LeftButton:
            self.is_resizing = True
            self.start_mouse_pos = event.scenePos()
            self.start_scale_x = self.transform().m11() if self.transform().m11() != 0 else 1
            self.start_scale_y = self.transform().m22() if self.transform().m22() != 0 else 1
            
            rect = super().boundingRect()
            if self.resize_dir == 'tl': self.anchor_item = rect.bottomRight()
            elif self.resize_dir == 'tr': self.anchor_item = rect.bottomLeft()
            elif self.resize_dir == 'bl': self.anchor_item = rect.topRight()
            elif self.resize_dir == 'br': self.anchor_item = rect.topLeft()
            elif self.resize_dir == 't': self.anchor_item = QPointF(rect.center().x(), rect.bottom())
            elif self.resize_dir == 'b': self.anchor_item = QPointF(rect.center().x(), rect.top())
            elif self.resize_dir == 'l': self.anchor_item = QPointF(rect.right(), rect.center().y())
            elif self.resize_dir == 'r': self.anchor_item = QPointF(rect.left(), rect.center().y())

            self.anchor_scene = self.mapToScene(self.anchor_item)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # --- EJECUCIÓN DE GIRO (AHORA CON IMÁN) ---
        if getattr(self, 'is_rotating', False):
            mouse_scene_pos = event.scenePos()
            dy = mouse_scene_pos.y() - self.center_scene_pos.y()
            dx = mouse_scene_pos.x() - self.center_scene_pos.x()
            current_angle = math.degrees(math.atan2(dy, dx))
            
            angle_diff = current_angle - self.start_angle
            raw_angle = self.start_rotation + angle_diff
            
            # Buscamos el múltiplo de 90 más cercano
            nearest_90 = round(raw_angle / 90.0) * 90.0
            
            # Tolerancia magnética de 5 grados
            if abs(raw_angle - nearest_90) <= 5.0:
                final_angle = nearest_90
            else:
                final_angle = raw_angle
                
            self.setRotation(final_angle)
            event.accept()
            
        # --- EJECUCIÓN DE REDIMENSIONADO ---
        elif getattr(self, 'is_resizing', False):
            dx_scene = event.scenePos().x() - self.start_mouse_pos.x()
            dy_scene = event.scenePos().y() - self.start_mouse_pos.y()
            
            angle = math.radians(self.rotation())
            dx = dx_scene * math.cos(-angle) - dy_scene * math.sin(-angle)
            dy = dx_scene * math.sin(-angle) + dy_scene * math.cos(-angle)
            
            rect = super().boundingRect()
            start_w = rect.width() * self.start_scale_x
            start_h = rect.height() * self.start_scale_y
            
            new_w, new_h = start_w, start_h
            
            if 'l' in self.resize_dir: new_w = start_w - dx
            elif 'r' in self.resize_dir: new_w = start_w + dx
            if 't' in self.resize_dir: new_h = start_h - dy
            elif 'b' in self.resize_dir: new_h = start_h + dy
            
            new_w = max(20, min(new_w, 1000))
            new_h = max(20, min(new_h, 700))
            
            if self.resize_dir in ['tl', 'tr', 'bl', 'br']:
                aspect_ratio = rect.width() / rect.height() if rect.height() != 0 else 1
                if abs(dx) > abs(dy): new_h = new_w / aspect_ratio
                else: new_w = new_h * aspect_ratio
                    
            sx = new_w / rect.width()
            sy = new_h / rect.height()
            
            self.setTransform(QTransform().scale(sx, sy))
            
            new_anchor_scene = self.mapToScene(self.anchor_item)
            offset = self.anchor_scene - new_anchor_scene
            self.setPos(self.pos() + offset)
            
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, 'is_rotating', False):
            self.is_rotating = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        elif getattr(self, 'is_resizing', False):
            self.is_resizing = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class MemeImageItem(ResizableItemMixin, QGraphicsPixmapItem):
    def __init__(self, pixmap, item_id):
        super().__init__(pixmap)
        self.item_id = item_id
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setup_resizing() 

class MemeTextItem(ResizableItemMixin, QGraphicsTextItem):
    def __init__(self, text, item_id, update_callback):
        super().__init__(text)
        self.item_id = item_id
        self.update_callback = update_callback
        
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsItem
        
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        # --- SOLUCIÓN REAL: EL CLON TRASERO ---
        self.bg_text = QGraphicsTextItem(self)
        self.bg_text.setPos(0, 0)
        
        # ¡ESTA ES LA MAGIA QUE FALTABA! 
        # Obliga a Qt a dibujar este clon por DEBAJO de tu letra de color.
        self.bg_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent, True)
        self.bg_text.setZValue(-1) 
        
        # Hacemos que el clon sea un "fantasma" que no interfiera con el ratón
        self.bg_text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.bg_text.setAcceptHoverEvents(False)
        self.bg_text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.bg_text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.bg_text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsFocusable, False)
        
        # Propiedades de Color por defecto
        self.text_color = QColor("white")
        self.border_color = QColor("black")
        self.border_width = 2.0 
        
        self._aplicando_formato = False
        
        self.setup_resizing() 
        self.aplicar_formato() 
        self.document().contentsChanged.connect(self.on_text_changed)

    def aplicar_formato(self):
        if self._aplicando_formato: return
        self._aplicando_formato = True
        
        from PyQt6.QtGui import QTextCursor, QTextCharFormat, QPen, QBrush, QFont
        from PyQt6.QtCore import Qt
        
        cursor_real = self.textCursor()
        posicion = cursor_real.position()
        
        # 1. TEXTO TRASERO (Es el que hace crecer el borde hacia afuera)
        self.bg_text.setPlainText(self.toPlainText())
        cursor_bg = self.bg_text.textCursor()
        cursor_bg.select(QTextCursor.SelectionType.Document)
        
        formato_fondo = QTextCharFormat()
        formato_fondo.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        # El interior del clon trasero debe ser del mismo color que su borde para evitar huecos
        formato_fondo.setForeground(QBrush(self.border_color)) 
        
        if self.border_width > 0:
            # Multiplicamos x2 porque la mitad quedará escondida bajo la letra principal
            pen = QPen(self.border_color, self.border_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            formato_fondo.setTextOutline(pen)
        else:
            formato_fondo.setTextOutline(QPen(Qt.PenStyle.NoPen))
            
        cursor_bg.mergeCharFormat(formato_fondo)
        
        # 2. TEXTO FRONTAL (Tu letra principal, sin bordes para que no se "coma" el color)
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        
        formato_frente = QTextCharFormat()
        formato_frente.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        formato_frente.setForeground(QBrush(self.text_color))
        formato_frente.setTextOutline(QPen(Qt.PenStyle.NoPen)) # Frente 100% limpio
        
        cursor.mergeCharFormat(formato_frente)
        
        # Restaurar el cursor por si estás escribiendo
        if self.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction:
            cursor_real.setPosition(posicion)
            self.setTextCursor(cursor_real)
            
        self._aplicando_formato = False

    def on_text_changed(self):
        if self._aplicando_formato: return
        self.aplicar_formato() # Sincroniza el clon trasero instantáneamente al escribir
        self.setTransformOriginPoint(super().boundingRect().center())
        self.update_callback(self.item_id, self.toPlainText())

    def mouseDoubleClickEvent(self, event):
        from PyQt6.QtCore import Qt
        if self.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.setFocus()
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        from PyQt6.QtCore import Qt
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.aplicar_formato()
        super().focusOutEvent(event)
class LayerListWidget(QListWidget):
    """Lista de capas personalizada para detectar la tecla Suprimir"""
    def __init__(self, parent_tab):
        super().__init__()
        self.parent_tab = parent_tab

    def keyPressEvent(self, event):
        # Escucha la tecla Suprimir (Delete) o Retroceso (Backspace)
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.parent_tab.eliminar_capa()
        else:
            super().keyPressEvent(event)

class MemeCanvas(QGraphicsView):
    def __init__(self, parent_tab):
        super().__init__()
        self.parent_tab = parent_tab
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setSceneRect(0, 0, 1000, 700)
        self.setStyleSheet("background-color: #2b2b2b;") 
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                self.parent_tab.agregar_capa_imagen(url.toLocalFile(), event.position())
            event.acceptProposedAction()

    def keyPressEvent(self, event):
        from PyQt6.QtCore import Qt
        
        # --- NUEVO: Validar si estamos editando texto ---
        focus_item = self.scene.focusItem()
        is_editing_text = False
        if focus_item and hasattr(focus_item, 'textInteractionFlags'):
            if focus_item.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction:
                is_editing_text = True

        # Si el texto está activo, dejamos que el evento pase de largo para que borre letras
        if is_editing_text:
            super().keyPressEvent(event)
            return

        # --- COMPORTAMIENTO NORMAL DEL LIENZO ---
        # Borrar capa
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.parent_tab.eliminar_capa()
            
        # Pegar desde el portapapeles
        elif event.key() == Qt.Key.Key_V and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.parent_tab.pegar_desde_portapapeles()
            
        else:
            super().keyPressEvent(event)

class MemeTab(QWidget):
    def __init__(self):
        super().__init__()
        from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QWidget, QSpinBox
        from PyQt6.QtCore import Qt
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # --- ZONA IZQUIERDA: Barra Superior + Lienzo ---
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.top_bar = QWidget()
        self.top_bar.setFixedHeight(50)
        self.top_bar.setStyleSheet("background-color: #3d3d3d; border-radius: 8px;")
        self.top_layout = QHBoxLayout(self.top_bar)
        
        lbl_fondo = QLabel("Fondo del Lienzo:")
        lbl_fondo.setStyleSheet("color: white; font-weight: bold; padding-left: 10px;")
        self.top_layout.addWidget(lbl_fondo)
        
        self.btn_fondo_color = QPushButton("🎨 Color Sólido")
        self.btn_fondo_color.setStyleSheet("background-color: #555; color: white; padding: 5px 15px;")
        self.btn_fondo_color.clicked.connect(self.cambiar_fondo_color)
        self.top_layout.addWidget(self.btn_fondo_color)
        
        self.btn_fondo_img = QPushButton("🖼️ Subir Imagen")
        self.btn_fondo_img.setStyleSheet("background-color: #555; color: white; padding: 5px 15px;")
        self.btn_fondo_img.clicked.connect(self.cambiar_fondo_imagen)
        self.top_layout.addWidget(self.btn_fondo_img)
        
        self.btn_limpiar_fondo = QPushButton("🗑️ Limpiar")
        self.btn_limpiar_fondo.setStyleSheet("background-color: #d9534f; color: white; padding: 5px 15px; font-weight: bold;")
        self.btn_limpiar_fondo.clicked.connect(self.limpiar_fondo)
        self.top_layout.addWidget(self.btn_limpiar_fondo)
        
        self.top_layout.addStretch()
        self.left_layout.addWidget(self.top_bar)
        
        self.canvas = MemeCanvas(self)
        self.left_layout.addWidget(self.canvas)
        
        # --- ZONA DERECHA: Panel de Capas ---
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setFixedWidth(250)
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        
        lbl_capas = QLabel("CAPAS")
        lbl_capas.setStyleSheet("font-weight: bold; font-size: 16px; color: #333;")
        lbl_capas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(lbl_capas)
        
        lbl_instrucciones = QLabel("(Arrastra los nombres para reordenar\nDoble clic para editar texto\nArrastra bordes para redimensionar\nUsa Suprimir para borrar)")
        lbl_instrucciones.setStyleSheet("font-size: 11px; color: #666;")
        lbl_instrucciones.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(lbl_instrucciones)

        self.layer_list = LayerListWidget(self)
        self.layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layer_list.setStyleSheet("font-size: 14px; padding: 5px;")
        self.layer_list.model().rowsMoved.connect(self.actualizar_z_index)
        self.sidebar_layout.addWidget(self.layer_list)

        self.btn_add_text = QPushButton("Añadir Texto")
        self.btn_add_text.setFixedHeight(35)
        self.btn_add_text.clicked.connect(self.agregar_capa_texto)
        self.sidebar_layout.addWidget(self.btn_add_text)
        
        self.btn_delete = QPushButton("Eliminar Capa Seleccionada")
        self.btn_delete.setFixedHeight(35)
        self.btn_delete.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;")
        self.btn_delete.clicked.connect(self.eliminar_capa)
        self.sidebar_layout.addWidget(self.btn_delete)
        
        # --- SUB-PANEL DE HERRAMIENTAS DE TEXTO ---
        self.text_tools_widget = QWidget()
        self.text_tools_layout = QVBoxLayout(self.text_tools_widget)
        self.text_tools_layout.setContentsMargins(0, 15, 0, 0)
        
        lbl_texto_props = QLabel("PROPIEDADES DE TEXTO")
        lbl_texto_props.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")
        lbl_texto_props.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_tools_layout.addWidget(lbl_texto_props)
        
        self.btn_color_texto = QPushButton("Color de Letra")
        self.btn_color_texto.setFixedHeight(30)
        self.btn_color_texto.clicked.connect(self.cambiar_color_texto)
        self.text_tools_layout.addWidget(self.btn_color_texto)
        
        self.btn_color_borde = QPushButton("Color de Borde")
        self.btn_color_borde.setFixedHeight(30)
        self.btn_color_borde.clicked.connect(self.cambiar_color_borde)
        self.text_tools_layout.addWidget(self.btn_color_borde)
        
        # --- NUEVO: Control de Grosor del Borde ---
        self.grosor_layout = QHBoxLayout()
        lbl_grosor = QLabel("Grosor:")
        lbl_grosor.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
        self.grosor_spinbox = QSpinBox()
        self.grosor_spinbox.setRange(0, 25) # De 0 (sin borde) a 25 (muy grueso)
        self.grosor_spinbox.setValue(2)
        self.grosor_spinbox.valueChanged.connect(self.cambiar_grosor_borde)
        
        self.grosor_layout.addWidget(lbl_grosor)
        self.grosor_layout.addWidget(self.grosor_spinbox)
        self.text_tools_layout.addLayout(self.grosor_layout)
        
        self.sidebar_layout.addWidget(self.text_tools_widget)
        self.text_tools_widget.setVisible(False) 

        self.layout.addWidget(self.left_panel)
        self.layout.addWidget(self.sidebar_widget)

        self.items_dict = {} 
        self.layer_counter = 1
        self._sincronizando = False
        self.bg_item = None 
        self._actualizando_texto = False
        
        self.layer_list.itemSelectionChanged.connect(self.sincronizar_seleccion_desde_lista)
        self.canvas.scene.selectionChanged.connect(self.sincronizar_seleccion_desde_lienzo)
        self.layer_list.itemChanged.connect(self.actualizar_texto_desde_lista)

    # -------------------------------------------------------------
    # --- FUNCIONES DE DISEÑO DE TEXTO ---
    # -------------------------------------------------------------
    def cambiar_color_texto(self):
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtCore import Qt
        selected = self.layer_list.selectedItems()
        if not selected: return
        item_id = selected[0].data(Qt.ItemDataRole.UserRole)
        canvas_item = self.items_dict.get(item_id)
        
        if canvas_item and hasattr(canvas_item, 'text_color'):
            color = QColorDialog.getColor(canvas_item.text_color, self, "Elige el color de la letra")
            if color.isValid():
                canvas_item.text_color = color
                canvas_item.aplicar_formato()

    def cambiar_color_borde(self):
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtCore import Qt
        selected = self.layer_list.selectedItems()
        if not selected: return
        item_id = selected[0].data(Qt.ItemDataRole.UserRole)
        canvas_item = self.items_dict.get(item_id)
        
        if canvas_item and hasattr(canvas_item, 'border_color'):
            color = QColorDialog.getColor(canvas_item.border_color, self, "Elige el color del borde")
            if color.isValid():
                canvas_item.border_color = color
                canvas_item.aplicar_formato()

    def cambiar_grosor_borde(self, valor):
        """Aplica el valor numérico del selector al grosor del borde de la letra."""
        from PyQt6.QtCore import Qt
        selected = self.layer_list.selectedItems()
        if not selected: return
        item_id = selected[0].data(Qt.ItemDataRole.UserRole)
        canvas_item = self.items_dict.get(item_id)
        
        if canvas_item and hasattr(canvas_item, 'border_width'):
            canvas_item.border_width = float(valor)
            canvas_item.aplicar_formato()

    def evaluar_panel_texto(self, item_id):
        """Muestra el panel de herramientas y sincroniza el valor del grosor."""
        if item_id and item_id.startswith("txt_"):
            self.text_tools_widget.setVisible(True)
            
            # Sincronizamos el SpinBox con el grosor real de esa capa
            canvas_item = self.items_dict.get(item_id)
            if canvas_item and hasattr(canvas_item, 'border_width'):
                self.grosor_spinbox.blockSignals(True) # Evitar que dispare el evento cambiar_grosor_borde
                self.grosor_spinbox.setValue(int(canvas_item.border_width))
                self.grosor_spinbox.blockSignals(False)
        else:
            self.text_tools_widget.setVisible(False)

    # -------------------------------------------------------------
    # --- FUNCIONES DE SINCRONIZACIÓN Y SELECCIÓN ---
    # -------------------------------------------------------------
    def sincronizar_seleccion_desde_lista(self):
        from PyQt6.QtCore import Qt
        if self._sincronizando: return
        self._sincronizando = True
        
        self.canvas.scene.clearSelection()
        selected_items = self.layer_list.selectedItems()
        if selected_items:
            item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            canvas_item = self.items_dict.get(item_id)
            if canvas_item:
                canvas_item.setSelected(True)
            self.evaluar_panel_texto(item_id)
        else:
            self.evaluar_panel_texto(None)
                
        self._sincronizando = False

    def sincronizar_seleccion_desde_lienzo(self):
        from PyQt6.QtCore import Qt
        if self._sincronizando: return
        self._sincronizando = True
        
        selected_canvas_items = self.canvas.scene.selectedItems()
        if not selected_canvas_items:
            self.layer_list.clearSelection()
            self.evaluar_panel_texto(None)
        else:
            canvas_item = selected_canvas_items[0]
            if hasattr(canvas_item, 'item_id'):
                target_id = canvas_item.item_id
                self.evaluar_panel_texto(target_id)
                for i in range(self.layer_list.count()):
                    list_item = self.layer_list.item(i)
                    if list_item.data(Qt.ItemDataRole.UserRole) == target_id:
                        self.layer_list.setCurrentItem(list_item)
                        break
                        
        self._sincronizando = False

    def actualizar_nombre_texto(self, item_id, nuevo_texto):
        from PyQt6.QtCore import Qt
        if self._actualizando_texto: return
        self._actualizando_texto = True
        for i in range(self.layer_list.count()):
            list_item = self.layer_list.item(i)
            if list_item.data(Qt.ItemDataRole.UserRole) == item_id:
                texto_limpio = nuevo_texto.replace('\n', ' ')
                if len(texto_limpio) > 20: texto_limpio = texto_limpio[:17] + "..."
                list_item.setText(f"📝 {texto_limpio}")
                break
        self._actualizando_texto = False

    def actualizar_texto_desde_lista(self, list_item):
        from PyQt6.QtCore import Qt
        if self._actualizando_texto: return
        self._actualizando_texto = True
        
        item_id = list_item.data(Qt.ItemDataRole.UserRole)
        canvas_item = self.items_dict.get(item_id)
        
        if item_id and item_id.startswith("txt_") and canvas_item:
            nuevo_texto = list_item.text()
            texto_canvas = nuevo_texto
            if texto_canvas.startswith("📝 "): texto_canvas = texto_canvas[3:]
            canvas_item.setPlainText(texto_canvas)
            
            texto_limpio = texto_canvas.replace('\n', ' ')
            if len(texto_limpio) > 20: texto_limpio = texto_limpio[:17] + "..."
            list_item.setText(f"📝 {texto_limpio}")
            
        self._actualizando_texto = False

    # -------------------------------------------------------------
    # --- FUNCIONES RESTANTES (CAPAS, FONDO, PORTAPAPELES) ---
    # -------------------------------------------------------------
    def _registrar_y_mostrar_capa(self, graphics_item, item_id, nombre_capa):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QListWidgetItem
        self.canvas.scene.addItem(graphics_item)
        self.items_dict[item_id] = graphics_item
        
        list_item = QListWidgetItem(nombre_capa)
        list_item.setData(Qt.ItemDataRole.UserRole, item_id) 
        list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsEditable)
        
        self.layer_list.insertItem(0, list_item) 
        self.layer_counter += 1
        self.actualizar_z_index()
        self.layer_list.setCurrentItem(list_item)

    def agregar_capa_imagen(self, ruta, pos):
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        import os
        
        pixmap = QPixmap(ruta)
        if not pixmap.isNull():
            if pixmap.width() > 1000 or pixmap.height() > 700:
                pixmap = pixmap.scaled(
                    1000, 700, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
            
            item_id = f"img_{self.layer_counter}"
            nombre_archivo = os.path.basename(ruta)
            nombre_capa = f"🖼️ {nombre_archivo}"
            
            # Nota: Asume que MemeImageItem ya está importada / definida arriba en tu archivo
            item = MemeImageItem(pixmap, item_id)
            scene_pos = self.canvas.mapToScene(pos.toPoint())
            item.setPos(scene_pos)
            
            self._registrar_y_mostrar_capa(item, item_id, nombre_capa)

    def agregar_capa_texto(self):
        item_id = f"txt_{self.layer_counter}"
        texto_inicial = "DOBLE CLIC AQUÍ"
        nombre_capa = f"📝 {texto_inicial}"
        
        # Nota: Asume que MemeTextItem ya está importada / definida arriba en tu archivo
        item = MemeTextItem(texto_inicial, item_id, self.actualizar_nombre_texto)
        item.setPos(400, 300)
        
        self._registrar_y_mostrar_capa(item, item_id, nombre_capa)

    def eliminar_capa(self):
        from PyQt6.QtCore import Qt
        selected_items = self.layer_list.selectedItems()
        if not selected_items: return
            
        list_item = selected_items[0]
        item_id = list_item.data(Qt.ItemDataRole.UserRole)
        
        canvas_item = self.items_dict.get(item_id)
        if canvas_item:
            self.canvas.scene.removeItem(canvas_item)
            del self.items_dict[item_id]
            
        self.layer_list.takeItem(self.layer_list.row(list_item))

    def actualizar_z_index(self):
        from PyQt6.QtCore import Qt
        total_items = self.layer_list.count()
        for i in range(total_items):
            list_item = self.layer_list.item(i)
            item_id = list_item.data(Qt.ItemDataRole.UserRole)
            canvas_item = self.items_dict.get(item_id)
            if canvas_item: canvas_item.setZValue(total_items - i)

    def cambiar_fondo_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid(): self.aplicar_fondo(color=color)

    def cambiar_fondo_imagen(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Fondo", "", "Images (*.png *.jpg *.jpeg)")
        if path: self.aplicar_fondo(ruta=path)

    def aplicar_fondo(self, color=None, ruta=None):
        from PyQt6.QtWidgets import QGraphicsRectItem
        from PyQt6.QtGui import QBrush, QPixmap
        from PyQt6.QtCore import Qt
        
        if not self.bg_item:
            self.bg_item = QGraphicsRectItem(0, 0, 1000, 700)
            self.bg_item.setZValue(-9999) 
            self.canvas.scene.addItem(self.bg_item)
            
        if color: self.bg_item.setBrush(QBrush(color))
        elif ruta:
            pixmap = QPixmap(ruta).scaled(
                1000, 700, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.bg_item.setBrush(QBrush(pixmap))

    def limpiar_fondo(self):
        if self.bg_item:
            self.canvas.scene.removeItem(self.bg_item)
            self.bg_item = None

    def pegar_desde_portapapeles(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QPoint
        
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            qimage = clipboard.image()
            if not qimage.isNull():
                pixmap = QPixmap.fromImage(qimage)
                self._procesar_y_agregar_pixmap(pixmap, "Imagen Pegada")
        elif mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile(): self.agregar_capa_imagen(url.toLocalFile(), QPoint(500, 350))

    def _procesar_y_agregar_pixmap(self, pixmap, nombre_base):
        from PyQt6.QtCore import Qt
        if not pixmap.isNull():
            if pixmap.width() > 1000 or pixmap.height() > 700:
                pixmap = pixmap.scaled(
                    1000, 700, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            item_id = f"img_{self.layer_counter}"
            nombre_capa = f"🖼️ {nombre_base}"
            
            item = MemeImageItem(pixmap, item_id)
            center_x = (1000 - pixmap.width()) / 2
            center_y = (700 - pixmap.height()) / 2
            item.setPos(center_x, center_y)
            
            self._registrar_y_mostrar_capa(item, item_id, nombre_capa)

class MemeStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meme Studio & IA Background Remover")
        self.resize(1300, 825)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_meme = MemeTab()
        self.tab_ia = BackgroundRemoverTab()

        self.tabs.addTab(self.tab_meme, "Generador de Memes")
        self.tabs.addTab(self.tab_ia, "Quitar Fondo")

        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MemeStudioApp()
    window.show()
    sys.exit(app.exec())