"""
gen_sas.py
Generador de SAS token de ejemplo que toma la clave del dispositivo desde la
variable de entorno `DEVICE_KEY`. No debe contener la clave en el repositorio.
"""
import os
import time
import hmac
import hashlib
import base64
import urllib.parse

try:
	from dotenv import load_dotenv
	load_dotenv()
except Exception:
	# python-dotenv no es obligatorio; si no está instalado, se confiará en las VARS de entorno
	pass

# Leer clave y configuración desde variables de entorno
device_key = os.getenv("DEVICE_KEY")
iothub_host = os.getenv("IOTHUB_HOST", "master-esp32.azure-devices.net")
device_id = os.getenv("DEVICE_ID", "esp32")
expiry = str(int(time.time() + 3600))  # 1 hora

if not device_key:
	raise SystemExit("ERROR: DEVICE_KEY no está definida. Crea un archivo .env con DEVICE_KEY=... o exporta la variable en el entorno.")

resource_uri = f"{iothub_host}/devices/{device_id}"
to_sign = resource_uri + "\n" + expiry

key = base64.b64decode(device_key)
signature = base64.b64encode(hmac.new(key, to_sign.encode('utf-8'), hashlib.sha256).digest()).decode()
sig_enc = urllib.parse.quote(signature, safe='')
sr_enc = urllib.parse.quote(resource_uri, safe='')

sas = f"SharedAccessSignature sr={sr_enc}&sig={sig_enc}&se={expiry}"
print(sas)