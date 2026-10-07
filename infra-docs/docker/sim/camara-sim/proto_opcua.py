"""
Adaptador OPC-UA (asyncua) da câmara.

Endpoint: opc.tcp://<host>:4840/   segurança None, acesso anônimo (laboratório!)
Escuta em todas as interfaces; o endereço devolvido no GetEndpoints é o mesmo que o
cliente usou (localhost, IP do PC ou <grupo>-camara na rede Docker), então UaExpert,
Node-RED e FUXA conectam sem configurar nome de host.
Namespace URI "urn:utfpr:camara-climatica" (índice 2). NodeIds: ns=2;s=Camara.<nome>

  Objects/Camara/
    Medicoes/   temp (Double), umid (Double), pot_raw (Int32), sp_efetivo (Double)
    Atuadores/  aquecedor_pwm, ventilador_pwm (Double %), aquecedor_duty, ventilador_duty (Int32)
    Estado/     estado (Int32), estado_txt (String), alarme (Int32), led_verde,
                led_amarelo, led_vermelho, dht_ok (Boolean), dht_erros, heartbeat, uptime (Int32),
                oled (String, linhas separadas por \\n)
    Comandos/   habilitado (Boolean), modo (Int32), fonte_sp (Int32), setpoint (Double),
                aquecedor_cmd (Double), ventilador_cmd (Double)              [GRAVÁVEIS]
    Simulacao/  pot_raw_sim (Int32), falha_dht (Boolean)                      [GRAVÁVEIS]
"""

import socket

from asyncua import Server, ua
from asyncua.common.callback import CallbackType

NS_URI = "urn:utfpr:camara-climatica"
D, I, B, S = ua.VariantType.Double, ua.VariantType.Int32, ua.VariantType.Boolean, ua.VariantType.String

PASTAS = {
    "Medicoes": [("temp", D), ("umid", D), ("pot_raw", I), ("sp_efetivo", D)],
    "Atuadores": [("aquecedor_pwm", D), ("ventilador_pwm", D), ("aquecedor_duty", I),
                  ("ventilador_duty", I)],
    "Estado": [("estado", I), ("estado_txt", S), ("alarme", I), ("led_verde", B),
               ("led_amarelo", B), ("led_vermelho", B), ("dht_ok", B), ("dht_erros", I),
               ("heartbeat", I), ("uptime", I), ("oled", S)],
    "Comandos": [("habilitado", B), ("modo", I), ("fonte_sp", I), ("setpoint", D),
                 ("aquecedor_cmd", D), ("ventilador_cmd", D)],
    "Simulacao": [("pot_raw_sim", I), ("falha_dht", B)],
}
GRAVAVEIS = {"Comandos", "Simulacao"}


def _conv(vtype, v):
    if vtype == D:
        return float(v)
    if vtype == I:
        return int(v)
    if vtype == B:
        return bool(v)
    return "\n".join(v) if isinstance(v, list) else str(v)


class OpcUaAdapter:
    def __init__(self, camara, log):
        self.cam, self.log = camara, log
        self.server = None
        self.nodes = {}      # nome -> (node, vtype)
        self.by_id = {}      # NodeId -> nome

    async def start(self, bind="0.0.0.0", port=4840):
        self.server = Server()
        await self.server.init()
        self.server.set_endpoint(f"opc.tcp://{socket.gethostname()}:{port}/")
        self.server.socket_address = (bind, port)   # escuta aqui; anuncia o endereço do cliente
        self.server.set_server_name("UTFPR Camara Climatica ESP32 (simulador)")
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        idx = await self.server.register_namespace(NS_URI)
        cam = await self.server.nodes.objects.add_object(ua.NodeId("Camara", idx), f"{idx}:Camara")
        s = self.cam.snapshot()
        s["pot_raw_sim"] = self.cam.cmd["pot_raw"]
        for pasta, vars_ in PASTAS.items():
            obj = await cam.add_object(ua.NodeId(f"Camara.{pasta}", idx), f"{idx}:{pasta}")
            for nome, vt in vars_:
                nid = ua.NodeId(f"Camara.{nome}", idx)
                node = await obj.add_variable(nid, f"{idx}:{nome}", ua.Variant(_conv(vt, s[nome]), vt))
                if pasta in GRAVAVEIS:
                    await node.set_writable()
                self.nodes[nome] = (node, vt)
                self.by_id[nid] = nome
        self.server.subscribe_server_callback(CallbackType.PostWrite, self._on_write)
        await self.server.start()
        self.log(f"[opcua] opc.tcp://<host>:{port}/  (escutando em {bind})  '{NS_URI}' = ns={idx}")

    async def _on_write(self, event, _dispatcher):
        if not event.is_external:          # escritas do próprio simulador
            return
        for wv, status in zip(event.request_params.NodesToWrite, event.response_params):
            nome = self.by_id.get(wv.NodeId)
            if nome and status.is_good():
                cmd = "pot_raw" if nome == "pot_raw_sim" else nome
                self.cam.aplicar(cmd, wv.Value.Value.Value, "opcua")

    async def sync(self, s):
        s = dict(s, pot_raw_sim=self.cam.cmd["pot_raw"])
        for nome, (node, vt) in self.nodes.items():
            await node.write_value(ua.Variant(_conv(vt, s[nome]), vt))

    async def stop(self):
        if self.server:
            await self.server.stop()
