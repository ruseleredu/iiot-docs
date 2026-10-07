"""
Gera os fluxos do Node-RED para a câmara simulada de UM grupo do LAB IoT.

    py gerar_flows.py --grupo lab05-a                 # -> flows/camara-lab05-a.json
    py gerar_flows.py --grupo lab05-a --saida x.json

Compatível com o Node-RED criado por gen_iot_scada_portal.py (laboratório e kit):
  - broker "mosquitto:1883", tópicos <grupo>/camara/...
  - simulador em "<grupo>-camara" (Modbus 502/5021, S7 102, OPC-UA 4840)
  - dashboard em <base>/<grupo>/dashboard/camara
  - SQLite em /data/camara.sqlite (volume do grupo)
  - alarmes avisados no ntfy do grupo (NTFY_URL, NTFY_TOPIC, NTFY_TOKEN do container)
Abas: Dashboard · Banco SQLite · Controle Node-RED · Modbus / S7 / OPC-UA
"""
import argparse
import hashlib
import json
import os
import re

ap = argparse.ArgumentParser(description="Fluxos Node-RED da câmara climática")
ap.add_argument("--grupo", required=True, help="grupo do LAB IoT, ex.: lab05-a")
ap.add_argument("--saida", default=None, help="arquivo de saída (padrão: flows/camara-<grupo>.json)")
ap.add_argument("--host-sim", default=None, help="host do simulador (padrão: <grupo>-camara)")
ap.add_argument("--host-mqtt", default="mosquitto", help="broker MQTT (padrão: mosquitto)")
ap.add_argument("--porta-modbus", default="502")
ap.add_argument("--porta-s7", default="102")
ap.add_argument("--db", default="/data/camara.sqlite", help="arquivo SQLite")
A = ap.parse_args()
GRUPO = A.grupo.lower()
if not re.fullmatch(r"[a-z][a-z0-9]{1,20}-[a-z]", GRUPO):
    raise SystemExit("--grupo no formato do LAB IoT: <lab>-<letra>, ex.: lab05-a")
BASE = f"{GRUPO}/camara"
SIM = A.host_sim or f"{GRUPO}-camara"
P_MTCP = A.porta_modbus
P_S7 = A.porta_s7
DB_PATH = A.db
SAIDA = A.saida or os.path.join("flows", f"camara-{GRUPO}.json")
# ids estáveis por grupo (reimportar substitui em vez de duplicar)
_PFX = hashlib.sha1(GRUPO.encode()).hexdigest()[:4]

nodes = []
_c = [0]


def nid():
    _c[0] += 1
    return f"{_PFX}{_c[0]:012x}"


def node(type_, z=None, x=None, y=None, **kw):
    n = {"id": kw.pop("id", None) or nid(), "type": type_}
    if z:
        n["z"] = z
    n.update(kw)
    if z:
        n["x"], n["y"] = x, y
        n.setdefault("wires", [])
    nodes.append(n)
    return n


# ======================================================== config nodes
BROKER = node("mqtt-broker", id=f"{_PFX}b0000000000b", name="mosquitto (LAB IoT)",
              broker=A.host_mqtt, port="1883", clientid="",
              autoConnect=True, usetls=False, protocolVersion="5", keepalive="60",
              cleansession=True, autoUnsubscribe=True,
              birthTopic=f"{GRUPO}/nodered/status", birthQos="1", birthRetain="true", birthPayload="online",
              birthMsg={}, closeTopic=f"{GRUPO}/nodered/status", closeQos="1", closeRetain="true",
              closePayload="offline", closeMsg={}, willTopic=f"{GRUPO}/nodered/status", willQos="1",
              willRetain="true", willPayload="offline", willMsg={}, userProps="", sessionExpiry="")
DB = node("sqlitedb", id=f"{_PFX}d0000000000d", db=DB_PATH, mode="RWC")
UIBASE = node("ui-base", id=f"{_PFX}a0000000000a", name=f"Dashboard {GRUPO}", path="/dashboard",
              appIcon="", includeClientData=True,
              acceptsClientConfig=["ui-notification", "ui-control", "ui-led"],
              showPathInSidebar=False, headerContent="page", navigationStyle="default",
              titleBarStyle="default", showReconnectNotification=True, notificationDisplayTime=1,
              showDisconnectNotification=True, allowInstall=False)
THEME = node("ui-theme", id=f"{_PFX}e0000000000e", name="Tema Câmara",
             colors={"surface": "#263238", "primary": "#ef6c00", "bgPage": "#eceff1",
                     "groupBg": "#ffffff", "groupOutline": "#cfd8dc"},
             sizes={"density": "default", "pagePadding": "12px", "groupGap": "12px",
                    "groupBorderRadius": "6px", "widgetGap": "12px"})
PAGE = node("ui-page", id=f"{_PFX}f0000000000f", name="Câmara Climática", ui=UIBASE["id"],
            path="/camara", icon="thermometer", layout="grid", theme=THEME["id"],
            breakpoints=[{"name": "Default", "px": 0, "cols": 3}, {"name": "Tablet", "px": 576, "cols": 6},
                         {"name": "Small Desktop", "px": 768, "cols": 9},
                         {"name": "Desktop", "px": 1024, "cols": 12}],
            order=1, className="", visible="true", disabled="false")


def group(name, width, order):
    return node("ui-group", name=name, page=PAGE["id"], width=width, height=1, order=order,
                showTitle=True, className="", visible="true", disabled="false",
                groupType="default")["id"]


G_MED = group("Medições (DHT22)", 4, 1)
G_EST = group("Estado da planta", 4, 2)
G_OLED = group("Tela OLED", 4, 3)
G_TEND = group("Tendência", 8, 4)
G_CMD = group("Comandos", 4, 5)
G_SIM = group("Simulação (bancada)", 4, 6)
G_CTRL = group("Controle externo (Node-RED)", 4, 7)
G_HIST = group("Histórico (SQLite)", 8, 8)


