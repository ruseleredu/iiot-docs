"""
Adaptador MQTT (paho-mqtt 2.x, MQTT v5) - é o que o firmware do ESP32 real faria.

Tópicos (base = <grupo>/camara, ex.: lab05-a/camara — convenção do LAB IoT):

  <base>/status       "online" / "offline"   (retido; "offline" é o Last Will)
  <base>/telemetria   JSON com todas as variáveis, a cada --mqtt-period s (padrão 2 s)
  <base>/oled         texto da tela OLED (6 linhas), a cada publicação
  <base>/cmd          JSON parcial, ex.: {"setpoint": 40, "modo": 2}
  <base>/cmd/<campo>  valor simples, ex.: lab05-a/camara/cmd/setpoint  ->  40

Campos aceitos em cmd: habilitado, modo, fonte_sp, setpoint, aquecedor_cmd,
ventilador_cmd, pot_raw (simulação), falha_dht (simulação).
"""

import json
import uuid

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties


class MqttAdapter:
    def __init__(self, camara, log, host, port=1883, base="camara",
                 user=None, password=None, v5=True):
        self.cam, self.log = camara, log
        self.host, self.port, self.base = host, port, base.rstrip("/")
        self.v5 = v5
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"camara-sim-{uuid.uuid4().hex[:6]}",
            protocol=mqtt.MQTTv5 if v5 else mqtt.MQTTv311,
        )
        if user:
            self.client.username_pw_set(user, password)
        self.client.will_set(f"{self.base}/status", "offline", qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_connect_fail = self._on_connect_fail
        self.client.reconnect_delay_set(1, 10)
        self.connected = False

    def start(self):
        kw = {"clean_start": True} if self.v5 else {}
        self.client.connect_async(self.host, self.port, keepalive=30, **kw)
        self.client.loop_start()           # thread própria, reconecta sozinho
        self.log(f"[mqtt] conectando a {self.host}:{self.port}, base '{self.base}'")

    def _on_connect(self, client, _ud, _flags, reason_code, _props):
        if reason_code.is_failure:
            self.log(f"[mqtt] falha na conexão: {reason_code}")
            return
        self.connected = True
        client.publish(f"{self.base}/status", "online", qos=1, retain=True)
        client.subscribe([(f"{self.base}/cmd", 1), (f"{self.base}/cmd/+", 1)])
        self.log(f"[mqtt] conectado; assinando {self.base}/cmd e {self.base}/cmd/+")

    def _on_connect_fail(self, _client, _ud):
        self.log(f"[mqtt] broker {self.host}:{self.port} inacessível; tentando de novo... "
                 "(os outros protocolos seguem funcionando)")

    def _on_disconnect(self, _c, _ud, _flags, reason_code, _props):
        self.connected = False
        self.log(f"[mqtt] desconectado ({reason_code}); tentando de novo...")

    def _on_message(self, _client, _ud, msg):
        payload = msg.payload.decode(errors="replace").strip()
        if msg.topic == f"{self.base}/cmd":
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                self.log(f"[mqtt] JSON inválido em {msg.topic}: {payload!r}")
                return
            if isinstance(data, dict):
                for k, v in data.items():
                    self.cam.aplicar(k, v, "mqtt")
        else:
            campo = msg.topic.rsplit("/", 1)[-1]
            try:
                valor = json.loads(payload)
            except json.JSONDecodeError:
                valor = payload
            self.cam.aplicar(campo, valor, "mqtt")

    def publish(self, s):
        if not self.connected:
            return
        props = None
        if self.v5:
            props = Properties(PacketTypes.PUBLISH)
            props.ContentType = "application/json"
            props.MessageExpiryInterval = 10
        self.client.publish(f"{self.base}/telemetria", json.dumps(s), qos=0, properties=props)
        self.client.publish(f"{self.base}/oled", "\n".join(s["oled"]), qos=0)

    def stop(self):
        try:
            self.client.publish(f"{self.base}/status", "offline", qos=1, retain=True).wait_for_publish(2)
        except Exception:  # noqa: BLE001
            pass
        self.client.loop_stop()
        self.client.disconnect()
