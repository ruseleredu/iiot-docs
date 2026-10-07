"""
Teste de ponta a ponta do simulador da câmara em todos os protocolos.

Cada protocolo ESCREVE um setpoint diferente e os outros LEEM o valor,
mostrando que todos enxergam a mesma planta.

    py testar_clientes.py --grupo lab05-a                # simulador e broker neste PC
    py testar_clientes.py --grupo lab05-a --sem-mqtt     # sem broker
    py testar_clientes.py --host 192.168.0.20 --porta-s7 1102
"""

import argparse
import asyncio
import json
import struct
import threading
import time

import paho.mqtt.client as mqtt
import snap7
from asyncua import Client, ua
from pymodbus import FramerType
from pymodbus.client import AsyncModbusTcpClient

NS = "urn:utfpr:camara-climatica"


def f32(hi, lo):
    return struct.unpack(">f", struct.pack(">HH", hi, lo))[0]


async def modbus_ler(host, port, framer):
    c = AsyncModbusTcpClient(host, port=port, framer=framer, timeout=3)
    await c.connect()
    ir = (await c.read_input_registers(0, count=18, slave=1)).registers
    hr = (await c.read_holding_registers(0, count=8, slave=1)).registers
    di = (await c.read_discrete_inputs(0, count=5, slave=1)).bits[:5]
    c.close()
    return {"temp": round(f32(ir[12], ir[13]), 1), "umid": ir[1] / 10, "sp": hr[3] / 10, "sp_ef": ir[2] / 10,
            "aq": ir[3], "ve": ir[4], "estado": ir[6], "leds(v,a,r)": [int(b) for b in di[:3]]}


async def modbus_setpoint(host, port, framer, sp):
    c = AsyncModbusTcpClient(host, port=port, framer=framer, timeout=3)
    await c.connect()
    await c.write_register(3, int(sp * 10), slave=1)
    c.close()


def s7_ler(host, port):
    c = snap7.client.Client()
    c.connect(host, 0, 1, port)
    d = c.db_read(1, 0, 56)
    c.disconnect()
    temp, umid, sp_ef, aq, ve = struct.unpack_from(">fffff", d, 20)
    estado, = struct.unpack_from(">h", d, 40)
    return {"temp": round(temp, 1), "umid": round(umid, 1), "sp": round(struct.unpack_from(">f", d, 4)[0], 1),
            "sp_ef": sp_ef, "aq": aq, "ve": ve, "estado": estado}


def s7_setpoint(host, port, sp):
    c = snap7.client.Client()
    c.connect(host, 0, 1, port)
    c.db_write(1, 4, bytearray(struct.pack(">f", sp)))
    c.disconnect()


async def opcua_ler_escrever(host, port, sp=None):
    async with Client(f"opc.tcp://{host}:{port}/") as c:
        idx = await c.get_namespace_index(NS)
        n = lambda k: c.get_node(f"ns={idx};s=Camara.{k}")  # noqa: E731
        if sp is not None:
            await n("setpoint").write_value(ua.DataValue(ua.Variant(float(sp), ua.VariantType.Double)))
            return None
        r = {k: await n(k).read_value() for k in ("temp", "umid", "setpoint", "sp_efetivo",
                                                   "aquecedor_pwm", "ventilador_pwm", "estado_txt")}
        r["oled"] = (await n("oled").read_value()).split("\n")
        return r


def mqtt_ciclo(host, port, base, sp):
    recebido = {}
    ev = threading.Event()

    def on_msg(_c, _u, m):
        if m.topic.endswith("/telemetria"):
            recebido.update(json.loads(m.payload))
            ev.set()

    c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
    c.on_message = on_msg
    c.connect(host, port)
    c.subscribe(f"{base}/telemetria")
    c.loop_start()
    c.publish(f"{base}/cmd", json.dumps({"setpoint": sp}), qos=1).wait_for_publish(3)
    ev.wait(5)
    c.loop_stop()
    c.disconnect()
    return {k: recebido.get(k) for k in ("temp", "umid", "setpoint", "estado_txt", "aquecedor_pwm")}


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--grupo", default="", help="ex.: lab05-a (tópicos <grupo>/camara)")
    p.add_argument("--mqtt-host", default=None, help="padrão: o mesmo de --host")
    p.add_argument("--mqtt-port", type=int, default=1883)
    p.add_argument("--sem-mqtt", action="store_true")
    p.add_argument("--porta-modbus-tcp", type=int, default=502)
    p.add_argument("--porta-modbus-rtu", type=int, default=5021)
    p.add_argument("--porta-s7", type=int, default=102)
    p.add_argument("--porta-opcua", type=int, default=4840)
    a = p.parse_args()
    h = a.host
    a.mqtt_base = f"{a.grupo}/camara" if a.grupo else "camara"
    mh = a.mqtt_host or h
    a.modbus_tcp_port, a.modbus_rtu_port = a.porta_modbus_tcp, a.porta_modbus_rtu
    a.s7_port, a.opcua_port = a.porta_s7, a.porta_opcua

    passos = [
        ("MQTT escreve SP=36.0", lambda: asyncio.to_thread(mqtt_ciclo, mh, a.mqtt_port, a.mqtt_base, 36.0)),
        ("Modbus TCP lê", lambda: modbus_ler(h, a.modbus_tcp_port, FramerType.SOCKET)),
        ("Modbus TCP escreve SP=37.5", lambda: modbus_setpoint(h, a.modbus_tcp_port, FramerType.SOCKET, 37.5)),
        ("S7 lê", lambda: asyncio.to_thread(s7_ler, h, a.s7_port)),
        ("S7 escreve SP=38.0", lambda: asyncio.to_thread(s7_setpoint, h, a.s7_port, 38.0)),
        ("OPC-UA lê", lambda: opcua_ler_escrever(h, a.opcua_port)),
        ("OPC-UA escreve SP=39.0", lambda: opcua_ler_escrever(h, a.opcua_port, 39.0)),
        ("Modbus RTU/TCP lê", lambda: modbus_ler(h, a.modbus_rtu_port, FramerType.RTU)),
        ("MQTT escreve SP=35.0 e lê", lambda: asyncio.to_thread(mqtt_ciclo, mh, a.mqtt_port, a.mqtt_base, 35.0)),
    ]
    if a.sem_mqtt:
        passos = [p_ for p_ in passos if not p_[0].startswith("MQTT")]
    for nome, fn in passos:
        try:
            r = await fn()
            print(f"{nome:28s} {r if r is not None else 'ok'}")
        except Exception as e:  # noqa: BLE001
            print(f"{nome:28s} FALHOU: {e!r}")
        await asyncio.sleep(1.2)   # deixa o simulador sincronizar (0,5 s)


if __name__ == "__main__":
    asyncio.run(main())
