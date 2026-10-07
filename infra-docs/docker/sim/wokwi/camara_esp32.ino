/*
 * Câmara Climática ESP32 — firmware para o Wokwi e para a placa real
 * ---------------------------------------------------------------------------
 * Mesmo contrato MQTT do camara-sim (LAB IoT, gen_iot_scada_portal.py):
 *   <GRUPO>/camara/status        "online"/"offline" (retido; offline = Last Will)
 *   <GRUPO>/camara/telemetria    JSON a cada 2 s
 *   <GRUPO>/camara/oled          texto da tela
 *   <GRUPO>/camara/cmd           JSON parcial  {"setpoint":40,"modo":2}
 *   <GRUPO>/camara/cmd/<campo>   valor simples
 *
 * Hardware: DHT22 (GPIO4) · potenciômetro (GPIO34) · aquecedor PWM (GPIO25)
 *           ventilador PWM (GPIO26) · OLED SSD1306 I2C (SDA21/SCL22)
 *           LEDs verde/amarelo/vermelho (GPIO16/17/5)
 *           botão "habilitado" (GPIO14) · chave "planta virtual" (GPIO27)
 *
 * PLANTA VIRTUAL: no Wokwi o aquecedor não esquenta o DHT22. Com a planta virtual
 * ligada, o próprio ESP32 calcula a temperatura e a umidade da câmara a partir dos
 * PWMs aplicados (mesmo modelo do camara-sim), e o DHT22 passa a ser o AMBIENTE
 * (mexa nos sliders dele). A chave do GPIO27 escolhe: esquerda (GND) = planta virtual,
 * direita = DHT22 real. Na placa real sem a chave o pino fica em 1 (pull-up) = planta real.
 * Também dá para trocar por MQTT: <GRUPO>/camara/cmd/planta_virtual  true|false
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHTesp.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>

// ============================== CONFIGURAÇÃO ==============================
#define GRUPO        "lab05-a"                // seu grupo do LAB IoT
#define WIFI_SSID    "Wokwi-GUEST"            // placa real: rede do laboratório
#define WIFI_PASS    ""
#define WIFI_CANAL   6                        // Wokwi-GUEST = canal 6; placa real: 0
// Broker MQTT:
//  - Wokwi + gateway privado: "host.wokwi.internal" = o seu PC (mosquitto do kit)
//  - Wokwi gratuito (gateway público): um broker público, ex. "broker.hivemq.com"
//  - placa real no laboratório: IP do servidor do lab, ex. "192.168.0.10"
#define MQTT_HOST    "host.wokwi.internal"
#define MQTT_PORT    1883
// ==========================================================================

// Pinos
const int PIN_DHT = 4, PIN_POT = 34, PIN_AQUEC = 25, PIN_VENT = 26;
const int PIN_LED_VERDE = 16, PIN_LED_AMARELO = 17, PIN_LED_VERMELHO = 5;
const int PIN_BOTAO = 14, PIN_CHAVE = 27;
const int PWM_BITS = 8;                       // LEDC 8 bits: duty 0..255
const int PWM_FREQ_AQUEC = 1000, PWM_FREQ_VENT = 25000;

// Constantes do processo (iguais às do camara-sim)
const float SP_MIN = 20, SP_MAX = 55, T_ALARME = 60, T_LIBERA = 55;
const char *ESTADOS[] = {"DESLIGADO", "AQUECENDO", "RESFRIANDO", "ESTAVEL", "ALARME"};
const char *MODOS[] = {"MANUAL", "ON/OFF", "PI"};
const String BASE = String(GRUPO) + "/camara";

// Protótipos (explícitos: o Arduino não precisa gerar automaticamente)
float ah_sat(float t);
float clampf(float v, float lo, float hi);
float ruido(float a);
float sp_efetivo();
void planta_step(float dt);
void ler_sensores();
void ler_pot();
void controle(float dt);
int duty(float pct);
void aplicar_saidas();
void linhas_oled(char l[6][22]);
void desenhar_oled();
bool aplicar(const char *nome, JsonVariantConst v, const char *origem);
void ao_receber(char *topic, byte *payload, unsigned int len);
void publicar_telemetria();
void manter_conexoes();
void ler_botao_chave();
void set_planta_virtual(bool v);
void setup();
void loop();

// Objetos
WiFiClient wifi;
PubSubClient mqtt(wifi);
DHTesp dht;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
bool oledOk = false;

// Comandos (graváveis por MQTT)
struct Comandos {
  bool habilitado = true;
  int modo = 1;               // 0 MANUAL, 1 ON/OFF, 2 PI
  int fonte_sp = 0;           // 0 remoto, 1 potenciômetro
  float setpoint = 35.0;
  float aquecedor_cmd = 0, ventilador_cmd = 20;
  bool falha_dht = false;     // simulação de falha do sensor
  bool planta_virtual = false; // definido pela chave do GPIO27 no setup()
};
Comandos cmd;

// Medições, atuadores e estado
float temp = 25, umid = 60;           // última leitura válida (da câmara)
float t_amb = 25, ur_amb = 60;        // ambiente (DHT22 quando a planta é virtual)
int pot_raw = 0;
bool dht_ok = true;
int dht_erros = 0, falhas_seguidas = 0;
float aq_pwm = 0, ve_pwm = 0, integral = 0;
bool onoff_aquecendo = false;
int alarme = 0, estado = 0;
uint16_t heartbeat = 0;

// Planta virtual (mesmo modelo do camara_model.py)
const float P_MAX = 25, C_H = 20, C_C = 120, S_UMID = 0.01;
float Th = 25, Tc = 25, AH = 13.8;

float ah_sat(float t) {   // umidade absoluta de saturação (g/m³), Magnus
  return 6.112 * expf(17.67 * t / (t + 243.5)) * 2.1674 / (273.15 + t) * 100;
}
float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
float ruido(float a) { return a * (random(-1000, 1001) / 1000.0); }
float sp_efetivo() {
  if (cmd.fonte_sp == 1) return roundf((SP_MIN + pot_raw / 4095.0 * (SP_MAX - SP_MIN)) * 2) / 2;
  return cmd.setpoint;
}

void planta_step(float dt) {
  float fan = ve_pwm / 100, p = P_MAX * aq_pwm / 100;
  float k_hc = 1.0 + fan, k_loss = 0.4 + 1.6 * fan, k_v = 0.002 + 0.02 * fan;
  float ah_amb = ah_sat(t_amb) * ur_amb / 100;
  int n = max(1, (int)(dt / 0.05));
  float h = dt / n;
  for (int i = 0; i < n; i++) {
    float q = k_hc * (Th - Tc);
    Th += h * (p - q) / C_H;
    Tc += h * (q - k_loss * (Tc - t_amb)) / C_C;
    AH += h * (S_UMID + k_v * (ah_amb - AH));
  }
}

// Ao ligar a planta virtual, ela parte da última medição (sem degrau)
void set_planta_virtual(bool v) {
  if (v && !cmd.planta_virtual) {
    Tc = Th = temp;
    AH = ah_sat(temp) * umid / 100;
  }
  cmd.planta_virtual = v;
}

void ler_sensores() {
  TempAndHumidity th = dht.getTempAndHumidity();
  bool erro = cmd.falha_dht || dht.getStatus() != DHTesp::ERROR_NONE || isnan(th.temperature);
  if (erro) {
    dht_erros++;
    falhas_seguidas++;
  } else {
    falhas_seguidas = 0;
    if (cmd.planta_virtual) {            // DHT22 = ambiente; câmara = modelo
      t_amb = th.temperature;
      ur_amb = th.humidity;
      temp = roundf((Tc + ruido(0.1)) * 10) / 10;
      umid = roundf(clampf(AH / ah_sat(Tc) * 100 + ruido(0.5), 0, 100) * 10) / 10;
    } else {                             // câmara real: DHT22 dentro da câmara
      temp = roundf(th.temperature * 10) / 10;
      umid = roundf(th.humidity * 10) / 10;
    }
  }
  dht_ok = falhas_seguidas < 3;
}

void ler_pot() {
  long s = 0;
  for (int i = 0; i < 4; i++) s += analogRead(PIN_POT);
  pot_raw = s / 4;
}

void controle(float dt) {
  float sp = sp_efetivo(), e = sp - temp;
  int alm = alarme;                                   // proteções com histerese
  if (!dht_ok) alm |= 2; else alm &= ~2;
  if (temp >= T_ALARME) alm |= 1; else if ((alm & 1) && temp < T_LIBERA) alm &= ~1;
  if (alm != alarme) Serial.printf("[planta] alarme %d -> %d\n", alarme, alm);
  alarme = alm;

  float aq, ve;
  if (alarme) { aq = 0; ve = 100; }
  else if (!cmd.habilitado) { aq = 0; ve = 0; integral = 0; }
  else if (cmd.modo == 0) { aq = cmd.aquecedor_cmd; ve = cmd.ventilador_cmd; }
  else if (cmd.modo == 1) {                           // ON/OFF ±0,5 °C
    if (temp < sp - 0.5) onoff_aquecendo = true;
    else if (temp > sp + 0.5) onoff_aquecendo = false;
    aq = onoff_aquecendo ? 100 : 0;
    ve = temp > sp + 2 ? 100 : 20;
  } else {                                            // PI com anti-windup
    const float kp = 15, ki = 0.15;
    float u = kp * e + integral;
    if ((u > 0 && u < 100) || (u >= 100 && e < 0) || (u <= 0 && e > 0))
      integral = clampf(integral + ki * e * dt, 0, 100);
    aq = clampf(kp * e + integral, 0, 100);
    ve = 20 + clampf(30 * (-e - 0.5), 0, 80);
  }
  aq_pwm = roundf(aq * 10) / 10;
  ve_pwm = roundf(ve * 10) / 10;

  if (alarme) estado = 4;
  else if (!cmd.habilitado) estado = 0;
  else if (fabsf(e) <= 1) estado = 3;
  else estado = e > 0 ? 1 : 2;
}

int duty(float pct) { return lroundf(pct * 255 / 100); }

void aplicar_saidas() {
  ledcWrite(PIN_AQUEC, duty(aq_pwm));
  ledcWrite(PIN_VENT, duty(ve_pwm));
  digitalWrite(PIN_LED_VERDE, estado == 3);
  digitalWrite(PIN_LED_AMARELO, estado == 1 || estado == 2);
  digitalWrite(PIN_LED_VERMELHO, estado == 4);
}

// ------------------------------------------------------------- OLED
void linhas_oled(char l[6][22]) {
  snprintf(l[0], 22, "CAMARA CLIMATICA");
  if (dht_ok) snprintf(l[1], 22, "T:%5.1fC UR:%5.1f%%", temp, umid);
  else snprintf(l[1], 22, "T: --.-C UR: --.-%%");
  snprintf(l[2], 22, "SP:%5.1fC %s %s", sp_efetivo(), cmd.fonte_sp ? "POT" : "REM", MODOS[cmd.modo]);
  snprintf(l[3], 22, "AQ:%3.0f%% VENT:%3.0f%%", aq_pwm, ve_pwm);
  snprintf(l[4], 22, "EST: %s", ESTADOS[estado]);
  if (alarme) snprintf(l[5], 22, "%s%s", (alarme & 1) ? "!SOBRETEMP " : "", (alarme & 2) ? "!SENSOR" : "");
  else snprintf(l[5], 22, "%s MQTT:%s", cmd.planta_virtual ? "VIRT" : "REAL", mqtt.connected() ? "OK" : "--");
}

void desenhar_oled() {
  if (!oledOk) return;
  char l[6][22];
  linhas_oled(l);
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  for (int i = 0; i < 6; i++) {
    oled.setCursor(0, i == 0 ? 0 : 6 + i * 9);   // 1ª linha na faixa amarela (bicolor)
    oled.print(l[i]);
  }
  oled.display();
}

// ------------------------------------------------------------- comandos
bool aplicar(const char *nome, JsonVariantConst v, const char *origem) {
  float x;
  if (v.is<bool>()) x = v.as<bool>() ? 1 : 0;
  else if (v.is<const char *>()) {
    String s = v.as<const char *>(); s.trim(); s.toLowerCase();
    if (s == "true" || s == "on") x = 1;
    else if (s == "false" || s == "off") x = 0;
    else x = s.toFloat();
  } else x = v.as<float>();

  String n = nome;
  if (n == "habilitado") cmd.habilitado = x >= 0.5;
  else if (n == "modo") { int m = (int)clampf(lroundf(x), 0, 2); if (m != cmd.modo) integral = 0; cmd.modo = m; }
  else if (n == "fonte_sp") cmd.fonte_sp = (int)clampf(lroundf(x), 0, 1);
  else if (n == "setpoint") cmd.setpoint = roundf(clampf(x, SP_MIN, SP_MAX) * 10) / 10;
  else if (n == "aquecedor_cmd") cmd.aquecedor_cmd = roundf(clampf(x, 0, 100) * 10) / 10;
  else if (n == "ventilador_cmd") cmd.ventilador_cmd = roundf(clampf(x, 0, 100) * 10) / 10;
  else if (n == "falha_dht") cmd.falha_dht = x >= 0.5;
  else if (n == "planta_virtual") set_planta_virtual(x >= 0.5);
  else if (n == "pot_raw") { Serial.println("[cmd] pot_raw ignorado: o potenciômetro é físico (gire o knob)"); return false; }
  else { Serial.printf("[cmd] %s: campo desconhecido '%s'\n", origem, nome); return false; }
  Serial.printf("[cmd] %s: %s = %g\n", origem, nome, x);
  return true;
}

void ao_receber(char *topic, byte *payload, unsigned int len) {
  String t = topic;
  JsonDocument doc;
  if (t == BASE + "/cmd") {
    if (deserializeJson(doc, payload, len) || !doc.is<JsonObjectConst>()) {
      Serial.println("[mqtt] JSON inválido em /cmd");
      return;
    }
    for (JsonPairConst kv : doc.as<JsonObjectConst>()) aplicar(kv.key().c_str(), kv.value(), "mqtt");
  } else {
    String campo = t.substring(t.lastIndexOf('/') + 1);
    if (deserializeJson(doc, payload, len)) {           // não é JSON: trata como texto
      String s((const char *)payload, len);
      doc.clear();
      doc.set(s);
    }
    aplicar(campo.c_str(), doc.as<JsonVariantConst>(), "mqtt");
  }
}

// ------------------------------------------------------------- MQTT
void publicar_telemetria() {
  if (!mqtt.connected()) return;
  float sp = sp_efetivo();
  JsonDocument d;
  d["temp"] = temp;                 d["umid"] = umid;
  d["pot_raw"] = pot_raw;           d["sp_efetivo"] = sp;
  d["aquecedor_pwm"] = aq_pwm;      d["ventilador_pwm"] = ve_pwm;
  d["aquecedor_duty"] = duty(aq_pwm); d["ventilador_duty"] = duty(ve_pwm);
  d["habilitado"] = (int)cmd.habilitado;
  d["modo"] = cmd.modo;             d["modo_txt"] = MODOS[cmd.modo];
  d["fonte_sp"] = cmd.fonte_sp;     d["setpoint"] = cmd.setpoint;
  d["aquecedor_cmd"] = cmd.aquecedor_cmd; d["ventilador_cmd"] = cmd.ventilador_cmd;
  d["falha_dht"] = (int)cmd.falha_dht;
  d["pot_sim"] = pot_raw;           // aqui o potenciômetro é físico
  d["estado"] = estado;             d["estado_txt"] = ESTADOS[estado];
  d["alarme"] = alarme;
  d["led_verde"] = (int)(estado == 3);
  d["led_amarelo"] = (int)(estado == 1 || estado == 2);
  d["led_vermelho"] = (int)(estado == 4);
  d["dht_ok"] = (int)dht_ok;        d["dht_erros"] = dht_erros;
  d["heartbeat"] = heartbeat;       d["uptime"] = millis() / 1000;
  d["planta_virtual"] = (int)cmd.planta_virtual;
  d["origem"] = "esp32";
  char l[6][22];
  linhas_oled(l);
  JsonArray o = d["oled"].to<JsonArray>();
  String texto;
  for (int i = 0; i < 6; i++) { o.add(l[i]); texto += l[i]; if (i < 5) texto += "\n"; }

  static char buf[1400];
  size_t n = serializeJson(d, buf, sizeof(buf));
  mqtt.publish((BASE + "/telemetria").c_str(), (const uint8_t *)buf, n, false);
  mqtt.publish((BASE + "/oled").c_str(), texto.c_str());
}

void manter_conexoes() {
  static unsigned long t_mqtt = 0;
  static bool wifi_ok = false;
  bool w = WiFi.status() == WL_CONNECTED;
  if (w != wifi_ok) {
    wifi_ok = w;
    Serial.println(w ? "[wifi] conectado, IP " + WiFi.localIP().toString() : String("[wifi] desconectado"));
  }
  if (!w || mqtt.connected() || millis() - t_mqtt < 5000) return;
  t_mqtt = millis();
  String id = String("camara-esp32-") + String((uint32_t)ESP.getEfuseMac(), HEX);
  String st = BASE + "/status";
  Serial.printf("[mqtt] conectando a %s:%d ...\n", MQTT_HOST, MQTT_PORT);
  if (mqtt.connect(id.c_str(), st.c_str(), 1, true, "offline")) {
    mqtt.publish(st.c_str(), "online", true);
    mqtt.subscribe((BASE + "/cmd").c_str(), 1);
    mqtt.subscribe((BASE + "/cmd/+").c_str(), 1);
    Serial.printf("[mqtt] conectado; tópicos %s/#\n", BASE.c_str());
  } else {
    Serial.printf("[mqtt] falhou (rc=%d); nova tentativa em 5 s\n", mqtt.state());
  }
}

// ------------------------------------------------------------- botão e chave
void ler_botao_chave() {
  static bool ult_botao = HIGH, ult_chave = digitalRead(PIN_CHAVE);
  static unsigned long t_botao = 0;
  bool b = digitalRead(PIN_BOTAO);
  if (b != ult_botao && millis() - t_botao > 50) {
    t_botao = millis();
    ult_botao = b;
    if (b == LOW) {
      cmd.habilitado = !cmd.habilitado;
      Serial.printf("[botao] habilitado = %d\n", cmd.habilitado);
    }
  }
  bool c = digitalRead(PIN_CHAVE);   // esquerda (GND) = planta virtual; direita = DHT22 real
  if (c != ult_chave) {
    ult_chave = c;
    set_planta_virtual(c == LOW);
    Serial.printf("[chave] planta virtual = %d\n", cmd.planta_virtual);
  }
}

// ------------------------------------------------------------- setup / loop
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_AMARELO, OUTPUT);
  pinMode(PIN_LED_VERMELHO, OUTPUT);
  pinMode(PIN_BOTAO, INPUT_PULLUP);
  pinMode(PIN_CHAVE, INPUT_PULLUP);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_POT, ADC_11db);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_AQUEC, PWM_FREQ_AQUEC, PWM_BITS);
  ledcAttach(PIN_VENT, PWM_FREQ_VENT, PWM_BITS);
#else
#error "Use o core ESP32 do Arduino 3.x (o Wokwi já usa)"
#endif
  dht.setup(PIN_DHT, DHTesp::DHT22);
  Wire.begin(21, 22);
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) Serial.println("[oled] SSD1306 não encontrado");
  randomSeed(esp_random());
  set_planta_virtual(digitalRead(PIN_CHAVE) == LOW);    // chave à esquerda = virtual

  AH = ah_sat(t_amb) * ur_amb / 100;
  Serial.printf("\nCâmara climática %s · planta %s\n", GRUPO, cmd.planta_virtual ? "VIRTUAL" : "REAL");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CANAL);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(ao_receber);
  mqtt.setBufferSize(1536);
  mqtt.setKeepAlive(30);
  ler_pot();
}

void loop() {
  static unsigned long t_ant = millis(), t_dht = 0, t_ctrl = 0, t_pub = 0, t_oled = 0;
  unsigned long agora = millis();
  float dt = (agora - t_ant) / 1000.0;
  t_ant = agora;

  if (cmd.planta_virtual) planta_step(dt);
  ler_botao_chave();

  if (agora - t_dht >= 2000) { t_dht = agora; ler_sensores(); }      // DHT22: 0,5 Hz
  if (agora - t_ctrl >= 1000) {                                       // controle: 1 Hz
    float dtc = t_ctrl ? (agora - t_ctrl) / 1000.0 : 1.0;
    t_ctrl = agora;
    ler_pot();
    controle(dtc);
    aplicar_saidas();
    heartbeat++;
  }
  if (agora - t_oled >= 500) { t_oled = agora; desenhar_oled(); }

  manter_conexoes();
  mqtt.loop();
  if (agora - t_pub >= 2000) { t_pub = agora; publicar_telemetria(); }
  delay(10);
}