# ======================================================== helpers
def comment(z, x, y, name, info=""):
    return node("comment", z, x, y, name=name, info=info)["id"]


def debug(z, x, y, name, active=False, status=""):
    return node("debug", z, x, y, name=name, active=active, tosidebar=True, console=False,
                tostatus=bool(status), complete="payload", targetType="msg",
                statusVal=status, statusType="auto" if status else "auto")["id"]


def func(z, x, y, name, code, outputs=1, labels=None, init=""):
    n = node("function", z, x, y, name=name, func=code, outputs=outputs, timeout=0, noerr=0,
             initialize=init, finalize="", libs=[])
    if labels:
        n["outputLabels"] = labels
    return n


def mqtt_in(z, x, y, topic, name="", dt="auto-detect"):
    return node("mqtt in", z, x, y, name=name, topic=topic, qos="1", datatype=dt, broker=BROKER["id"],
                nl=False, rap=True, rh=0, inputs=0)


def mqtt_out(z, x, y, name="", topic=""):
    return node("mqtt out", z, x, y, name=name, topic=topic, qos="1", retain="false", respTopic="",
                contentType="", userProps="", correl="", expiry="", broker=BROKER["id"])["id"]


def inject(z, x, y, name, payload="", ptype="date", topic="", once=False, delay="1", repeat="",
           wires=None):
    return node("inject", z, x, y, name=name,
                props=[{"p": "payload"}, {"p": "topic", "vt": "str"}], repeat=repeat, crontab="",
                once=once, onceDelay=delay, topic=topic, payload=payload, payloadType=ptype,
                wires=wires or [])["id"]


def set_wires(n, *outs):
    n["wires"] = [list(o) for o in outs]


# ======================================================== ABA 1: Dashboard
T1 = node("tab", label="Câmara - Dashboard", disabled=False,
          info=f"Dashboard 2.0 da câmara climática. Recebe {BASE}/telemetria e "
               f"envia comandos em {BASE}/cmd/<campo>.")["id"]

comment(T1, 190, 40, "Telemetria do ESP32 (a cada 2 s) -> widgets",
        f"Tópico {BASE}/telemetria (JSON). Os widgets de comando só são\n"
        "atualizados quando o valor muda, para não 'brigar' com o usuário.")

DISTRIB = r"""// Distribui a telemetria do ESP32 para os widgets do dashboard.
const t = msg.payload;
if (typeof t !== "object" || t === null) return null;

// Widgets de comando: só atualiza quando o valor mudou no equipamento
// (evita que o slider "pule" enquanto o usuário arrasta).
const last = context.get("last") || {};
function seMudou(campo, valor) {
    if (last[campo] === valor) return null;
    last[campo] = valor;
    return { payload: valor };
}
const ALARMES = { 0: "Nenhum", 1: "Sobretemperatura (≥ 60 °C)", 2: "Falha do sensor DHT22",
                  3: "Sobretemperatura + falha do sensor" };

const out = [
    { payload: t.temp },                                                // 1 gauge temperatura
    { payload: t.umid },                                                // 2 gauge umidade
    [ { topic: "Temperatura", payload: t.temp },                        // 3 gráfico °C
      { topic: "Setpoint",    payload: t.sp_efetivo } ],
    [ { topic: "Umidade (%UR)", payload: t.umid },                      // 4 gráfico %
      { topic: "Aquecedor (%)", payload: t.aquecedor_pwm },
      { topic: "Ventilador (%)", payload: t.ventilador_pwm } ],
    { payload: `${t.sp_efetivo.toFixed(1)} °C (${t.fonte_sp ? "potenciômetro" : "remoto"})` }, // 5
    { payload: `${t.aquecedor_pwm.toFixed(0)} %  /  ${t.ventilador_pwm.toFixed(0)} %` },     // 6
    { payload: { verde: t.led_verde, amarelo: t.led_amarelo,            // 7 LEDs de estado
                 vermelho: t.led_vermelho } },
    { payload: `${t.estado_txt} · modo ${t.modo_txt}` },                // 8 estado
    { payload: ALARMES[t.alarme] || t.alarme },                         // 9 alarme
    { payload: t.oled },                                                // 10 OLED
    seMudou("habilitado", !!t.habilitado),                              // 11
    seMudou("modo", t.modo),                                            // 12
    seMudou("fonte_sp", t.fonte_sp),                                    // 13
    seMudou("setpoint", t.setpoint),                                    // 14
    seMudou("aquecedor_cmd", t.aquecedor_cmd),                          // 15
    seMudou("ventilador_cmd", t.ventilador_cmd),                        // 16
    seMudou("pot_raw", t.pot_sim),                                      // 17
    seMudou("falha_dht", !!t.falha_dht),                                // 18
];
context.set("last", last);
return out;
"""
labels = ["temp", "umid", "gráfico °C", "gráfico %", "SP efetivo", "PWMs", "LEDs", "estado", "alarme", "OLED", "habilitado", "modo",
          "fonte SP", "setpoint", "aquecedor_cmd", "ventilador_cmd", "pot_raw", "falha_dht"]
m_tel = mqtt_in(T1, 140, 300, f"{BASE}/telemetria", "telemetria", "json")
dist = func(T1, 400, 300, "Distribui telemetria", DISTRIB, 18, labels)
set_wires(m_tel, [dist["id"]])

MQ1 = mqtt_out(T1, 1180, 760, "comandos -> ESP32")
X = 820
outs = []
order = {}


def nextorder(g):
    order[g] = order.get(g, 0) + 1
    return order[g]


def gauge(y, title, units, mn, mx, segs):
    return node("ui-gauge", T1, X, y, name=title, group=G_MED, order=nextorder(G_MED), value="payload",
                valueType="msg", width=2, height=3, gtype="gauge-half", gstyle="rounded",
                title=title, alwaysShowTitle=True, floatingTitlePosition="top-left", units=units,
                icon="", prefix="", suffix="", segments=segs, min=mn, max=mx, sizeThickness=16,
                sizeGap=4, sizeKeyThickness=8, styleRounded=True, styleGlow=False, className="")["id"]


