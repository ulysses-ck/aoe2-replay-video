# Especificación técnica — aoe2-replay-video

Documento de diseño detallado. Complementa el `README.md`.

## 1. Objetivo

Convertir un replay `.aoe2record` de AoE2: DE en un vídeo `.mp4` resumido que:
- acelera los periodos sin eventos relevantes,
- mantiene velocidad 1x en eventos clave,
- centra la cámara en los eventos,
- exporta `.mp4` (H.264/AAC) listo para YouTube,
- opcionalmente sube a YouTube con metadatos automáticos.

## 2. Alcance (MVP)

- Parseo de un único replay.
- Detección de los 7 tipos de evento clave.
- Grabación de pantalla de la ventana de AoE2 DE (Opción B).
- Exportación local `.mp4`.
- (Post-MVP) Subida a YouTube.

## 3. Fuera de alcance (MVP)

- Edición manual de timeline.
- Multi-replay / batch.
- Soporte de otros juegos.

## 4. Módulos

### 4.1 `parser/` — Fase 1

- Entrada: ruta a `.aoe2record`.
- Salida: `Timeline` = lista de `Segment {start, end, speed, camera: (x,y), event_type}`.
- Usa `aoc-mgz` para leer eventos.
- Heurísticas de detección:
  - Edad: eventos de tecnología "Feudal/Castle/Imperial Age".
  - Raid economía: ≥ N aldeanos muertos en ventana T.
  - Pico batalla: concentración de muertes en radio R en ventana T.
  - Pico APM: delta de APM > umbral.
  - Avanzada/asedio: construcción de Castle/Siege Workshop cerca de base enemiga.
  - Conversión crítica: monk convert de unidad high-value.
  - Maravilla/reliquias: Wonder built o relic capture masiva.

### 4.2 `control/` — Fase 2

- Lanzador de AoE2 DE con replay como argumento (o automatización de menú).
- Gestión de ventana: resolución fija, borderless, foco.
- Controlador de teclado/mouse (pyautogui/pynput): speed keys, cámara.
- Grabador: ffmpeg con captura de ventana (dshow/gdigrab en Windows; x11grab en Linux; NVENC/VAAPI/AMF).
- Sincronización con `Timeline`: en cada segmento ajusta velocidad y cámara.

### 4.3 `editing/` — Fase 3

- Entrada: grabación cruda + `Timeline`.
- Recortes por segmento, transiciones (xfade), normalización de audio.
- Salida: `.mp4` H.264/AAC.

### 4.4 `youtube/` — Fase 4

- OAuth2 desktop flow, token persistente.
- Upload resumable.
- Metadatos: título (jugadores + mapa), descripción con timestamps, categoría Gaming, privacidad unlisted/private.

### 4.5 `ui/` — GUI

- CustomTkinter o PySide6.
- Flujo: seleccionar replay → elegir perfil de aceleración → "Procesar y Grabar" → preview + "Subir a YouTube"/"Guardar Local".

## 5. Perfiles de aceleración

| Perfil | Tiempo muerto | Eventos |
|---|---|---|
| Suave | 2x | 1x |
| Normal | 4x | 1x |
| Agresivo | 8x | 1x |

## 6. Riesgos y mitigaciones

- Detección de eventos heurística → validar contra replays reales, ajustar umbrales.
- Sincronización juego/captura → usar timestamps del replay como fuente de verdad.
- Anti-cheat / fair use → solo replays propios/públicos, no automatizar online.
- Captura de ventana dependiente del OS → abstracción por plataforma.

## 7. Métricas de éxito (MVP)

- Parseo correcto de ≥ 10 replays de prueba.
- Vídeo generado con duración ≤ 25% del original.
- Subida exitosa a YouTube (post-MVP).
