from azure.storage.blob import BlobServiceClient, ContainerClient
import json
import base64
import os
from pathlib import Path

# Simple .env loading: attempt to import python-dotenv and load a .env
# file located next to this script. If python-dotenv is not available,
# the script will still read environment variables from the environment.
try:
    from dotenv import load_dotenv
    # Determine where to look for .env. When running the script line-by-line in
    # an interactive session (e.g. REPL / editor selection), `__file__` may not
    # be defined. In that case look for `.env` in the current working directory.
    if '__file__' in globals():
        env_path = Path(__file__).resolve().parent / '.env'
    else:
        env_path = Path.cwd() / '.env'
        print(f"[dotenv] __file__ is not defined (interactive). Looking for .env in CWD: {env_path}")

    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
        print(f"[dotenv] Loaded .env from {env_path}")
    else:
        # call load_dotenv() so it searches the working directory as fallback
        load_dotenv()
        print(f"[dotenv] .env not found at {env_path}; load_dotenv() attempted (cwd: {Path.cwd()})")
except Exception:
    print("[dotenv] python-dotenv not installed; reading environment variables only")

# Configuración desde variables de entorno (.env)
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER", "esp32")
# Opcional: Carpeta donde guardar los archivos decodificados
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "mensajes_decodificados.csv")

if not CONNECTION_STRING:
    print(f"[debug] Current working dir: {Path.cwd()}")
    print("[error] AZURE_STORAGE_CONNECTION_STRING no está definido. Crea un archivo .env en el mismo directorio que este script o exporta la variable de entorno.")
    raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING no está definido. Crea un archivo .env o exporta la variable de entorno.")
else:
    # Do not print the connection string value, only indicate it was loaded
    print("[config] AZURE_STORAGE_CONNECTION_STRING: set")
    print(f"[config] AZURE_STORAGE_CONTAINER: {CONTAINER_NAME}")

def decode_base64(body):
    content = base64.b64decode(body).decode('utf-8')
    return content

def main():
    # Conectar al container
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Abrir el archivo para guardar resultados
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
        f_out.write("EnqueuedTime;DeviceId;Payload\n")
        # Recorrer todos los blobs/archivos del container
        for blob in container_client.list_blobs():
            print(f"Descargando: {blob.name}")
            blob_client = container_client.get_blob_client(blob)
            data = blob_client.download_blob().readall()
            # Procesar cada línea (un mensaje por línea normalmente)
            for line in data.decode("utf-8").splitlines():
                record = json.loads(line)
                time = record.get("EnqueuedTimeUtc")
                device = record.get("SystemProperties", {}).get("connectionDeviceId", "")
                payload = decode_base64(record["Body"])
                # Mostrar por pantalla y guardar en CSV
                print(f"{time} | {device} | {payload}")
                f_out.write(f"{time};{device};{payload}\n")

if __name__ == "__main__":
    main()



import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv(OUTPUT_FILE, sep=";", index_col=False)

df.head()

df.columns
['EnqueuedTime', 'DeviceId', 'Payload']

df['EnqueuedTime']
df['DeviceId']
df['Payload'][0]

df.dtypes

df['Payload'] = df['Payload'].apply(json.loads)



# Ahora puedes quedarte solo con las columnas que quieres
df = pd.json_normalize(df['Payload'])

df['fecha'] = pd.to_datetime(df['fecha'])

df.columns




# Boxplots por hora: distribución de temperatura y humedad
if df.empty:
    print("[plot] No hay datos para graficar.")
else:
    # Agrupar por hora del día
    hour_group = df.groupby(df['fecha'].dt.hour)
    hours = [int(h) for h in hour_group.groups.keys()]

    # Preparar listas de valores por hora (en el mismo orden que 'hours')
    temp_data = [hour_group.get_group(h)['temperatura'].values for h in hours]
    hum_data = [hour_group.get_group(h)['humedad'].values for h in hours]

    # Crear figura con dos boxplots lado a lado
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=False)

    # Temperatura
    axes[0].boxplot(temp_data, positions=range(len(hours)), widths=0.6, showfliers=False)
    axes[0].set_xticks(range(len(hours)))
    axes[0].set_xticklabels(hours, rotation=45)
    axes[0].set_xlabel('Hora del día (0-23)')
    axes[0].set_ylabel('Temperatura (°C)')
    axes[0].set_title('Distribución de Temperatura por Hora')
    axes[0].grid(axis='y', linestyle='--', alpha=0.5)

    # Humedad
    axes[1].boxplot(hum_data, positions=range(len(hours)), widths=0.6, showfliers=False)
    axes[1].set_xticks(range(len(hours)))
    axes[1].set_xticklabels(hours, rotation=45)
    axes[1].set_xlabel('Hora del día (0-23)')
    axes[1].set_ylabel('Humedad (%)')
    axes[1].set_title('Distribución de Humedad por Hora')
    axes[1].grid(axis='y', linestyle='--', alpha=0.5)

    fig.tight_layout()
    plt.show()