def text(g, y, label, name=None):
    return node("ui-text", T1, X, y, name=name or label, group=g, order=nextorder(g), width=0, height=0,
                label=label, format="{{msg.payload}}", layout="row-spread", style=False,
                font="Helvetica", fontSize=16, color="#717171", wrapText=False, className="",
                value="payload", valueType="msg")["id"]


def led(y, label, color):
    return node("ui-led", T1, X, y, name=label, group=G_EST, order=nextorder(G_EST), width=0, height=0,
                label=label, labelPlacement="right", labelAlignment="left",
                states=[{"value": "0", "valueType": "num", "color": "#455a64"},
                        {"value": "1", "valueType": "num", "color": color}],
                allowColorForValueInMessage=False, shape="circle", showBorder=True, showGlow=True)["id"]


def chart(y, label, ylabel, ymin, ymax, colors):
    return node("ui-chart", T1, X, y, name=label, group=G_TEND, label=label, order=nextorder(G_TEND),
                chartType="line", category="topic", categoryType="msg", xAxisLabel="",
                xAxisProperty="", xAxisPropertyType="timestamp", xAxisType="time", xAxisFormat="",
                xAxisFormatType="auto", xmin="", xmax="", yAxisLabel=ylabel, yAxisProperty="payload",
                yAxisPropertyType="msg", ymin=ymin, ymax=ymax, bins=10, action="append",
                stackSeries=False, pointShape="false", pointRadius=4, showLegend=True,
                removeOlder="15", removeOlderUnit="60", removeOlderPoints="", colors=colors,
                textColor=["#666666"], textColorDefault=True, gridColor=["#e5e5e5"],
                gridColorDefault=True, width=8, height=4, className="", interpolation="linear")["id"]


def cmd_topic(campo):
    return f"{BASE}/cmd/{campo}"


def switch(g, y, label, campo, z=T1, x=X, topic=None):
    return node("ui-switch", z, x, y, name=label, label=label, group=g, order=nextorder(g), width=0,
                height=0, passthru=False, decouple=False, topic=topic or cmd_topic(campo),
                topicType="str", style="", className="", layout="row-spread", clickableArea="switch",
                onvalue="true", onvalueType="bool", onicon="", oncolor="", offvalue="false",
                offvalueType="bool", officon="", offcolor="")


def dropdown(g, y, label, campo, opts):
    return node("ui-dropdown", T1, X, y, name=label, label=label, tooltip="", group=g,
                order=nextorder(g), width=0, height=0, passthru=False, multiple=False, chips=False,
                clearable=False, options=[{"label": l, "value": v, "type": "num"} for v, l in opts],
                payload="", topic=cmd_topic(campo), topicType="str", className="",
                typeIsComboBox=True, msgTrigger="onChange")


def slider(g, y, label, campo, mn, mx, step):
    return node("ui-slider", T1, X, y, name=label, label=label, tooltip="", group=g,
                order=nextorder(g), width=0, height=0, passthru=False, outs="end",
                topic=cmd_topic(campo), topicType="str", thumbLabel="always", showTicks="false",
                min=mn, max=mx, step=step, className="", iconPrepend="", iconAppend="", color="",
                colorTrack="", colorThumb="", showTextField=True)


OLED_TPL = r"""<template>
  <!-- Réplica da tela SSD1306 128x64 (2 linhas amarelas + 6 azuis no modelo bicolor) -->
  <div class="oled">
    <div v-for="(l, i) in linhas" :key="i" :class="{ topo: i === 0 }">{{ l || ' ' }}</div>
  </div>
</template>

<script>
export default {
  computed: {
    linhas () {
      return Array.isArray(this.msg?.payload) ? this.msg.payload : ['(aguardando ESP32...)']
    }
  }
}
</script>

<style scoped>
.oled {
  background: #000; color: #5ec8ff; font-family: 'Courier New', monospace;
  font-size: 15px; line-height: 1.3; padding: 10px 14px; border-radius: 6px;
  border: 8px solid #1c1c1c; white-space: pre; width: fit-content; min-width: 23ch;
  margin: 0 auto; box-shadow: inset 0 0 12px rgba(94,200,255,.15);
}
.topo { color: #ffd84d; border-bottom: 1px dashed #333; margin-bottom: 4px; }
</style>
"""

LEDS_TPL = r"""<template>
  <!-- LEDs de estado do ESP32 (GPIO16 verde, GPIO17 amarelo, GPIO5 vermelho) -->
  <div class="leds">
    <div v-for="l in leds" :key="l.k" class="led-row">
      <span class="led" :style="estilo(l)"></span><span>{{ l.txt }}</span>
    </div>
  </div>
</template>

<script>
export default {
  data () {
    return { leds: [
      { k: 'verde', cor: '#00e676', txt: 'Verde - estável' },
      { k: 'amarelo', cor: '#ffc400', txt: 'Amarelo - aquecendo / resfriando' },
      { k: 'vermelho', cor: '#ff1744', txt: 'Vermelho - alarme' }
    ] }
  },
  methods: {
    estilo (l) {
      const on = this.msg?.payload?.[l.k] === 1
      return { background: on ? l.cor : '#455a64', boxShadow: on ? `0 0 10px 3px ${l.cor}` : 'none' }
    }
  }
}
</script>

<style scoped>
.leds { display: flex; flex-direction: column; gap: 10px; padding: 4px 0; }
.led-row { display: flex; align-items: center; gap: 12px; }
.led { width: 20px; height: 20px; border-radius: 50%; border: 2px solid #263238; transition: all .3s; }
</style>
"""

w = []
w.append(gauge(60, "Temperatura", "°C", 0, 70,
               [{"from": "0", "color": "#42a5f5"}, {"from": "30", "color": "#66bb6a"},
                {"from": "55", "color": "#ffa726"}, {"from": "60", "color": "#ef5350"}]))
