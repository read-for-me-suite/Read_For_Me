#include <WiFi.h>
#include <WebServer.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ESPmDNS.h>

// ================================================================
// CONFIGURATION (À adapter à ton routeur/partage de connexion)
// ================================================================
const char* ssid = "RPI-HOTSPOT"; 
const char* password = "Dont4get!";

const char* hostname = "thermo"; 

// ================================================================
// MATÉRIEL & VARIABLES
// ================================================================
const int oneWireBus = 4; 
OneWire oneWire(oneWireBus);
DallasTemperature sensors(&oneWire);
WebServer server(80);

float currentTemp = 0.0;
unsigned long lastWifiCheck = 0;
bool dejaAnnonceConnecte = false;

// ================================================================
// FONCTIONS UTILITAIRES
// ================================================================

void readSensor() {
  sensors.requestTemperatures(); 
  float tempC = sensors.getTempCByIndex(0);
  // -127 est la valeur d'erreur du capteur DS18B20
  if (tempC != DEVICE_DISCONNECTED_C) {
    currentTemp = tempC;
  } else {
    currentTemp = -999.0; // Code d'erreur interne
  }
}

// ================================================================
// ROUTE API (Machine)
// ================================================================
void handleAPI() {
  readSensor();
  // Renvoie juste la valeur numérique brute (ex: 22.5) pour le script Python
  server.send(200, "text/plain", String(currentTemp, 1));
}

// ================================================================
// ROUTE WEB (Humain)
// ================================================================
void handleWebInterface() {
  readSensor();
  
  String tempStr;
  String sensorStatusColor;
  String sensorStatusText;

  Serial.println(currentTemp);
  
  // 1. Vérification du capteur
  if (currentTemp == -999.0) {
    tempStr = "--.-";
    sensorStatusColor = "#e74c3c"; // Rouge (Erreur Capteur)
    sensorStatusText = "Erreur Capteur";
  } else {
    tempStr = String(currentTemp, 1);
    sensorStatusColor = "#2ecc71"; // Vert (OK)
    sensorStatusText = "Capteur OK";
  }

  // 2. Vérification du WiFi (Si on voit la page, c'est qu'on est connecté, 
  // mais on affiche l'info réseau pour confirmer le SSID)
  String wifiSSID = WiFi.SSID();
  // Construction de la page HTML avec CSS intégré (Design "Card")
  String html = "<!DOCTYPE html><html lang='fr'><head>";
  html += "<meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<meta http-equiv='refresh' content='5'>"; // Actualisation auto toutes les 5s
  html += "<title>Thermomètre MHK</title>";
  html += "<style>";
  html += "body { font-family: 'Segoe UI', sans-serif; background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; color: #333; }";
  html += ".card { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; width: 320px; }";
  html += "h1 { color: #2c3e50; font-size: 1.4rem; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 1px; }";
  
  html += ".temp-container { margin: 1.5rem 0; }";
  html += ".temp { font-size: 4.5rem; font-weight: bold; color: #2c3e50; margin: 0; line-height: 1; }";
  html += ".unit { font-size: 1.5rem; vertical-align: super; color: #7f8c8d; }";
  
  html += ".badges { display: flex; justify-content: center; gap: 10px; margin-bottom: 1rem; }";
  html += ".badge { padding: 5px 12px; border-radius: 20px; color: white; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }";
  
  html += ".info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; text-align: left; font-size: 0.85rem; background: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 1rem;}";
  html += ".info-label { color: #95a5a6; font-weight: 600; }";
  html += ".info-value { color: #34495e; font-weight: bold; text-align: right; }";
  
  html += ".footer { margin-top: 1.5rem; font-size: 0.75rem; color: #bdc3c7; }";
  html += "</style></head>";
  
  html += "<body>";
  html += "<div class='card'>";
  html += "<h1>Machine à Lire</h1>";
  
  // Badges d'état (Capteur + WiFi)
  html += "<div class='badges'>";
  html += "<div class='badge' style='background-color: " + sensorStatusColor + "'>" + sensorStatusText + "</div>";
  html += "<div class='badge' style='background-color: #3498db'>WiFi: Connecté</div>";
  html += "</div>";
  
  // Température
  html += "<div class='temp-container'>";
  html += "<div class='temp'>" + tempStr + "<span class='unit'>&deg;C</span></div>";
  html += "</div>";
  
  // Tableau d'informations techniques
  html += "<div class='info-grid'>";
  html += "<div class='info-label'>Réseau</div><div class='info-value'>" + wifiSSID + "</div>";
  html += "<div class='info-label'>IP</div><div class='info-value'>" + WiFi.localIP().toString() + "</div>";
  html += "</div>";

  html += "<div class='footer'>Projet My Human Kit • IMT 2025</div>";
  html += "</div>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}
// ================================================================
// SETUP
// ================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- MODE CLIENT WI-FI ---");

  sensors.begin();
  
  // Connexion au réseau existant
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  WiFi.setAutoReconnect(true);

  // Initialisation mDNS pour être joignable via http://thermo.local
  if (MDNS.begin(hostname)) {
    Serial.println("mDNS actif : http://thermo.local");
  }

  // Définition des routes
  server.on("/api", handleAPI);        // Pour le script Python
  server.on("/", handleWebInterface);  // Pour le navigateur (Téléphone/PC)
  
  server.begin();
}

// ================================================================
// LOOP
// ================================================================
void loop() {
  server.handleClient();
  
  if (WiFi.status() == WL_CONNECTED) {
    if (!dejaAnnonceConnecte) {
      Serial.println("\n[WIFI] Connecté au réseau !");
      Serial.print("[WIFI] Adresse IP : ");
      Serial.println(WiFi.localIP());
      Serial.println("[WIFI] Interface Web : http://thermo.local");
      dejaAnnonceConnecte = true;
    }
  } else {
    dejaAnnonceConnecte = false;
  }
  
  delay(5);
}