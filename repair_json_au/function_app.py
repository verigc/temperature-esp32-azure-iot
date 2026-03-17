import azure.functions as func
import json
import logging
import os
import re
from azure.storage.blob import BlobServiceClient
from datetime import datetime

app = func.FunctionApp()

def repair_corrupted_json(content: str) -> dict:
    """
    Intenta reparar JSON corruptos eliminando claves duplicadas y cerrando llaves faltantes.
    Extrae el primer valor válido de cada clave duplicada.
    """
    try:
        # Intentar parsear directo
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Estrategia 1: Extraer valores usando regex
    # La estructura típica es: "clave": "valor" o "clave": número
    try:
        result = {}
        
        # Extraer Body (base64 encoded string)
        body_match = re.search(r'"Body"\s*:\s*"([^"]+)"', content)
        if body_match:
            result["Body"] = body_match.group(1)
        
        # Extraer EnqueuedTimeUtc
        enqueued_match = re.search(r'"EnqueuedTimeUtc"\s*:\s*"([^"]+)"', content)
        if enqueued_match:
            result["EnqueuedTimeUtc"] = enqueued_match.group(1)
        
        # Extraer SystemProperties (todo el objeto)
        sysprop_match = re.search(r'"SystemProperties"\s*:\s*({[^}]+})', content, re.DOTALL)
        if sysprop_match:
            try:
                result["SystemProperties"] = json.loads(sysprop_match.group(1))
            except:
                result["SystemProperties"] = {}
        
        # Extraer Properties (normalmente empty object)
        result["Properties"] = {}
        
        if result:
            return result
        else:
            return None
    except Exception as e:
        logging.warning(f"Failed to repair JSON: {str(e)}")
        return None


def get_blob_service_client(connection_string: str) -> BlobServiceClient:
    """Crea un cliente de Blob Storage a partir de la connection string."""
    return BlobServiceClient.from_connection_string(connection_string)


def get_storage_connection_string() -> str | None:
    """
    Obtiene la connection string desde configuración del entorno.
    Prioriza una variable específica y luego usa AzureWebJobsStorage como fallback.
    """
    return (
        os.environ.get("BLOB_STORAGE_CONNECTION_STRING")
        or os.environ.get("AzureWebJobsStorage")
    )