w.append(gauge(100, "Umidade", "%UR", 0, 100,
               [{"from": "0", "color": "#ffb74d"}, {"from": "30", "color": "#66bb6a"},
                {"from": "70", "color": "#42a5f5"}]))
w.append(chart(140, "Temperatura e setpoint", "°C", "20", "65", ["#e53935", "#fb8c00"]))
w.append(chart(180, "Umidade e atuadores", "%", "0", "100", ["#1e88e5", "#d81b60", "#43a047"]))
w.append(text(G_MED, 220, "Setpoint efetivo"))
w.append(text(G_MED, 260, "Aquecedor / ventilador"))
w.append(node("ui-template", T1, X, 340, name="LEDs de estado", group=G_EST, page="", ui="",
              order=nextorder(G_EST), width=0, height=0, head="", format=LEDS_TPL, storeOutMessages=True,
              passthru=False, resendOnRefresh=True, templateScope="local", className="")["id"])
w.append(text(G_EST, 420, "Estado"))
w.append(text(G_EST, 460, "Alarme"))
w.append(node("ui-template", T1, X, 500, name="OLED SSD1306", group=G_OLED, page="", ui="",
              order=1, width=0, height=0, head="", format=OLED_TPL, storeOutMessages=True,
              passthru=False, resendOnRefresh=True, templateScope="local", className="")["id"])

cmd_nodes = [
    switch(G_CMD, 540, "Habilitado", "habilitado"),
    dropdown(G_CMD, 580, "Modo de controle", "modo", [(0, "0 - MANUAL"), (1, "1 - ON/OFF"), (2, "2 - PI")]),
    dropdown(G_CMD, 620, "Fonte do setpoint", "fonte_sp", [(0, "Remoto (dashboard)"), (1, "Potenciômetro")]),
    slider(G_CMD, 660, "Setpoint (°C)", "setpoint", 20, 55, 0.5),
    slider(G_CMD, 700, "Aquecedor - manual (%)", "aquecedor_cmd", 0, 100, 5),
    slider(G_CMD, 740, "Ventilador - manual (%)", "ventilador_cmd", 0, 100, 5),
    slider(G_SIM, 780, "Potenciômetro (ADC 0..4095)", "pot_raw", 0, 4095, 1),
    switch(G_SIM, 820, "Injetar falha no DHT22", "falha_dht"),
]
for c in cmd_nodes:
    c["wires"] = [[MQ1]]
w += [c["id"] for c in cmd_nodes]
set_wires(dist, *[[i] for i in w])

m_st = mqtt_in(T1, 150, 880, f"{BASE}/status", "status do ESP32 (LWT)", "utf8")
st_fmt = func(T1, 400, 880, "formata status",
              'msg.payload = msg.payload === "online" ? "🟢 online" : "🔴 offline (Last Will)";\nreturn msg;')
st_txt = text(G_EST, 920, "ESP32 (MQTT)")
st_fmt["x"], st_fmt["y"] = 400, 880
nodes[-1]["x"], nodes[-1]["y"] = X, 880
set_wires(m_st, [st_fmt["id"]])
set_wires(st_fmt, [st_txt])

# ======================================================== ABA 2: SQLite
T2 = node("tab", label="Câmara - Banco SQLite", disabled=False,
          info=f"Grava a telemetria (1 amostra a cada 10 s) em {DB_PATH}.")["id"]
comment(T2, 170, 40, "Estrutura do banco")
SQL_CREATE = """CREATE TABLE IF NOT EXISTS camara_dados (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      DATETIME DEFAULT (datetime('now','localtime')),
    temp           REAL,     -- °C (DHT22)
    umid           REAL,     -- %UR (DHT22)
    sp_efetivo     REAL,     -- °C
    fonte_sp       INTEGER,  -- 0 remoto, 1 potenciômetro
    pot_raw        INTEGER,  -- ADC 0..4095
    aquecedor_pwm  REAL,     -- %
    ventilador_pwm REAL,     -- %
    modo           INTEGER,  -- 0 MANUAL, 1 ON/OFF, 2 PI
    estado         INTEGER,  -- 0 DESLIGADO .. 4 ALARME
    estado_txt     TEXT,
    alarme         INTEGER,  -- bit0 sobretemp, bit1 sensor
    dht_ok         INTEGER
);"""
sql_n = node("sqlite", T2, 640, 100, mydb=DB["id"], sqlquery="msg.topic", sql="", name="camara.sqlite")
dbg_sql = debug(T2, 860, 100, "resultado SQL", True)
set_wires(sql_n, [dbg_sql])
inject(T2, 170, 100, "Criar tabela (automático)", "", "date", SQL_CREATE, once=True, delay="0.5",
       wires=[[sql_n["id"]]])

QUERIES = [
    ("Últimos 10 registros", "SELECT * FROM camara_dados ORDER BY id DESC LIMIT 10;"),
    ("Médias por estado (última hora)",
     "SELECT estado_txt, COUNT(*) AS n, ROUND(AVG(temp),2) AS temp_media, ROUND(AVG(umid),1) AS umid_media, "
     "ROUND(AVG(aquecedor_pwm),1) AS aq_medio FROM camara_dados "
     "WHERE timestamp >= datetime('now','localtime','-1 hour') GROUP BY estado_txt;"),
    ("Erro médio |SP - T| por modo",
     "SELECT modo, COUNT(*) AS n, ROUND(AVG(ABS(sp_efetivo - temp)),2) AS erro_medio, "
     "ROUND(MAX(temp),1) AS temp_max FROM camara_dados WHERE estado <> 0 GROUP BY modo;"),
    ("Eventos de alarme", "SELECT timestamp, temp, alarme, estado_txt FROM camara_dados "
                          "WHERE alarme <> 0 ORDER BY id DESC LIMIT 20;"),
    ("Apagar dados", "DELETE FROM camara_dados;"),
    ("Apagar tabela", "DROP TABLE IF EXISTS camara_dados;"),
]
for i, (nm, q) in enumerate(QUERIES):
    inject(T2, 190, 160 + i * 40, nm, "", "date", q, wires=[[sql_n["id"]]])

