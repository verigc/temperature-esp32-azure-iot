#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <DHT.h>
#include "time.h"
#include <mbedtls/md.h>
#include <mbedtls/base64.h>
#include <esp_task_wdt.h>  // Watchdog timer

#define DHTPIN 4            // Pin conectado al DHT11
#define DHTTYPE DHT11       // Tipo de sensor
#define LED_PIN 2           // LED integrado del ESP32
#define WDT_TIMEOUT 60      // segundos para watchdog

DHT dht(DHTPIN, DHTTYPE);

// Secrets and configuration
// Sensitive values (WiFi, device key, connection strings) are moved to
// a local header `secrets.h` that's NOT committed. See `secrets.example.h`
// for the format. This makes the repo safe to publish.
#include "secrets.h"

// Use secure client for TLS
WiFiClientSecure espClient;
PubSubClient client(espClient);

// Configuración NTP
const char* ntpServer = "time.windows.com";
const long gmtOffset_sec = -10800; // UTC-3 para Argentina/Chile
const int daylightOffset_sec = 0;

// Load certificate from centralized header under src/certs/
#include "certs/digicert_root.h"

// SAS token management
String currentSas = "";
uint32_t currentSasExpiry = 0; // epoch seconds

// forward declaration
String generateSasToken(const char* iothubHost, const char* deviceId, const char* deviceKey, uint32_t expiryInSeconds, bool useBase64Url);

// Ensure SAS token is valid; regenerate if it's going to expire within 5 minutes
void ensureSasValid() {
  time_t nowSec = time(nullptr);
  if (nowSec <= 0) nowSec = 0;
  // regenerate if empty or expiring in less than 5 minutes
  if (currentSas.length() == 0 || currentSasExpiry == 0 || (currentSasExpiry - nowSec) < 300) {
    Serial.println("Generando/renovando SAS token...");
    // default 1 hour expiry
    uint32_t expiryInSeconds = 60 * 60;
    String token = generateSasToken(IOTHUB_HOST, DEVICE_ID, DEVICE_KEY, expiryInSeconds, false);
    if (token.length() > 0) {
      currentSas = token;
      currentSasExpiry = (uint32_t)(nowSec + expiryInSeconds);
      Serial.print("Nuevo SAS expiry: "); Serial.println(currentSasExpiry);
    } else {
      Serial.println("Falló la generación del SAS token");
    }
  } else {
    Serial.print("SAS token vigente, expira en secs: "); Serial.println(currentSasExpiry - nowSec);
  }
}

void setup_wifi() {
  delay(10);
  Serial.println("Conectando a WiFi...");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi conectado!");
  Serial.print("IP asignada: ");
  Serial.println(WiFi.localIP());
}

// URL-encode (percent-encode) helper - específico para Azure IoT Hub SAS tokens
String urlEncode(const String &str) {
  String encoded = "";
  char buf[4];
  for (size_t i = 0; i < str.length(); ++i) {
    char c = str[i];
    // Azure IoT Hub espera estos caracteres específicamente percent-encoded
    if (c == '+') encoded += "%2B";
    else if (c == '/') encoded += "%2F";
    else if (c == '=') encoded += "%3D";
    else if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '-' || c == '_' || c == '.' || c == '~') {
      encoded += c;
    } else {
      sprintf(buf, "%%%02X", (unsigned char)c);
      encoded += buf;
    }
  }
  return encoded;
}

