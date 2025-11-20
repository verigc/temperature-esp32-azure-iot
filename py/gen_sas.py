# gen_sas.py
import time, hmac, hashlib, base64, urllib.parse

device_key = "xtU0RPRs4e3IOMIMZdXQCzsF+QzD+CNreuHsgPAxcsA="
iothub_host = "master-esp32.azure-devices.net"
device_id = "esp32"
expiry = str(int(time.time() + 3600))  # 1 hora

resource_uri = f"{iothub_host}/devices/{device_id}"
to_sign = resource_uri + "\n" + expiry

key = base64.b64decode(device_key)
signature = base64.b64encode(hmac.new(key, to_sign.encode('utf-8'), hashlib.sha256).digest()).decode()
sig_enc = urllib.parse.quote(signature, safe='')
sr_enc = urllib.parse.quote(resource_uri, safe='')

sas = f"SharedAccessSignature sr={sr_enc}&sig={sig_enc}&se={expiry}"
print(sas)