comment(T2, 170, 440, "Gravação: telemetria -> 1 amostra/10 s -> INSERT preparado")
m_tel2 = mqtt_in(T2, 140, 500, f"{BASE}/telemetria", "telemetria", "json")
lim = node("delay", T2, 360, 500, name="1 msg / 10 s", pauseType="rate", timeout="5",
           timeoutUnits="seconds", rate="1", nbRateUnits="10", rateUnits="second",
           randomFirst="1", randomLast="5", randomUnits="seconds", drop=True,
           allowrate=False, outputs=1)
INS_FN = r"""// Statement preparado: os valores vão em msg.params (evita SQL injection
// e problemas com aspas/ponto decimal).
if (Date.now() - context.get("t0") < 5000) return null;   // aguarda o CREATE TABLE
const t = msg.payload;
msg.params = {
    $temp: t.temp, $umid: t.umid, $sp: t.sp_efetivo, $fonte: t.fonte_sp, $pot: t.pot_raw,
    $aq: t.aquecedor_pwm, $ve: t.ventilador_pwm, $modo: t.modo, $estado: t.estado,
    $estado_txt: t.estado_txt, $alarme: t.alarme, $dht_ok: t.dht_ok
};
return msg;
"""
ins_fn = func(T2, 560, 500, "monta parâmetros", INS_FN, init='context.set("t0", Date.now());')
ins = node("sqlite", T2, 780, 500, mydb=DB["id"], sqlquery="prepared", name="INSERT",
           sql="INSERT INTO camara_dados (temp, umid, sp_efetivo, fonte_sp, pot_raw, aquecedor_pwm, "
               "ventilador_pwm, modo, estado, estado_txt, alarme, dht_ok) VALUES ($temp, $umid, $sp, "
               "$fonte, $pot, $aq, $ve, $modo, $estado, $estado_txt, $alarme, $dht_ok);")
set_wires(m_tel2, [lim["id"]])
set_wires(lim, [ins_fn["id"]])
set_wires(ins_fn, [ins["id"]])

comment(T2, 170, 580, "Histórico no dashboard (a cada 10 s)")
hist_sql = node("sqlite", T2, 520, 640, mydb=DB["id"], sqlquery="fixed", name="últimos 15",
                sql="SELECT strftime('%H:%M:%S', timestamp) AS hora, temp, umid, sp_efetivo AS sp, "
                    "aquecedor_pwm AS aquec, ventilador_pwm AS vent, estado_txt AS estado "
                    "FROM camara_dados ORDER BY id DESC LIMIT 15;")
inject(T2, 160, 640, "a cada 10 s", "", "date", "", once=True, delay="3", repeat="10",
       wires=[[hist_sql["id"]]])
tbl = node("ui-table", T2, 760, 640, name="Histórico", group=G_HIST, label="Últimas 15 amostras",
           order=1, width=8, height=6, maxrows=15, passthru=False, autocols=True, showSearch=False,
           deselect=True, selectionType="none", columns=[], mobileBreakpoint="sm",
           mobileBreakpointType="defaults", action="replace", className="")
set_wires(hist_sql, [tbl["id"]])

# ======================================================== ABA 3: Controle externo
T3 = node("tab", label="Câmara - Controle Node-RED", disabled=False,
          info="Exemplo de estratégia de controle implementada FORA do ESP32.\n"
               "Coloca o ESP32 em modo MANUAL (0) e envia aquecedor_cmd / ventilador_cmd.")["id"]
comment(T3, 230, 40, "Estratégia de controle no Node-RED (edite à vontade!)",
        "1. Ative o switch 'Controle Node-RED ativo' no dashboard.\n"
        "2. O fluxo envia {modo: 0} (MANUAL) ao ESP32.\n"
        f"3. A cada telemetria (2 s) a função calcula os PWMs e publica em {BASE}/cmd.\n\n"
        "Sugestões de atividade: trocar por controle P, PI com anti-windup, PID, fuzzy...\n"
        "Compare com os controladores internos do ESP32 (modos 1 e 2) usando o SQLite.")

CTRL = r"""// ===== Controlador externo (roda no Node-RED, não no ESP32) =====
// Entrada: telemetria do ESP32. Saída: comando JSON para <grupo>/camara/cmd
// Estratégia exemplo: ON/OFF com histerese no aquecedor
//                     + ventilador proporcional ao excesso de temperatura.
if (!flow.get("ativo")) return null;
const t = msg.payload;
if (t.modo !== 0) {                         // garante modo MANUAL no ESP32
    return { payload: { modo: 0 } };
}
if (!t.dht_ok || t.alarme) return null;     // proteções do ESP32 assumem

const H = 0.5;                              // histerese (°C)  <-- ajuste aqui
const sp = t.sp_efetivo, T = t.temp;
let aquecendo = context.get("aquecendo") || false;
if (T < sp - H) aquecendo = true;
if (T > sp + H) aquecendo = false;
context.set("aquecendo", aquecendo);

const aq = aquecendo ? 100 : 0;
const ve = Math.min(100, Math.max(20, 20 + 40 * (T - sp - 1)));   // 20 % mínimo (circulação)

// só publica quando algo mudou
const cmd = { aquecedor_cmd: aq, ventilador_cmd: Math.round(ve) };
if (cmd.aquecedor_cmd === t.aquecedor_cmd && cmd.ventilador_cmd === t.ventilador_cmd) return null;
node.status({ fill: aquecendo ? "red" : "blue", shape: "dot",
              text: `T=${T} SP=${sp} AQ=${aq}% VE=${cmd.ventilador_cmd}%` });
return { payload: cmd };
"""
m_tel3 = mqtt_in(T3, 140, 140, f"{BASE}/telemetria", "telemetria", "json")
ctrl = func(T3, 400, 140, "Controlador ON/OFF + ventilador P", CTRL)
mq3 = mqtt_out(T3, 700, 140, "cmd (JSON)", f"{BASE}/cmd")
dbg3 = debug(T3, 680, 200, "comandos enviados")
set_wires(m_tel3, [ctrl["id"]])
set_wires(ctrl, [mq3, dbg3])