// Generate SAS token for IoT Hub
String generateSasToken(const char* iothubHost, const char* deviceId, const char* deviceKey, uint32_t expiryInSeconds = 3600, bool useBase64Url = false) {
  String resourceUri = String(iothubHost) + "/devices/" + String(deviceId);
  Serial.print("resourceUri antes de encode: '"); Serial.print(resourceUri); Serial.println("'");

  time_t nowSec = time(nullptr);
  if (nowSec <= 0) nowSec = 0;
  uint32_t exp = (uint32_t)nowSec + expiryInSeconds;
  String expStr = String(exp);

  String encodedResourceUri = urlEncode(resourceUri);
  String toSign = encodedResourceUri + "\n" + expStr;
  
  Serial.println("toSign bytes (hex):");
  for (size_t i = 0; i < toSign.length(); ++i) {
    char hexbuf[3];
    sprintf(hexbuf, "%02X", (unsigned char)toSign[i]);
    Serial.print(hexbuf);
  }
  Serial.println();
  
  Serial.print("toSign exacto: '"); 
  Serial.print(encodedResourceUri); 
  Serial.print("\\n");
  Serial.print(expStr);
  Serial.println("'");

  Serial.print("deviceKey original: '"); Serial.print(deviceKey); Serial.println("'");
  
  size_t keyLen = 0;
  unsigned char keyBin[64];
  int ret = mbedtls_base64_decode(keyBin, sizeof(keyBin), &keyLen, (const unsigned char*)deviceKey, strlen(deviceKey));
  if (ret != 0) {
    Serial.print("Error base64 decode key: "); Serial.println(ret);
    return String("");
  }
  
  Serial.print("Key completa (hex): ");
  for (size_t i = 0; i < keyLen; ++i) {
    char hexbuf[3];
    sprintf(hexbuf, "%02X", keyBin[i]);
    Serial.print(hexbuf);
  }
  Serial.println();

  unsigned char hmacOut[32];
  mbedtls_md_context_t ctx;
  const mbedtls_md_info_t *md_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_init(&ctx);
  if (mbedtls_md_setup(&ctx, md_info, 1) != 0) {
    Serial.println("mbedtls_md_setup failed");
    mbedtls_md_free(&ctx);
    return String("");
  }
  mbedtls_md_hmac_starts(&ctx, keyBin, keyLen);
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)toSign.c_str(), toSign.length());
  mbedtls_md_hmac_finish(&ctx, hmacOut);
  mbedtls_md_free(&ctx);

  unsigned char sigBase64[64];
  size_t sigBase64Len = 0;
  ret = mbedtls_base64_encode(sigBase64, sizeof(sigBase64), &sigBase64Len, hmacOut, sizeof(hmacOut));
  if (ret != 0) {
    Serial.print("Error base64 encode sig: "); Serial.println(ret);
    return String("");
  }
  String sigB64Str = String((const char*)sigBase64);
  if (sigB64Str.length() > (int)sigBase64Len) sigB64Str = sigB64Str.substring(0, sigBase64Len);

  char hexbuf[3];
  String hmacHex = "";
  for (size_t i = 0; i < sizeof(hmacOut); ++i) {
    sprintf(hexbuf, "%02X", hmacOut[i]);
    hmacHex += String(hexbuf);
  }
  Serial.print("hmac hex: "); Serial.println(hmacHex);
  Serial.print("toSign: "); Serial.println(toSign);
  Serial.print("sig (base64): "); Serial.println(sigB64Str);
  Serial.print("expiry (epoch): "); Serial.println(exp);
  
  int padNeeded = (4 - (sigB64Str.length() % 4)) % 4;
  if (padNeeded > 0) {
    Serial.print("Base64 padding missing, appending '=' x"); Serial.println(padNeeded);
    for (int i = 0; i < padNeeded; ++i) sigB64Str += '=';
    Serial.print("sig (base64) after padding: "); Serial.println(sigB64Str);
  }
  String sigFinal = sigB64Str;
  
  String sigEnc = urlEncode(sigFinal);
  String srEnc = urlEncode(resourceUri);

  String token = String("SharedAccessSignature ") + 
                "sr=" + srEnc + 
                "&sig=" + sigEnc + 
                "&se=" + expStr;
  
  Serial.println("Token antes de cualquier encoding:");
  Serial.print("1. sr='"); Serial.print(resourceUri); Serial.println("'");
  Serial.print("2. sig='"); Serial.print(sigB64Str); Serial.println("'");
  Serial.print("3. se='"); Serial.print(expStr); Serial.println("'");
  Serial.print("4. Token completo:'"); Serial.print(token); Serial.println("'");
  return token;
}

