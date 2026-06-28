import React, { useState, useEffect, useRef } from 'react';
import './App.css';

interface Layer {
  id: string;
  type: 'image' | 'text';
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number; // en grados
  zIndex: number;
  // Campos de Texto
  text?: string;
  color?: string;
  borderColor?: string;
  borderWidth?: number;
  fontSize?: number;
  fontFamily?: string;
  // Campos de Imagen
  imageUrl?: string;
}

type TabType = 'remover' | 'meme';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('remover');
  const [apiUrl, setApiUrl] = useState<string>(() => {
    return localStorage.getItem('hf_space_url') || import.meta.env.VITE_API_URL || '';
  });
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [tempApiUrl, setTempApiUrl] = useState<string>(apiUrl);

  // --- Estados de Quitar Fondo ---
  const [sourceImage, setSourceImage] = useState<string | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- Estados del Generador de Memes ---
  const [canvasWidth, setCanvasWidth] = useState<number>(1000);
  const [canvasHeight, setCanvasHeight] = useState<number>(700);
  const [layers, setLayers] = useState<Layer[]>([]);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [canvasBackground, setCanvasBackground] = useState<{
    type: 'color' | 'image';
    value: string;
  }>({ type: 'color', value: '#2b2b2b' });
  const [preset, setPreset] = useState<string>('original');
  const [layerCounter, setLayerCounter] = useState<number>(1);

  // --- Referencias y Responsividad ---
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const [canvasScale, setCanvasScale] = useState<number>(1);
  const canvasRef = useRef<HTMLDivElement>(null);
  const bgFileInputRef = useRef<HTMLInputElement>(null);
  const layerFileInputRef = useRef<HTMLInputElement>(null);

  // Lógica de arrastre de capas
  const [activeAction, setActiveAction] = useState<{
    type: 'drag' | 'resize' | 'rotate';
    handle?: 'tl' | 'tr' | 'bl' | 'br';
    layerId: string;
    startX: number;
    startY: number;
    startLayerX: number;
    startLayerY: number;
    startLayerW: number;
    startLayerH: number;
    startLayerRot: number;
  } | null>(null);

  // Guardar API URL en localStorage
  const handleSaveSettings = () => {
    localStorage.setItem('hf_space_url', tempApiUrl);
    setApiUrl(tempApiUrl);
    setShowSettings(false);
  };

  // Ajustar la escala del lienzo responsivo
  useEffect(() => {
    const updateScale = () => {
      if (!canvasContainerRef.current) return;
      const containerWidth = canvasContainerRef.current.clientWidth;
      const padding = 40; // Margen interno
      const availableWidth = containerWidth - padding;
      
      if (availableWidth < canvasWidth) {
        setCanvasScale(availableWidth / canvasWidth);
      } else {
        setCanvasScale(1);
      }
    };

    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, [canvasWidth, activeTab]);

  // Manejar el cambio de presets de tamaño del lienzo
  const applyPreset = (presetName: string) => {
    setPreset(presetName);
    if (presetName === 'original') {
      setCanvasWidth(1000);
      setCanvasHeight(700);
    } else if (presetName === '1:1') {
      setCanvasWidth(800);
      setCanvasHeight(800);
    } else if (presetName === '16:9') {
      setCanvasWidth(1280);
      setCanvasHeight(720);
    } else if (presetName === '9:16') {
      setCanvasWidth(720);
      setCanvasHeight(1280);
    }
  };

  // -------------------------------------------------------------
  // --- LÓGICA DE QUITAR FONDO (API) ---
  // -------------------------------------------------------------
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      loadSourceImage(files[0]);
    }
  };

  const loadSourceImage = (file: File) => {
    if (!file.type.startsWith('image/')) {
      alert('Por favor, selecciona un archivo de imagen.');
      return;
    }
    setSourceFile(file);
    setResultImage(null);
    setErrorMsg(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      setSourceImage(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      loadSourceImage(files[0]);
    }
  };

  const handleRemoveBackground = async () => {
    if (!sourceFile) return;

    if (!apiUrl) {
      setShowSettings(true);
      alert('Por favor, configura la URL de tu Space de Hugging Face primero.');
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);
    setProcessingStatus('Enviando imagen al servidor...');

    try {
      const formData = new FormData();
      formData.append('file', sourceFile);

      // Limpiar URL por si tiene barras al final
      const cleanUrl = apiUrl.replace(/\/$/, '');
      
      setProcessingStatus('Procesando fondo con BiRefNet (esto puede tomar unos segundos)...');
      
      const response = await fetch(`${cleanUrl}/remove-bg`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Error del servidor (${response.status})`);
      }

      setProcessingStatus('Generando archivo final...');
      const blob = await response.blob();
      const resultUrl = URL.createObjectURL(blob);
      setResultImage(resultUrl);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Error al comunicarse con el Space. Asegúrate de que la URL sea correcta y el Space esté activo.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownloadResult = () => {
    if (!resultImage) return;
    const link = document.createElement('a');
    link.href = resultImage;
    link.download = `sin-fondo-${Date.now()}.png`;
    link.click();
  };

  const handleSendToCanvas = () => {
    if (!resultImage) return;
    
    // Crear una nueva capa de imagen
    const newLayer: Layer = {
      id: `img_${layerCounter}`,
      type: 'image',
      name: `🖼️ Imagen Recortada ${layerCounter}`,
      x: 100,
      y: 100,
      width: 400,
      height: 400,
      rotation: 0,
      zIndex: layers.length + 1,
      imageUrl: resultImage,
    };

    setLayers([newLayer, ...layers]);
    setLayerCounter(prev => prev + 1);
    setSelectedLayerId(newLayer.id);
    
    // Cambiar a la pestaña de memes
    setActiveTab('meme');
  };

  const handleResetRemover = () => {
    setSourceImage(null);
    setSourceFile(null);
    setResultImage(null);
    setErrorMsg(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // -------------------------------------------------------------
  // --- LÓGICA DEL GENERADOR DE MEMES (Canvas) ---
  // -------------------------------------------------------------
  const handleAddText = () => {
    const newLayer: Layer = {
      id: `txt_${layerCounter}`,
      type: 'text',
      name: `📝 Texto ${layerCounter}`,
      x: canvasWidth / 2 - 150,
      y: canvasHeight / 2 - 50,
      width: 300,
      height: 100,
      rotation: 0,
      zIndex: layers.length + 1,
      text: 'DOBLE CLIC AQUÍ',
      color: '#ffffff',
      borderColor: '#000000',
      borderWidth: 2,
      fontSize: 40,
      fontFamily: 'Impact',
    };

    setLayers([newLayer, ...layers]);
    setLayerCounter(prev => prev + 1);
    setSelectedLayerId(newLayer.id);
  };

  const handleAddImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const newLayer: Layer = {
          id: `img_${layerCounter}`,
          type: 'image',
          name: `🖼️ ${files[0].name}`,
          x: canvasWidth / 2 - 200,
          y: canvasHeight / 2 - 200,
          width: 400,
          height: 400,
          rotation: 0,
          zIndex: layers.length + 1,
          imageUrl: event.target?.result as string,
        };
        setLayers([newLayer, ...layers]);
        setLayerCounter(prev => prev + 1);
        setSelectedLayerId(newLayer.id);
      };
      reader.readAsDataURL(files[0]);
    }
  };

  const handleDeleteLayer = (idToDelete: string | null) => {
    const targetId = idToDelete || selectedLayerId;
    if (!targetId) return;
    
    setLayers(prev => prev.filter(layer => layer.id !== targetId));
    if (selectedLayerId === targetId) {
      setSelectedLayerId(null);
    }
  };

  const handleZIndexChange = (direction: 'up' | 'down', id: string) => {
    setLayers(prev => {
      const sorted = [...prev].sort((a, b) => b.zIndex - a.zIndex); // ZIndex descendente (capa de arriba primero)
      const index = sorted.findIndex(l => l.id === id);
      if (index === -1) return prev;

      if (direction === 'up' && index > 0) {
        // Intercambiar Z-Index con el de arriba en la lista (que se dibuja después, es decir, tiene mayor ZIndex)
        const temp = sorted[index].zIndex;
        sorted[index].zIndex = sorted[index - 1].zIndex;
        sorted[index - 1].zIndex = temp;
      } else if (direction === 'down' && index < sorted.length - 1) {
        // Intercambiar Z-Index con el de abajo en la lista
        const temp = sorted[index].zIndex;
        sorted[index].zIndex = sorted[index + 1].zIndex;
        sorted[index + 1].zIndex = temp;
      }
      return sorted;
    });
  };

  const handleBgColorChange = (color: string) => {
    setCanvasBackground({ type: 'color', value: color });
  };

  const handleBgImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setCanvasBackground({
          type: 'image',
          value: event.target?.result as string,
        });
      };
      reader.readAsDataURL(files[0]);
    }
  };

  const handleClearBg = () => {
    setCanvasBackground({ type: 'color', value: '#2b2b2b' });
  };

  const updateSelectedLayer = (updates: Partial<Layer>) => {
    if (!selectedLayerId) return;
    setLayers(prev => prev.map(layer => {
      if (layer.id === selectedLayerId) {
        const updated = { ...layer, ...updates };
        // Si cambia el texto, actualizamos el nombre de la capa
        if (updates.text !== undefined && layer.type === 'text') {
          let cleanText = updates.text.replace(/\n/g, ' ');
          if (cleanText.length > 20) cleanText = cleanText.substring(0, 17) + '...';
          updated.name = `📝 ${cleanText || 'Vacío'}`;
        }
        return updated;
      }
      return layer;
    }));
  };

  const selectedLayer = layers.find(l => l.id === selectedLayerId);

  // -------------------------------------------------------------
  // --- MATEMÁTICAS DE ARRASTRE, REDIMENSIONADO Y ROTACIÓN ---
  // -------------------------------------------------------------
  const handleLayerMouseDown = (e: React.MouseEvent, layerId: string, handle?: 'tl' | 'tr' | 'bl' | 'br' | 'rot') => {
    e.preventDefault();
    e.stopPropagation();
    
    setSelectedLayerId(layerId);

    const layer = layers.find(l => l.id === layerId);
    if (!layer) return;

    if (handle === 'rot') {
      setActiveAction({
        type: 'rotate',
        layerId,
        startX: e.clientX,
        startY: e.clientY,
        startLayerX: layer.x,
        startLayerY: layer.y,
        startLayerW: layer.width,
        startLayerH: layer.height,
        startLayerRot: layer.rotation,
      });
    } else if (handle) {
      setActiveAction({
        type: 'resize',
        handle,
        layerId,
        startX: e.clientX,
        startY: e.clientY,
        startLayerX: layer.x,
        startLayerY: layer.y,
        startLayerW: layer.width,
        startLayerH: layer.height,
        startLayerRot: layer.rotation,
      });
    } else {
      setActiveAction({
        type: 'drag',
        layerId,
        startX: e.clientX,
        startY: e.clientY,
        startLayerX: layer.x,
        startLayerY: layer.y,
        startLayerW: layer.width,
        startLayerH: layer.height,
        startLayerRot: layer.rotation,
      });
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!activeAction || !canvasRef.current) return;

      const layer = layers.find(l => l.id === activeAction.layerId);
      if (!layer) return;

      const canvasRect = canvasRef.current.getBoundingClientRect();
      
      // Coordenadas actuales del ratón escaladas
      const mx = (e.clientX - canvasRect.left) / canvasScale;
      const my = (e.clientY - canvasRect.top) / canvasScale;

      if (activeAction.type === 'drag') {
        const dx = (e.clientX - activeAction.startX) / canvasScale;
        const dy = (e.clientY - activeAction.startY) / canvasScale;
        
        let newX = activeAction.startLayerX + dx;
        let newY = activeAction.startLayerY + dy;

        // Comportamiento de bordes pegajosos (Sticky borders)
        const RESIST_ZONE = 25;
        if (Math.abs(newX) < RESIST_ZONE) newX = 0;
        if (Math.abs(newX + layer.width - canvasWidth) < RESIST_ZONE) newX = canvasWidth - layer.width;
        if (Math.abs(newY) < RESIST_ZONE) newY = 0;
        if (Math.abs(newY + layer.height - canvasHeight) < RESIST_ZONE) newY = canvasHeight - layer.height;

        setLayers(prev => prev.map(l => {
          if (l.id === layer.id) {
            return { ...l, x: newX, y: newY };
          }
          return l;
        }));
      } 
      else if (activeAction.type === 'rotate') {
        // Centro del lienzo
        const cx = layer.x + layer.width / 2;
        const cy = layer.y + layer.height / 2;

        const dy = my - cy;
        const dx = mx - cx;
        
        // Sumamos 90 porque el tirador de rotación está arriba (vector 0, -h/2)
        let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
        
        // Comportamiento magnético a múltiplos de 90° con tolerancia de 5°
        const nearest90 = Math.round(angle / 90) * 90;
        if (Math.abs(angle - nearest90) <= 5) {
          angle = nearest90;
        }

        setLayers(prev => prev.map(l => {
          if (l.id === layer.id) {
            return { ...l, rotation: angle };
          }
          return l;
        }));
      } 
      else if (activeAction.type === 'resize' && activeAction.handle) {
        const rad = (activeAction.startLayerRot * Math.PI) / 180;
        const cos = Math.cos(rad);
        const sin = Math.sin(rad);

        // Identificar punto de anclaje local
        let pxLocal = 0;
        let pyLocal = 0;
        if (activeAction.handle === 'br') { pxLocal = 0; pyLocal = 0; } // Anclaje top-left
        else if (activeAction.handle === 'bl') { pxLocal = activeAction.startLayerW; pyLocal = 0; } // Anclaje top-right
        else if (activeAction.handle === 'tr') { pxLocal = 0; pyLocal = activeAction.startLayerH; } // Anclaje bottom-left
        else if (activeAction.handle === 'tl') { pxLocal = activeAction.startLayerW; pyLocal = activeAction.startLayerH; } // Anclaje bottom-right

        // Calcular el punto de anclaje en el canvas (coordenadas del mundo)
        const cx = activeAction.startLayerX + activeAction.startLayerW / 2;
        const cy = activeAction.startLayerY + activeAction.startLayerH / 2;
        const pxCentered = pxLocal - activeAction.startLayerW / 2;
        const pyCentered = pyLocal - activeAction.startLayerH / 2;

        const anchorX = cx + pxCentered * cos - pyCentered * sin;
        const anchorY = cy + pxCentered * sin + pyCentered * cos;

        // Vector desde el anclaje hasta el ratón
        const vx = mx - anchorX;
        const vy = my - anchorY;

        // Proyectar vector del ratón en el sistema de coordenadas de la capa
        const projX = vx * cos + vy * sin;
        const projY = -vx * sin + vy * cos;

        let w = activeAction.startLayerW;
        let h = activeAction.startLayerH;

        if (activeAction.handle === 'br') { w = projX; h = projY; }
        else if (activeAction.handle === 'bl') { w = -projX; h = projY; }
        else if (activeAction.handle === 'tr') { w = projX; h = -projY; }
        else if (activeAction.handle === 'tl') { w = -projX; h = -projY; }

        // Mantener relación de aspecto para imágenes
        if (layer.type === 'image') {
          const aspect = activeAction.startLayerW / activeAction.startLayerH;
          if (Math.abs(w - activeAction.startLayerW) > Math.abs(h - activeAction.startLayerH)) {
            h = w / aspect;
          } else {
            w = h * aspect;
          }
        }

        // Limitar dimensiones mínimas
        w = Math.max(20, w);
        h = Math.max(20, h);

        // Calcular nueva posición top-left del lienzo usando la fórmula del anclaje inverso
        let newX = 0;
        let newY = 0;

        if (activeAction.handle === 'br') { // pxLocal = 0, pyLocal = 0
          newX = anchorX - w / 2 - (-w / 2) * cos + (-h / 2) * sin;
          newY = anchorY - h / 2 - (-w / 2) * sin - (-h / 2) * cos;
        } else if (activeAction.handle === 'bl') { // pxLocal = w, pyLocal = 0
          newX = anchorX - w / 2 - (w - w / 2) * cos + (-h / 2) * sin;
          newY = anchorY - h / 2 - (w - w / 2) * sin - (-h / 2) * cos;
        } else if (activeAction.handle === 'tr') { // pxLocal = 0, pyLocal = h
          newX = anchorX - w / 2 - (-w / 2) * cos + (h - h / 2) * sin;
          newY = anchorY - h / 2 - (-w / 2) * sin - (h - h / 2) * cos;
        } else if (activeAction.handle === 'tl') { // pxLocal = w, pyLocal = h
          newX = anchorX - w / 2 - (w - w / 2) * cos + (h - h / 2) * sin;
          newY = anchorY - h / 2 - (w - w / 2) * sin - (h - h / 2) * cos;
        }

        setLayers(prev => prev.map(l => {
          if (l.id === layer.id) {
            return {
              ...l,
              width: w,
              height: h,
              x: newX,
              y: newY,
            };
          }
          return l;
        }));
      }
    };

    const handleMouseUp = () => {
      setActiveAction(null);
    };

    if (activeAction) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [activeAction, canvasScale, canvasWidth, canvasHeight, layers]);

  // Deseleccionar al hacer clic fuera del lienzo
  const handleCanvasContainerMouseDown = () => {
    setSelectedLayerId(null);
  };

  // -------------------------------------------------------------
  // --- EXPORTAR MEME A IMAGEN REAL (Canvas 2D) ---
  // -------------------------------------------------------------
  const loadImageAsync = (src: string): Promise<HTMLImageElement> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous'; // Evitar problemas de origen cruzado (canvas contaminado)
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(`No se pudo cargar la imagen: ${src}`));
      img.src = src;
    });
  };

  const handleExportMeme = async () => {
    setIsProcessing(true);
    setProcessingStatus('Generando imagen de alta resolución...');

    try {
      const canvas = document.createElement('canvas');
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('No se pudo obtener el contexto 2D del Canvas');

      // 1. Dibujar el fondo
      if (canvasBackground.type === 'color') {
        ctx.fillStyle = canvasBackground.value;
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);
      } else if (canvasBackground.type === 'image' && canvasBackground.value) {
        try {
          const bgImg = await loadImageAsync(canvasBackground.value);
          ctx.drawImage(bgImg, 0, 0, canvasWidth, canvasHeight);
        } catch (e) {
          console.error("Error al cargar la imagen de fondo", e);
          ctx.fillStyle = '#2b2b2b';
          ctx.fillRect(0, 0, canvasWidth, canvasHeight);
        }
      }

      // 2. Dibujar las capas en orden inverso de Z-Index (ZIndex ascendente)
      const sortedLayers = [...layers].sort((a, b) => a.zIndex - b.zIndex);

      for (const layer of sortedLayers) {
        ctx.save();
        
        // Mover el origen de coordenadas al centro de la capa
        const cx = layer.x + layer.width / 2;
        const cy = layer.y + layer.height / 2;
        ctx.translate(cx, cy);
        
        // Rotar
        ctx.rotate((layer.rotation * Math.PI) / 180);

        if (layer.type === 'image' && layer.imageUrl) {
          try {
            const img = await loadImageAsync(layer.imageUrl);
            ctx.drawImage(img, -layer.width / 2, -layer.height / 2, layer.width, layer.height);
          } catch (e) {
            console.error("Error al cargar la imagen de la capa", layer.id, e);
          }
        } 
        else if (layer.type === 'text' && layer.text) {
          ctx.font = `bold ${layer.fontSize || 40}px ${layer.fontFamily || 'Impact'}`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          const lines = layer.text.split('\n');
          const fontSize = layer.fontSize || 40;
          const lineHeight = fontSize * 1.1;
          const startY = -((lines.length - 1) * lineHeight) / 2;

          lines.forEach((line, index) => {
            const y = startY + index * lineHeight;

            // Dibujar el borde del clon trasero
            if (layer.borderWidth && layer.borderWidth > 0) {
              ctx.strokeStyle = layer.borderColor || '#000000';
              ctx.lineWidth = layer.borderWidth * 2; // se multiplica por 2 ya que strokeText se expande hacia adentro y afuera
              ctx.lineJoin = 'round';
              ctx.lineCap = 'round';
              ctx.strokeText(line, 0, y);
            }

            // Dibujar el frente
            ctx.fillStyle = layer.color || '#ffffff';
            ctx.fillText(line, 0, y);
          });
        }

        ctx.restore();
      }

      // 3. Descargar
      const dataUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `meme-${Date.now()}.png`;
      link.click();
    } catch (err: any) {
      console.error(err);
      alert(`Error al exportar: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResetCanvas = () => {
    if (window.confirm('¿Estás seguro de que quieres borrar todo el lienzo?')) {
      setLayers([]);
      setCanvasBackground({ type: 'color', value: '#2b2b2b' });
      setSelectedLayerId(null);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="title-container">
          <h1>Meme Studio & IA Background Remover</h1>
        </div>

        <div className="header-actions">
          <nav className="tabs-header">
            <button 
              className={`tab-btn ${activeTab === 'remover' ? 'active' : ''}`}
              onClick={() => setActiveTab('remover')}
            >
              ✂️ Quitar Fondo
            </button>
            <button 
              className={`tab-btn ${activeTab === 'meme' ? 'active' : ''}`}
              onClick={() => setActiveTab('meme')}
            >
              🖼️ Generador de Memes
            </button>
          </nav>
          
          <button 
            className="icon-btn" 
            onClick={() => { setTempApiUrl(apiUrl); setShowSettings(true); }}
            title="Configurar URL del Servidor"
            style={{ fontSize: '20px' }}
          >
            ⚙️
          </button>
        </div>
      </header>

      <main className="main-content">
        {/* --- PESTAÑA: QUITAR FONDO --- */}
        {activeTab === 'remover' && (
          <div className="bg-remover-container animate-fade-in">
            {/* Panel de imagen origen */}
            <div 
              className={`panel ${!sourceImage ? 'interactive' : ''}`}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => !sourceImage && fileInputRef.current?.click()}
            >
              <span className="panel-title">Original (Antes)</span>
              
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                accept="image/*" 
                style={{ display: 'none' }} 
              />

              {sourceImage ? (
                <>
                  <img src={sourceImage} alt="Antes" className="preview-image" />
                  <div className="actions-row">
                    <button className="btn btn-secondary" onClick={handleResetRemover}>
                      🗑️ Reiniciar
                    </button>
                    {!resultImage && (
                      <button 
                        className="btn btn-primary" 
                        onClick={handleRemoveBackground}
                        disabled={isProcessing}
                      >
                        ⚡ Quitar Fondo
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <div className="upload-placeholder">
                  <div className="upload-icon">📤</div>
                  <h3>Arrastra tu imagen aquí</h3>
                  <p>o haz clic para buscar en tu dispositivo</p>
                </div>
              )}

              {isProcessing && (
                <div className="loading-overlay">
                  <div className="spinner"></div>
                  <span className="loading-text">{processingStatus}</span>
                  <span className="loading-subtext">Utilizando ZhengPeng7/BiRefNet</span>
                </div>
              )}
            </div>

            {/* Panel de imagen resultado */}
            <div className="panel transparency-pattern">
              <span className="panel-title">Sin Fondo (Después)</span>

              {resultImage ? (
                <>
                  <img src={resultImage} alt="Después" className="preview-image" />
                  <div className="actions-row">
                    <button className="btn btn-secondary" onClick={handleDownloadResult}>
                      📥 Guardar PNG
                    </button>
                    <button className="btn btn-accent" onClick={handleSendToCanvas}>
                      🎨 Enviar al Editor de Memes →
                    </button>
                  </div>
                </>
              ) : errorMsg ? (
                <div className="upload-placeholder" style={{ color: 'var(--danger)', padding: '20px' }}>
                  <div style={{ fontSize: '48px' }}>⚠️</div>
                  <h3>Error al procesar</h3>
                  <p style={{ maxWidth: '350px', fontSize: '13px', marginTop: '10px' }}>{errorMsg}</p>
                  <button className="btn btn-secondary" style={{ marginTop: '15px' }} onClick={() => setErrorMsg(null)}>
                    Reintentar
                  </button>
                </div>
              ) : (
                <div className="upload-placeholder" style={{ opacity: 0.6 }}>
                  <div style={{ fontSize: '48px' }}>✨</div>
                  <h3>El resultado aparecerá aquí</h3>
                  <p>Sube una imagen y haz clic en Quitar Fondo</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* --- PESTAÑA: GENERADOR DE MEMES --- */}
        {activeTab === 'meme' && (
          <div className="meme-studio-container animate-fade-in">
            {/* Zona del Lienzo */}
            <div className="canvas-area-wrapper" ref={canvasContainerRef}>
              <div className="canvas-size-controls">
                <span>Tamaño:</span>
                <button className={`preset-btn ${preset === 'original' ? 'active' : ''}`} onClick={() => applyPreset('original')}>1000x700</button>
                <button className={`preset-btn ${preset === '1:1' ? 'active' : ''}`} onClick={() => applyPreset('1:1')}>1:1 (Post)</button>
                <button className={`preset-btn ${preset === '16:9' ? 'active' : ''}`} onClick={() => applyPreset('16:9')}>16:9</button>
                <button className={`preset-btn ${preset === '9:16' ? 'active' : ''}`} onClick={() => applyPreset('9:16')}>9:16 (Story)</button>
                
                <div className="canvas-size-input-group" style={{ marginLeft: '10px' }}>
                  <input 
                    type="number" 
                    value={canvasWidth} 
                    onChange={(e) => { setCanvasWidth(Math.max(100, Number(e.target.value))); setPreset('custom'); }} 
                    placeholder="Ancho"
                  />
                  <span>x</span>
                  <input 
                    type="number" 
                    value={canvasHeight} 
                    onChange={(e) => { setCanvasHeight(Math.max(100, Number(e.target.value))); setPreset('custom'); }} 
                    placeholder="Alto"
                  />
                  <span>px</span>
                </div>
              </div>

              <div className="responsive-canvas-container" onMouseDown={handleCanvasContainerMouseDown}>
                <div 
                  className="canvas-outer"
                  style={{
                    width: `${canvasWidth}px`,
                    height: `${canvasHeight}px`,
                    transform: `scale(${canvasScale})`,
                    transformOrigin: 'center center',
                    margin: `${((canvasHeight * canvasScale - canvasHeight) / 2)}px ${((canvasWidth * canvasScale - canvasWidth) / 2)}px`
                  }}
                >
                  <div 
                    ref={canvasRef}
                    className="canvas-inner"
                    style={{
                      backgroundColor: canvasBackground.type === 'color' ? canvasBackground.value : 'transparent',
                      backgroundImage: canvasBackground.type === 'image' ? `url(${canvasBackground.value})` : 'none',
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                    }}
                  >
                    {/* Render de Capas */}
                    {[...layers].sort((a, b) => a.zIndex - b.zIndex).map(layer => {
                      const isSelected = layer.id === selectedLayerId;
                      return (
                        <div
                          key={layer.id}
                          className={`canvas-layer ${isSelected ? 'selected' : ''}`}
                          style={{
                            left: `${layer.x}px`,
                            top: `${layer.y}px`,
                            width: `${layer.width}px`,
                            height: `${layer.height}px`,
                            transform: `rotate(${layer.rotation}deg)`,
                            zIndex: layer.zIndex,
                          }}
                          onMouseDown={(e) => handleLayerMouseDown(e, layer.id)}
                        >
                          {layer.type === 'image' && layer.imageUrl && (
                            <img 
                              src={layer.imageUrl} 
                              alt={layer.name} 
                              style={{ width: '100%', height: '100%', objectFit: 'fill', pointerEvents: 'none' }}
                            />
                          )}

                          {layer.type === 'text' && (
                            <div style={{ position: 'relative', width: '100%', height: '100%' }}>
                              {/* Texto trasero (Borde/Stroke) */}
                              {layer.borderWidth && layer.borderWidth > 0 && (
                                <div style={{
                                  position: 'absolute',
                                  top: 0,
                                  left: 0,
                                  width: '100%',
                                  height: '100%',
                                  color: layer.borderColor,
                                  WebkitTextStroke: `${layer.borderWidth * 2}px ${layer.borderColor}`,
                                  fontFamily: layer.fontFamily,
                                  fontSize: `${layer.fontSize}px`,
                                  fontWeight: 'bold',
                                  textAlign: 'center',
                                  whiteSpace: 'pre-wrap',
                                  lineHeight: 1.1,
                                  display: 'flex',
                                  justifyContent: 'center',
                                  alignItems: 'center',
                                }}>
                                  {layer.text}
                                </div>
                              )}
                              {/* Texto delantero (Relleno) */}
                              <div style={{
                                position: 'absolute',
                                top: 0,
                                  left: 0,
                                  width: '100%',
                                  height: '100%',
                                color: layer.color,
                                fontFamily: layer.fontFamily,
                                fontSize: `${layer.fontSize}px`,
                                fontWeight: 'bold',
                                textAlign: 'center',
                                whiteSpace: 'pre-wrap',
                                lineHeight: 1.1,
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                              }}>
                                {layer.text}
                              </div>
                            </div>
                          )}

                          {/* Tiradores de edición cuando está seleccionada */}
                          {isSelected && (
                            <>
                              <div className="handle handle-tl" onMouseDown={(e) => handleLayerMouseDown(e, layer.id, 'tl')} />
                              <div className="handle handle-tr" onMouseDown={(e) => handleLayerMouseDown(e, layer.id, 'tr')} />
                              <div className="handle handle-bl" onMouseDown={(e) => handleLayerMouseDown(e, layer.id, 'bl')} />
                              <div className="handle handle-br" onMouseDown={(e) => handleLayerMouseDown(e, layer.id, 'br')} />
                              
                              <div className="handle-rot-line" />
                              <div className="handle-rot" onMouseDown={(e) => handleLayerMouseDown(e, layer.id, 'rot')} />
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* Barra lateral de control */}
            <aside className="control-sidebar">
              {/* Acciones principales */}
              <div className="sidebar-section">
                <span className="section-title">Añadir Capas</span>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button className="btn btn-primary" style={{ flex: 1, padding: '10px' }} onClick={handleAddText}>
                    📝 Texto
                  </button>
                  <button className="btn btn-secondary" style={{ flex: 1, padding: '10px' }} onClick={() => layerFileInputRef.current?.click()}>
                    🖼️ Imagen
                  </button>
                </div>
                <input 
                  type="file" 
                  ref={layerFileInputRef} 
                  onChange={handleAddImageUpload} 
                  accept="image/*" 
                  style={{ display: 'none' }} 
                />
              </div>

              {/* Fondo del lienzo */}
              <div className="sidebar-section">
                <span className="section-title">Fondo del Lienzo</span>
                <div className="color-picker-row">
                  <div className="color-input-wrapper">
                    <input 
                      type="color" 
                      value={canvasBackground.type === 'color' ? canvasBackground.value : '#000000'} 
                      onChange={(e) => handleBgColorChange(e.target.value)} 
                    />
                    <span>Color</span>
                  </div>
                  <button className="btn btn-secondary" style={{ padding: '8px' }} onClick={() => bgFileInputRef.current?.click()}>
                    Upload 🖼️
                  </button>
                </div>
                <input 
                  type="file" 
                  ref={bgFileInputRef} 
                  onChange={handleBgImageUpload} 
                  accept="image/*" 
                  style={{ display: 'none' }} 
                />
                {canvasBackground.type === 'image' && (
                  <button className="btn btn-secondary" style={{ width: '100%', padding: '6px', fontSize: '12px' }} onClick={handleClearBg}>
                    Limpiar Fondo
                  </button>
                )}
              </div>

              {/* Lista de Capas */}
              <div className="sidebar-section">
                <span className="section-title">Capas ({layers.length})</span>
                {layers.length === 0 ? (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', padding: '15px' }}>
                    No hay capas. ¡Añade texto o imágenes!
                  </div>
                ) : (
                  <div className="layer-list">
                    {layers.map(layer => {
                      const isActive = layer.id === selectedLayerId;
                      return (
                        <div 
                          key={layer.id} 
                          className={`layer-item ${isActive ? 'active' : ''}`}
                          onClick={() => setSelectedLayerId(layer.id)}
                        >
                          <span className="layer-info">{layer.name}</span>
                          <div className="layer-actions" onClick={e => e.stopPropagation()}>
                            <button className="icon-btn" onClick={() => handleZIndexChange('up', layer.id)} title="Subir (traer al frente)">
                              ▲
                            </button>
                            <button className="icon-btn" onClick={() => handleZIndexChange('down', layer.id)} title="Bajar (enviar al fondo)">
                              ▼
                            </button>
                            <button className="icon-btn danger" onClick={() => handleDeleteLayer(layer.id)} title="Borrar capa">
                              🗑️
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Propiedades de Capa Seleccionada */}
              {selectedLayer && (
                <div className="sidebar-section animate-fade-in" style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <span className="section-title" style={{ color: 'var(--primary-hover)' }}>Propiedades de Capa</span>
                  
                  {/* Propiedades si es texto */}
                  {selectedLayer.type === 'text' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div className="form-group">
                        <label>Contenido del Texto</label>
                        <textarea 
                          rows={3} 
                          value={selectedLayer.text || ''} 
                          onChange={(e) => updateSelectedLayer({ text: e.target.value })}
                        />
                      </div>

                      <div className="form-group">
                        <label>Tipografía</label>
                        <select 
                          value={selectedLayer.fontFamily || 'Impact'} 
                          onChange={(e) => updateSelectedLayer({ fontFamily: e.target.value })}
                        >
                          <option value="Impact">Impact (Meme)</option>
                          <option value="Arial">Arial</option>
                          <option value="Courier New">Courier New</option>
                          <option value="Comic Sans MS">Comic Sans</option>
                          <option value="Georgia">Georgia</option>
                          <option value="Outfit">Outfit (Moderna)</option>
                          <option value="Inter">Inter</option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label>Tamaño de Letra</label>
                        <div className="range-control-group">
                          <input 
                            type="range" 
                            min="10" 
                            max="150" 
                            value={selectedLayer.fontSize || 40} 
                            onChange={(e) => updateSelectedLayer({ fontSize: Number(e.target.value) })}
                          />
                          <span>{selectedLayer.fontSize}px</span>
                        </div>
                      </div>

                      <div className="color-picker-row">
                        <div className="form-group">
                          <label>Color Letra</label>
                          <div className="color-input-wrapper">
                            <input 
                              type="color" 
                              value={selectedLayer.color || '#ffffff'} 
                              onChange={(e) => updateSelectedLayer({ color: e.target.value })}
                            />
                            <span>Fill</span>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>Color Borde</label>
                          <div className="color-input-wrapper">
                            <input 
                              type="color" 
                              value={selectedLayer.borderColor || '#000000'} 
                              onChange={(e) => updateSelectedLayer({ borderColor: e.target.value })}
                            />
                            <span>Borde</span>
                          </div>
                        </div>
                      </div>

                      <div className="form-group">
                        <label>Grosor del Borde</label>
                        <div className="range-control-group">
                          <input 
                            type="range" 
                            min="0" 
                            max="20" 
                            value={selectedLayer.borderWidth || 0} 
                            onChange={(e) => updateSelectedLayer({ borderWidth: Number(e.target.value) })}
                          />
                          <span>{selectedLayer.borderWidth}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Propiedades si es imagen */}
                  {selectedLayer.type === 'image' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <p>Tipo: Imagen</p>
                      <p>Dimensiones: {Math.round(selectedLayer.width)}x{Math.round(selectedLayer.height)} px</p>
                      <p>Rotación: {Math.round(selectedLayer.rotation)}°</p>
                      <div className="form-group" style={{ marginTop: '10px' }}>
                        <label>Cambiar Tamaño Ancho</label>
                        <input 
                          type="number" 
                          value={Math.round(selectedLayer.width)} 
                          onChange={(e) => {
                            const w = Math.max(10, Number(e.target.value));
                            const aspect = selectedLayer.width / selectedLayer.height;
                            updateSelectedLayer({ width: w, height: w / aspect });
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Botones de acción del Lienzo */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: 'auto', paddingTop: '15px', borderTop: '1px solid var(--border-color)' }}>
                <button className="btn btn-accent" onClick={handleExportMeme} disabled={layers.length === 0}>
                  💾 Exportar Meme (PNG)
                </button>
                <button className="btn btn-secondary" onClick={handleResetCanvas}>
                  🗑️ Limpiar Lienzo
                </button>
              </div>
            </aside>
          </div>
        )}
      </main>

      {/* --- MODAL DE CONFIGURACIÓN --- */}
      {showSettings && (
        <div className="settings-overlay animate-fade-in" onClick={() => setShowSettings(false)}>
          <div className="settings-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Configurar Servidor (Hugging Face)</h3>
              <button className="icon-btn" onClick={() => setShowSettings(false)} style={{ fontSize: '18px' }}>×</button>
            </div>
            
            <div className="form-group">
              <label>URL del Space de Hugging Face</label>
              <input 
                type="text" 
                value={tempApiUrl} 
                onChange={(e) => setTempApiUrl(e.target.value)} 
                placeholder="https://tu-usuario-tu-space.hf.space"
              />
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '5px', lineHeight: '1.3' }}>
                Escribe la URL pública de tu Space de Hugging Face. El Space debe estar configurado como Docker y estar activo.
                Por defecto, también puedes configurar esta URL mediante la variable de entorno <strong>VITE_API_URL</strong> al desplegar en Vercel.
              </p>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowSettings(false)}>
                Cancelar
              </button>
              <button className="btn btn-primary" onClick={handleSaveSettings}>
                Guardar Ajustes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
