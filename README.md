# aoe2-replay-video

Herramienta de escritorio que convierte un replay de **Age of Empires II: Definitive Edition** (`.aoe2record`) en un vídeo resumido y narrativo: acelera los periodos "muertos", mantiene la velocidad normal en los momentos clave (batallas, raids, picos de APM, avances de edad, maravillas) y centra la cámara en los eventos relevantes. El resultado se exporta a `.mp4` y se puede subir directamente a YouTube.

> Proyecto en fase de especificación. Este repositorio contiene el spec técnico y la estructura inicial.

## Contexto de entorno

- **WSL Debian** (desarrollo) sobre host **Windows**.
- **AoE2 DE** instalado en el host Windows (obligatorio: la Opción B captura la pantalla ejecutando el propio motor del juego).
- **OBS Studio** disponible en el host (alternativa/complemento de captura).
- **FFmpeg** instalado y en `PATH`.
- **Python 3.10+**.

## Stack seleccionado

| Capa | Tecnología |
|---|---|
| Lenguaje principal | Python 3.10+ |
| GUI | CustomTkinter / PySide6 (liviano, multiplataforma Windows/Linux) |
| Parsing de replays | `aoc-mgz` (replays de AoE2: DE) |
| Automatización teclado/mouse | `pyautogui` / `pynput` |
| Procesamiento de video | `ffmpeg-python` + CLI `ffmpeg` |
| Integración YouTube | `google-api-python-client` + `google-auth-oauthlib` |

## Requisitos previos e instalación

1. **AoE2 DE instalado** (obligatorio, Opción B captura la pantalla ejecutando el motor del juego).
2. **FFmpeg** instalado y agregado al `PATH`.
3. **Python 3.10+**.
4. (Opcional) **OBS Studio** en el host Windows para captura alternativa.

## Plan de ejecución y arquitectura

### Fase 1 — Parsing del replay (`.aoe2record`)

1. Lectura del archivo `.aoe2record` enviado por la GUI usando `aoc-mgz`.
2. Extracción de marcas de tiempo (timestamps) y coordenadas del mapa para los siguientes eventos clave:
   - **Pases de Edad**: Feudal, Castillos, Imperial.
   - **Raid a la economía**: eliminación masiva de aldeanos en lapsos cortos.
   - **Picos de Batalla**: concentración de muertes/pérdidas masivas en zonas acotadas.
   - **Picos de APM / Micro**: incrementos abruptos de acciones por minuto.
   - **Avanzadas y Asedios**: construcción de castillos o talleres de maquinaria cerca del enemigo.
   - **Conversiones Críticas**: monjes convirtiendo unidades de alto valor (elefantes, caballería pesada).
   - **Maravillas y Reliquias**: captura masiva de reliquias o inicio de maravillado.
3. Generación de una estructura limpia de datos con marcas de tiempo (inicio, fin, coordenadas de cámara y velocidad asignada).

### Fase 2 — Control del juego y grabación (Opción B)

1. Iniciar la ejecución automática de AoE2 DE pasándole el replay `.aoe2record` como parámetro de inicio, o automatizar el menú principal para lanzar la partida guardada.
2. Posicionar la ventana del juego en modo resolución fija sin bordes.
3. Enviar comandos mediante simulador de teclado/mouse para:
   - Acelerar el juego (vía teclas rápidas) en periodos entre eventos.
   - Desacelerar a velocidad normal (1x) durante los eventos clave.
   - Centrar la vista del juego usando coordenadas/minimapa en los eventos detectados.
4. Grabar la ventana del juego usando la API de captura de FFmpeg en segundo plano (NVENC para GPUs NVIDIA o VAAPI/AMF para Linux/AMD).

### Fase 3 — Edición y recorte de video

1. Procesar la grabación generada mediante FFmpeg.
2. Aplicar recortes, transiciones suaves entre eventos y ajuste de audio en los tramos acelerados.
3. Exportar el archivo final en formato `.mp4` (H.264 / AAC) optimizado para reproducción y subida.

### Fase 4 — Integración con YouTube API

1. Configuración del flujo OAuth2 dentro de la app desktop para autenticación del usuario.
2. Envío del video procesado mediante la API v3 de YouTube.
3. Configuración automática de metadatos (título con nombres de jugadores y mapa, descripción con marcas de tiempo de los eventos, categoría *Gaming* y visibilidad *Privado/No listado*).

## Instrucciones de uso

1. **Configuración inicial**:
   - Descargar la aplicación ejecutable o script ejecutable Python.
   - Autenticar la cuenta de Google/YouTube dentro del panel de Ajustes (solo la primera vez).
2. **Generación del video**:
   - Abrir la aplicación Desktop.
   - Arrastrar o seleccionar el archivo `.aoe2record` (ubicado usualmente en `C:\Users\<Usuario>\Games\Age of Empires 2 DE\<ID>\savegame`).
   - Seleccionar el perfil de aceleración deseado (ej. *Acelerar tiempo muerto a 4x/8x*, *Mantener batallas a 1x*).
   - Presionar **"Procesar y Grabar"**.
3. **Ejecución automática**:
   - La aplicación abrirá automáticamente AoE2 DE, controlará la reproducción y grabará el tramo de partida.
   - *Nota*: No se debe interactuar con el mouse ni teclado mientras la captura esté en progreso.
4. **Subida**:
   - Al finalizar, la app mostrará la vista previa del archivo `.mp4` y un botón directo para **"Subir a YouTube"** o **"Guardar Localmente"**.

## Estructura del proyecto (propuesta)

```
aoe2-replay-video/
├── README.md
├── SPEC.md
├── pyproject.toml
├── .gitignore
├── src/
│   └── aoe2_replay_video/
│       ├── __init__.py
│       ├── parser/          # Fase 1: parsing de .aoe2record
│       ├── control/         # Fase 2: control de juego + captura
│       ├── editing/         # Fase 3: edición con FFmpeg
│       ├── youtube/         # Fase 4: OAuth2 + upload
│       └── ui/             # GUI
├── tests/
└── docs/
```

## Licencia

MIT