@app.route(route="repair-json", methods=["POST"])
def repair_json_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function HTTP-triggered para reparar JSONs corruptos en Blob Storage.
    
    Body (JSON):
    {
        "container_name": "my-container",
        "blob_patterns": ["19.json.JSON", "*.json.JSON"],  # optional
        "output_container": "repaired-data",  # optional, usado solo si overwrite_original es false
        "overwrite_original": true  # optional, default: true
    }
    """
    try:
        req_body = req.get_json()
        connection_string = get_storage_connection_string()
        container_name = req_body.get("container_name")
        output_container = req_body.get("output_container", container_name)
        blob_patterns = req_body.get("blob_patterns", ["*.json.JSON", "*.json"])
        overwrite_original = req_body.get("overwrite_original", True)
        
        logging.info(f"[DEBUG] storage connection configured: {bool(connection_string)}")
        logging.info(f"[DEBUG] container_name: '{container_name}'")
        logging.info(f"[DEBUG] blob_patterns: {blob_patterns}")
        logging.info(f"[DEBUG] overwrite_original: {overwrite_original}")
        
        if not connection_string:
            error_msg = "Missing storage connection string in app settings"
            logging.error(f"[ERROR] {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=500,
                mimetype="application/json"
            )

        if not container_name:
            error_msg = "Missing container_name"
            logging.error(f"[ERROR] {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=400,
                mimetype="application/json"
            )
        
        logging.info(f"[DEBUG] Connecting to Blob Storage...")
        blob_service = get_blob_service_client(connection_string)
        container_client = blob_service.get_container_client(container_name)
        output_container_client = blob_service.get_container_client(output_container) if not overwrite_original else container_client
        
        logging.info(f"[DEBUG] Connected. Checking containers...")
        
        # Crear output container si no existe
        try:
            output_container_client.get_container_properties()
            logging.info(f"[DEBUG] Output container '{output_container}' exists")
        except Exception as e:
            logging.warning(f"[WARNING] Output container doesn't exist, creating... Error: {str(e)}")
            try:
                output_container_client.create_container()
                logging.info(f"[DEBUG] Created output container: {output_container}")
            except Exception as create_err:
                logging.error(f"[ERROR] Failed to create output container: {str(create_err)}")
        
        results = {
            "repaired": [],
            "failed": [],
            "skipped": [],
            "overwrite_original": overwrite_original,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Listar blobs
        logging.info(f"[DEBUG] Listing blobs from container '{container_name}'...")
        try:
            blobs = container_client.list_blobs()
            blob_list = list(blobs)
            logging.info(f"[DEBUG] Found {len(blob_list)} total blobs in container")
            if len(blob_list) == 0:
                logging.warning(f"[WARNING] Container '{container_name}' is empty or does not exist!")
        except Exception as list_err:
            error_msg = f"Failed to list blobs: {str(list_err)}"
            logging.error(f"[ERROR] {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=500,
                mimetype="application/json"
            )
        
        for blob in blob_list:
            blob_name = blob.name

            if blob_name.endswith(".repaired.json"):
                results["skipped"].append(blob_name)
                logging.info(f"[DEBUG] Skipped '{blob_name}' (already repaired)")
                continue
            
            # Filtrar por patrón
            should_process = any(
                blob_name.endswith(pattern.replace("*", "")) 
                for pattern in blob_patterns
            )
            
            logging.info(f"[DEBUG] Processing blob '{blob_name}': should_process={should_process}")
            
            if not should_process:
                results["skipped"].append(blob_name)
                logging.info(f"[DEBUG] Skipped '{blob_name}' (doesn't match patterns)")
                continue
            
            try:
                # Descargar blob
                blob_client = container_client.get_blob_client(blob_name)
                blob_content = blob_client.download_blob().readall().decode('utf-8')
                
                # Intentar reparar
                repaired_json = repair_corrupted_json(blob_content)
                
                if repaired_json:
                    # Guardar blob reparado
                    if overwrite_original:
                        output_blob_name = blob_name
                    else:
                        output_blob_name = blob_name.replace(".json.JSON", "") + ".repaired.json"
                    
                    output_blob_client = output_container_client.get_blob_client(output_blob_name)
                    output_blob_client.upload_blob(
                        json.dumps(repaired_json, indent=2),
                        overwrite=True
                    )
                    
                    results["repaired"].append({
                        "source": blob_name,
                        "destination": output_blob_name,
                        "overwritten": overwrite_original,
                        "keys_found": list(repaired_json.keys())
                    })
                    logging.info(f"✓ Repaired: {blob_name} -> {output_blob_name}")
                else:
                    results["failed"].append({
                        "blob": blob_name,
                        "reason": "Could not extract valid JSON structure"
                    })
                    logging.warning(f"✗ Failed to repair: {blob_name}")
                    
            except Exception as e:
                results["failed"].append({
                    "blob": blob_name,
                    "reason": str(e)
                })
                logging.error(f"Error processing {blob_name}: {str(e)}")
        
        logging.info(f"[DEBUG] === FINAL RESULTS ===")
        logging.info(f"[DEBUG] Repaired: {len(results['repaired'])}")
        logging.info(f"[DEBUG] Failed: {len(results['failed'])}")
        logging.info(f"[DEBUG] Skipped: {len(results['skipped'])}")
        
        return func.HttpResponse(
            json.dumps(results, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except ValueError as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON body: {str(e)}"}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Internal error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="validate-json", methods=["POST"])
def validate_json_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint simple para validar si un JSON en Blob Storage es válido.
    
    Body (JSON):
    {
        "container_name": "...",
        "blob_name": "19.json.JSON"
    }
    """
    try:
        req_body = req.get_json()
        connection_string = get_storage_connection_string()
        container_name = req_body.get("container_name")
        blob_name = req_body.get("blob_name")
        
        if not connection_string:
            return func.HttpResponse(
                json.dumps({"error": "Missing storage connection string in app settings"}),
                status_code=500,
                mimetype="application/json"
            )

        if not all([container_name, blob_name]):
            return func.HttpResponse(
                json.dumps({"error": "Missing required parameters"}),
                status_code=400,
                mimetype="application/json"
            )
        
        blob_service = get_blob_service_client(connection_string)
        container_client = blob_service.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        blob_content = blob_client.download_blob().readall().decode('utf-8')
        
        # Intentar validar
        try:
            json.loads(blob_content)
            is_valid = True
            repair_needed = False
            repaired_data = None
        except json.JSONDecodeError as e:
            is_valid = False
            repaired_data = repair_corrupted_json(blob_content)
            repair_needed = repaired_data is not None
        
        return func.HttpResponse(
            json.dumps({
                "blob": blob_name,
                "is_valid": is_valid,
                "repair_possible": repair_needed,
                "repaired_structure": repaired_data,
                "content_size": len(blob_content)
            }, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