ATIVA = r"""flow.set("ativo", msg.payload === true);
node.status({ fill: msg.payload ? "green" : "grey", shape: "ring",
              text: msg.payload ? "controle externo ATIVO" : "inativo" });
// ao ativar, coloca o ESP32 em MANUAL; ao desativar, volta ao PI interno
return { payload: msg.payload ? { modo: 0 } : { modo: 2 } };
"""
sw_ext = switch(G_CTRL, 300, "Controle Node-RED ativo", None, z=T3, x=170, topic="controle_externo")
ativa = func(T3, 420, 300, "ativa / desativa", ATIVA)
set_wires(sw_ext, [ativa["id"]])
set_wires(ativa, [mq3])
est_txt = node("ui-text", T3, 430, 360, name="estratégia", group=G_CTRL, order=nextorder(G_CTRL), width=0,
     height=0, label="Estratégia", format="ON/OFF ±0,5 °C + ventilador P", layout="row-spread",
     style=False, font="Helvetica", fontSize=14, color="#717171", wrapText=True, className="",
     value="payload", valueType="msg")
est_txt["format"] = "{{msg.payload}}"
inject(T3, 170, 360, "descrição", "ON/OFF ±0,5 °C + ventilador P", "str", once=True, delay="2",
       wires=[[est_txt["id"]]])


# ---- alarmes -> ntfy do grupo (variáveis NTFY_* do container do LAB IoT)
comment(T3, 230, 440, "Alarmes -> ntfy do grupo (celular)",
        "Usa NTFY_URL, NTFY_TOPIC e NTFY_TOKEN, já definidas no Node-RED do grupo pelo\n"
        "gen_iot_scada_portal.py. Fora do LAB IoT (sem essas variáveis) o nó só mostra um aviso.")
NTFY_FN = r"""// Avisa no ntfy do grupo quando o alarme da câmara muda (entra ou sai)
const t = msg.payload;
const ant = context.get("alarme");
context.set("alarme", t.alarme);
if (ant === undefined || ant === t.alarme) return null;
if (!env.get("NTFY_URL")) {
    node.status({ fill: "yellow", shape: "ring", text: "sem NTFY_URL (fora do LAB IoT)" });
    return null;
}
const TXT = { 1: "Sobretemperatura (≥ 60 °C)", 2: "Falha do sensor DHT22",
              3: "Sobretemperatura + falha do DHT22" };
const ativo = t.alarme !== 0;
msg.url = env.get("NTFY_URL");
msg.method = "POST";
msg.headers = { "Authorization": "Bearer " + env.get("NTFY_TOKEN"),
                "Content-Type": "application/json" };
msg.payload = {
    topic: env.get("NTFY_TOPIC"),
    title: ativo ? "Câmara em ALARME" : "Câmara: alarme normalizado",
    message: ativo ? `${TXT[t.alarme]} · T=${t.temp} °C · SP=${t.sp_efetivo} °C`
                   : `T=${t.temp} °C · estado ${t.estado_txt}`,
    priority: ativo ? 5 : 3,
    tags: [ativo ? "rotating_light" : "white_check_mark"]
};
node.status({ fill: ativo ? "red" : "green", shape: "dot", text: msg.payload.title });
return msg;
"""
m_tel_ntfy = mqtt_in(T3, 140, 500, f"{BASE}/telemetria", "telemetria", "json")
fn_ntfy = func(T3, 380, 500, "alarme mudou? -> ntfy", NTFY_FN)
http_ntfy = node("http request", T3, 600, 500, name="POST ntfy", method="use", ret="obj",
                 paytoqs="ignore", url="", tls="", persist=False, proxy="", insecureHTTPParser=False,
                 authType="", senderr=False, headers=[])
dbg_ntfy = debug(T3, 790, 500, "resposta ntfy")
set_wires(m_tel_ntfy, [fn_ntfy["id"]])
set_wires(fn_ntfy, [http_ntfy["id"]])
set_wires(http_ntfy, [dbg_ntfy])

# ======================================================== ABA 4: Protocolos industriais
T4 = node("tab", label="Câmara - Modbus / S7 / OPC-UA", disabled=False,
          info=f"Mesma câmara lida pelos protocolos industriais do simulador ({SIM}). "
               f"Cada leitura é republicada em {BASE}/via/<protocolo>.")["id"]
MQ4 = mqtt_out(T4, 1100, 300, "via/<protocolo>")
dbgs = {k: debug(T4, 1110, y, k, status="payload.temp") for k, y in
        [("Modbus TCP", 100), ("Modbus RTU (TCP)", 140),
         ("S7", 400), ("OPC-UA", 620)]}

comment(T4, 260, 40, "Modbus - IR 0..17 (FC4), HR 0..7 comandos (ver simuladores/README.md)")


def mb_client(name, **kw):
    n = {"id": nid(), "type": "modbus-client", "name": name, "clienttype": "tcp",
         "bufferCommands": True, "stateLogEnabled": False, "queueLogEnabled": False,
         "failureLogEnabled": True, "tcpHost": SIM, "tcpPort": "502", "tcpType": "DEFAULT",
         "serialPort": "", "serialType": "RTU-BUFFERD", "serialBaudrate": "9600",
         "serialDatabits": "8", "serialStopbits": "1", "serialParity": "none",
         "serialConnectionDelay": "100", "serialAsciiResponseStartDelimiter": "0x3A",
         "unit_id": "1", "commandDelay": "1", "clientTimeout": "1000",
         "reconnectOnTimeout": True, "reconnectTimeout": "2000", "parallelUnitIdsAllowed": True}
    n.update(kw)
    nodes.append(n)
    return n["id"]