bool connectToIoTHub() {
  String username = String(IOTHUB_HOST) + "/" + String(DEVICE_ID) + "/?api-version=2018-06-30";
  String clientId = String(DEVICE_ID);

  extern String currentSas;
  ensureSasValid();
  String sas = currentSas;
  if (sas.length() == 0) {
    Serial.println("No se pudo obtener SAS token");
    return false;
  }
  Serial.println("Conectando a IoT Hub con TLS...");
  
  extern const char* digicert_root_pem;
  if (digicert_root_pem != nullptr && strlen(digicert_root_pem) > 10) {
    espClient.setCACert(digicert_root_pem);
    Serial.println("Usando CA embebida para validación TLS.");
  } else {
    Serial.println("CA embebida no encontrada, usando setInsecure() (solo debug)");
    espClient.setInsecure();
  }

  client.setServer(IOTHUB_HOST, 8883);
  Serial.print("MQTT username: "); Serial.println(username);
  Serial.print("username length: "); Serial.println(username.length());
  size_t sasPrintLen = sas.length() > 200 ? 200 : sas.length();
  Serial.print("SAS used (truncated): "); Serial.println(sas.substring(0, sasPrintLen));
  Serial.print("SAS length: "); Serial.println(sas.length());

  Serial.println("\nComparación con token que funciona:");
  Serial.print("1. Longitud token actual  : "); Serial.println(sas.length());
  Serial.print("2. Longitud token ejemplo : "); Serial.println(strlen(TOKEN_EJEMPLO));
  
  if (client.connect(clientId.c_str(), username.c_str(), sas.c_str())) {
    Serial.println("Conectado a IoT Hub");
    return true;
  } else {
    int st = client.state();
    Serial.print("Falló conexión IoT Hub, rc="); Serial.println(st);
    String reason = "";
    switch (st) {
      case 0: reason = "Success"; break;
      case 1: reason = "Connection refused - unacceptable protocol version"; break;
      case 2: reason = "Connection refused - identifier rejected"; break;
      case 3: reason = "Connection refused - server unavailable"; break;
      case 4: reason = "Connection refused - bad user name or password"; break;
      case 5: reason = "Connection refused - not authorized"; break;
      default: reason = "See PubSubClient::state() for details"; break;
    }
    Serial.print("Reason: "); Serial.println(reason);
    return false;
  }
}

void reconnect() {
  while (!client.connected()) {
    digitalWrite(LED_PIN, HIGH);  // LED encendido mientras intenta conectar
    if (!connectToIoTHub()) {
      Serial.println("Reintentando en 5s...");
      // Parpadeo rápido para indicar error
      for(int i=0; i<5; i++) {
        digitalWrite(LED_PIN, LOW);
        delay(100);
        digitalWrite(LED_PIN, HIGH);
        delay(100);
      }
      delay(4000);  // Completa los 5 segundos
    }
  }
  digitalWrite(LED_PIN, LOW);  // LED apagado cuando está conectado
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n[INICIO] ESP32 DHT11 to Azure IoT Hub");
  
  // Configurar LED y watchdog
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // LED encendido durante inicio
  
  esp_task_wdt_init(WDT_TIMEOUT, true);  // enable panic so ESP32 restarts
  esp_task_wdt_add(NULL);  // add current thread to WDT watch
  
  dht.begin();
  Serial.println("✓ DHT11 iniciado");
  
  setup_wifi();
  
  // Inicializar NTP
  Serial.println("Configurando NTP...");
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Esperando sincronización de hora (max ~10s)...");
  struct tm ti;
  int waitCount = 0;
  while (!getLocalTime(&ti) && waitCount < 10) {
    delay(1000);
    Serial.print(".");
    waitCount++;
  }
  Serial.println();
  digitalWrite(LED_PIN, LOW);  // LED apagado después de inicio exitoso
}

String obtenerHoraActual() {
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("❌ Error: No se pudo obtener la hora.");
    Serial.println("Verifica WiFi y servidor NTP.");
    return "HoraNoDisponible";
  }

  char buffer[30];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &timeinfo);
  Serial.print("🕒 Hora sincronizada: ");
  Serial.println(buffer);
  return String(buffer);
}

void loop() {
  esp_task_wdt_reset();  // feed the watchdog
  
  static unsigned long lastMsg = 0;
  unsigned long now = millis();
  
  if (!client.connected()) {
    Serial.println("📡 Reconectando a IoT Hub...");
    reconnect();
  }
  client.loop();

  // Control de intervalo de envío
  if (now - lastMsg > 60000) {
    lastMsg = now;
    
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      Serial.println("❌ Error leyendo DHT11!");
      return;
    }

    Serial.printf("📊 Temperatura: %.1f°C, Humedad: %.1f%%\n", t, h);
    
    String ts = obtenerHoraActual();
    String payload = "{\"fecha\":\"" + ts + "\",\"temperatura\":" + String(t, 1) + 
                    ",\"humedad\":" + String(h, 1) + "}";

    Serial.print("📤 Enviando: ");
    Serial.println(payload);

    String topic = "devices/" + String(DEVICE_ID) + "/messages/events/";
    bool success = client.publish(topic.c_str(), payload.c_str());
    
    if (success) {
      Serial.println("✓ Mensaje enviado correctamente");
      // Parpadeo corto para indicar envío exitoso
      digitalWrite(LED_PIN, HIGH);
      delay(100);
      digitalWrite(LED_PIN, LOW);
    } else {
      Serial.println("❌ Error al enviar mensaje");
    }
  }
}