# Temperature ESP32 → Azure IoT

Descripción
-----------
Proyecto ejemplo para enviar telemetría de un sensor DHT11 conectado a un ESP32 hacia Azure IoT Hub (vía MQTT/TLS) y almacenar mensajes en Azure Blob Storage. Incluye además un script Python para descargar y procesar los mensajes desde el contenedor.

Estructura clave
-----------------
- `src/` : Firmware (PlatformIO/Arduino). Contiene `src/secrets.example.h`.
- `py/`  : Scripts Python (`get-esp32-measures.py`, utilidades).
- `certs/`: Certificados raíz usados por el firmware.
- `data/`: Ejemplos de datos exportados.

Requisitos previos
------------------
- Windows / macOS / Linux con PlatformIO (o VSCode+PlatformIO).
- Python 3.8+ y `pip`.
- Cuenta de Azure con permisos para crear IoT Hub y Storage Account (o `az` CLI configurado).

Pasos para implementar
----------------------

1) Preparar el entorno local

- Crear y activar un virtualenv (recomendado):

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Crear recursos en Azure

- En el Portal de Azure (o con `az`):
  - Crear un `Resource Group` (opcional).
  - Crear un `Storage Account` y dentro crear un contenedor de blobs (p. ej. `esp32`).
  - Crear un `IoT Hub`.
  - En el IoT Hub, crear una identidad de dispositivo (Device Identity) y copiar su Primary Key.

- (Opcional) Configurar Message Routing en IoT Hub:
  - En IoT Hub → `Message routing` → `Endpoints` añade un endpoint tipo `Storage Container` apuntando al Storage Account y contenedor.
  - Crea una `Route` que envíe `Device Telemetry` al endpoint creado.

3) Preparar el firmware (local)

- Copia `src/secrets.example.h` a `src/secrets.h` y rellena con tus credenciales de Wi‑Fi y del dispositivo en IoT Hub. Ejemplo:

```c
// src/secrets.h
#define ssid "TU_SSID"
#define password "TU_WIFI_PASS"
#define IOTHUB_HOST "<tu-iothub>.azure-devices.net"
#define DEVICE_ID "miDispositivo"
#define DEVICE_KEY "<primary_key_del_dispositivo>"
```

- IMPORTANTE: `src/secrets.h` está en `.gitignore`: no lo subas al repositorio.

4) Compilar y flashear al ESP32

- Desde VSCode PlatformIO: `PlatformIO: Build` y luego `PlatformIO: Upload`.
- Desde CLI (si tienes `pio`):

```powershell
# compilar
pio run
# subir/flash
pio run --target upload
```

- Abre la consola serie para validar que el ESP32 conecta a la Wi‑Fi y al IoT Hub.

5) Verificar que los mensajes llegan a Blob Storage

- Revisa el contenedor en el Storage Account; los mensajes deben aparecer como blobs (según la configuración de Message Routing).

6) Descargar y procesar mensajes con Python

- Crea un `.env` en la carpeta `py/` con:

```
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
AZURE_STORAGE_CONTAINER=esp32
OUTPUT_FILE=mensajes_decodificados.csv
```

- Ejecuta el script desde la raíz del proyecto (con el venv activado si aplica):

```powershell
& .\.venv\Scripts\Activate.ps1
python .\py\get-esp32-measures.py
```

- El script descargará los blobs, decodificará el campo `Body` (base64) y generará `mensajes_decodificados.csv`. También contiene un bloque opcional de análisis/plot.