c_tcp = mb_client("Câmara Modbus TCP", tcpPort=P_MTCP)
c_rtu = mb_client("Câmara Modbus RTU (sobre TCP)", tcpPort="5021", tcpType="TELNET")

MB_DEC = r"""// Input registers 0..17 da câmara -> mesmo JSON da telemetria MQTT
const r = msg.payload;
if (!Array.isArray(r) || r.length < 18) return null;
const s16 = v => (v > 0x7FFF ? v - 0x10000 : v);
const f32 = i => { const b = Buffer.alloc(4); b.writeUInt16BE(r[i], 0); b.writeUInt16BE(r[i+1], 2); return b.readFloatBE(0); };
const ESTADOS = ["DESLIGADO", "AQUECENDO", "RESFRIANDO", "ESTAVEL", "ALARME"];
msg.payload = {
    temp: Number(f32(12).toFixed(1)),      // ou s16(r[0]) / 10
    umid: Number(f32(14).toFixed(1)),      // ou r[1] / 10
    sp_efetivo: s16(r[2]) / 10,
    aquecedor_pwm: r[3], ventilador_pwm: r[4], pot_raw: r[5],
    estado: r[6], estado_txt: ESTADOS[r[6]], alarme: r[7],
    led_verde: r[8] & 1, led_amarelo: (r[8] >> 1) & 1, led_vermelho: (r[8] >> 2) & 1,
    dht_erros: r[9], heartbeat: r[10], uptime: r[11],
    aquecedor_duty: r[16], ventilador_duty: r[17]
};
return msg;
"""
mbdec = func(T4, 640, 140, "Decodifica IR 0..17", MB_DEC)
sw = node("switch", T4, 860, 140, name="por protocolo", property="topic", propertyType="msg",
          rules=[{"t": "eq", "v": f"{BASE}/via/modbus_tcp", "vt": "str"},
                 {"t": "eq", "v": f"{BASE}/via/modbus_rtu", "vt": "str"}],
          checkall="true", repair=False, outputs=2,
          wires=[[dbgs["Modbus TCP"]], [dbgs["Modbus RTU (TCP)"]]])
set_wires(mbdec, [MQ4, sw["id"]])


def mb_read(y, name, srv, topic):
    node("modbus-read", T4, 380, y, name=name, topic=topic, showStatusActivities=False,
         logIOActivities=False, showErrors=True, showWarnings=True, unitid="1",
         dataType="InputRegister", adr="0", quantity="18", rate="2", rateUnit="s",
         delayOnStart=True, startDelayTime="3", server=srv, useIOFile=False, ioFile="",
         useIOForPayload=False, emptyMsgOnFail=False, keepMsgProperties=False,
         wires=[[mbdec["id"]], []])


mb_read(100, "FC4 IR 0..17 (TCP)", c_tcp, f"{BASE}/via/modbus_tcp")
mb_read(140, "FC4 IR 0..17 (RTU/TCP)", c_rtu, f"{BASE}/via/modbus_rtu")

SP_X10 = 'msg.payload = Math.round(Number(msg.payload) * 10);   // HR3 = °C x 10\nreturn msg;'
mbw = node("modbus-write", T4, 620, 240, name="FC6 HR3 setpoint (TCP)", showStatusActivities=True,
           showErrors=True, showWarnings=True, unitid="1", dataType="HoldingRegister", adr="3",
           quantity="1", server=c_tcp, emptyMsgOnFail=False, keepMsgProperties=False,
           wires=[[], []])
x10 = func(T4, 400, 240, "°C x 10", SP_X10)
set_wires(x10, [mbw["id"]])
inject(T4, 150, 220, "SP 30 °C", "30", "num", wires=[[x10["id"]]])
inject(T4, 150, 260, "SP 45 °C", "45", "num", wires=[[x10["id"]]])
mbm = node("modbus-write", T4, 620, 300, name="FC6 HR1 modo (TCP)", showStatusActivities=True,
           showErrors=True, showWarnings=True, unitid="1", dataType="HoldingRegister", adr="1",
           quantity="1", server=c_tcp, emptyMsgOnFail=False, keepMsgProperties=False,
           wires=[[], []])
inject(T4, 150, 300, "Modo ON/OFF (1)", "1", "num", wires=[[mbm["id"]]])
inject(T4, 150, 340, "Modo PI (2)", "2", "num", wires=[[mbm["id"]]])

# ---- S7
comment(T4, 220, 380, "Siemens S7 - DB1 (comandos 0..17, estado 20..55)")
VARS_S7 = [("habilitado", "DB1,X0.0"), ("fonte_sp", "DB1,X0.1"), ("modo", "DB1,INT2"),
           ("setpoint", "DB1,REAL4"), ("temp", "DB1,REAL20"), ("umid", "DB1,REAL24"),
           ("sp_efetivo", "DB1,REAL28"), ("aquecedor_pwm", "DB1,REAL32"),
           ("ventilador_pwm", "DB1,REAL36"), ("estado", "DB1,INT40"), ("alarme", "DB1,INT42"),
           ("led_verde", "DB1,X44.0"), ("led_amarelo", "DB1,X44.1"), ("led_vermelho", "DB1,X44.2"),
           ("dht_ok", "DB1,X44.3"), ("pot_raw", "DB1,INT46"), ("heartbeat", "DB1,DINT48")]
s7ep = node("s7 endpoint", transport="iso-on-tcp", address=SIM, port=P_S7, rack="0", slot="1",
            localtsaphi="01", localtsaplo="00", remotetsaphi="01", remotetsaplo="00",
            connmode="rack-slot", adapter="", busaddr="2", cycletime="2000", timeout="2000",
            name="Câmara S7 (DB1)", vartable=[{"addr": a, "name": n} for n, a in VARS_S7])
S7_FMT = r"""// "s7 in" (todas as variáveis) -> JSON no mesmo formato da telemetria
const p = msg.payload, r1 = v => Math.round(v * 10) / 10;
const ESTADOS = ["DESLIGADO", "AQUECENDO", "RESFRIANDO", "ESTAVEL", "ALARME"];
msg.payload = {
    temp: r1(p.temp), umid: r1(p.umid), sp_efetivo: r1(p.sp_efetivo), setpoint: r1(p.setpoint),
    aquecedor_pwm: r1(p.aquecedor_pwm), ventilador_pwm: r1(p.ventilador_pwm),
    modo: p.modo, habilitado: +p.habilitado, fonte_sp: +p.fonte_sp, pot_raw: p.pot_raw,
    estado: p.estado, estado_txt: ESTADOS[p.estado], alarme: p.alarme,
    led_verde: +p.led_verde, led_amarelo: +p.led_amarelo, led_vermelho: +p.led_vermelho,
    dht_ok: +p.dht_ok, heartbeat: p.heartbeat
};
msg.topic = "__VIA__/s7";
return msg;
"""
s7f = func(T4, 640, 420, "Formata S7", S7_FMT.replace("__VIA__", f"{BASE}/via"))
set_wires(s7f, [MQ4, dbgs["S7"]])
node("s7 in", T4, 380, 420, endpoint=s7ep["id"], mode="all", variable="", diff=False,
     name="Lê DB1 (todas)", wires=[[s7f["id"]]])
s7sp = node("s7 out", T4, 400, 480, endpoint=s7ep["id"], variable="setpoint", name="DB1,REAL4 setpoint")
inject(T4, 150, 460, "SP 32 °C", "32", "num", wires=[[s7sp["id"]]])
inject(T4, 150, 500, "SP 40 °C", "40", "num", wires=[[s7sp["id"]]])
s7hab = node("s7 out", T4, 400, 540, endpoint=s7ep["id"], variable="habilitado", name="DB1,X0.0 habilitado")
inject(T4, 150, 540, "Liga", "true", "bool", wires=[[s7hab["id"]]])
inject(T4, 150, 580, "Desliga", "false", "bool", wires=[[s7hab["id"]]])

# ---- OPC-UA
comment(T4, 230, 620, f"OPC-UA - opc.tcp://{SIM}:4840/  ns=2;s=Camara.*")
opcep = node("OpcUa-Endpoint", name="Câmara OPC-UA", endpoint=f"opc.tcp://{SIM}:4840/",
             secpol="None", secmode="None", none=True, login=False, usercert=False,
             usercertificate="", userprivatekey="")


def opc_client(x, y, name, action, wires):
    return node("OpcUa-Client", T4, x, y, endpoint=opcep["id"], action=action, deadbandtype="a",
                deadbandvalue=1, time=2, timeUnit="s", certificate="n", localfile="",
                localkeyfile="", securitymode="None", securitypolicy="None", useTransport=False,
                maxChunkCount=1, maxMessageSize=8192, receiveBufferSize=8192, sendBufferSize=8192,
                setstatusandtime=False, keepsessionalive=True, name=name, applicationName="",
                applicationUri="", wires=wires)["id"]


OPC_ITEMS = r"""// Uma mensagem por variável a assinar (msg.topic = NodeId)
const ns = 2;   // índice de "urn:utfpr:camara-climatica" (ver log do simulador)
const vars = {
    temp: "Double", umid: "Double", sp_efetivo: "Double", setpoint: "Double",
    aquecedor_pwm: "Double", ventilador_pwm: "Double", pot_raw: "Int32", modo: "Int32",
    estado: "Int32", estado_txt: "String", alarme: "Int32", dht_ok: "Boolean", heartbeat: "Int32"
};
return [Object.entries(vars).map(([n, type]) => ({ topic: `ns=${ns};s=Camara.${n}`, datatype: type, payload: "" }))];
"""
OPC_JOIN = r"""// Junta as notificações da assinatura em um único objeto
const nome = String(msg.topic).split("Camara.")[1];
if (!nome) return null;
const v = (msg.payload && msg.payload.value !== undefined) ? msg.payload.value.value : msg.payload;
const d = context.get("d") || {};
d[nome] = typeof v === "boolean" ? +v : v;
context.set("d", d);
if (nome !== "heartbeat" || Object.keys(d).length < 13) return null;
const r1 = x => Math.round(x * 10) / 10;
return { topic: "__VIA__/opcua",
         payload: Object.assign({}, d, { temp: r1(d.temp), umid: r1(d.umid),
                                         aquecedor_pwm: r1(d.aquecedor_pwm), ventilador_pwm: r1(d.ventilador_pwm) }) };
"""
join = func(T4, 860, 680, "Agrupa variáveis", OPC_JOIN.replace("__VIA__", f"{BASE}/via"))
set_wires(join, [MQ4, dbgs["OPC-UA"]])
sub = opc_client(640, 680, "Assina (2 s)", "subscribe", [[join["id"]], []])
items = func(T4, 400, 680, "Lista de NodeIds", OPC_ITEMS)
set_wires(items, [sub])
inject(T4, 160, 680, "Iniciar assinatura", "", "date", once=True, delay="5", wires=[[items["id"]]])
wr = opc_client(640, 760, "Escreve", "write", [[], []])
it = node("OpcUa-Item", T4, 400, 760, item="ns=2;s=Camara.setpoint", datatype="Double", value="",
          name="Camara.setpoint", wires=[[wr]])
inject(T4, 150, 740, "SP 33 °C", "33", "num", wires=[[it["id"]]])
inject(T4, 150, 780, "SP 42 °C", "42", "num", wires=[[it["id"]]])

os.makedirs(os.path.dirname(SAIDA) or ".", exist_ok=True)
with open(SAIDA, "w", encoding="utf-8", newline="\n") as f:
    json.dump(nodes, f, indent=4, ensure_ascii=False)
print(f"✅ {SAIDA}: {len(nodes)} nós · tópicos {BASE}/# · simulador {SIM}")
