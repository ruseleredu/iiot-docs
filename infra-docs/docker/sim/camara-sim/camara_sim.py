"""
Simulador da Câmara Climática com ESP32 (DHT22, OLED, potenciômetro, PWM).

Uma única planta é exposta ao mesmo tempo por MQTT (paho-mqtt), Modbus TCP,
Modbus RTU sobre TCP, Siemens S7 e OPC-UA. Um comando enviado por qualquer
protocolo (ex.: setpoint via OPC-UA) aparece em todos os outros.

Compatível com o LAB IoT (gen_iot_scada_portal.py): tópicos MQTT sob <grupo>/...
(ex.: lab05-a/camara/telemetria), broker "mosquitto" e nome de host <grupo>-camara.

Exemplos:
  py camara_sim.py --grupo lab05-a                           # broker em localhost:1883
  py camara_sim.py --grupo lab05-a --mqtt-host 192.168.0.10  # broker do laboratório
  py camara_sim.py --sem-mqtt --modbus-tcp-port 5020 --s7-port 1102   # sem broker, sem admin
  py camara_sim.py --speed 10                                # dinâmica 10x mais rápida

Cada opção também pode vir de variável de ambiente (é assim que o Docker configura):
  GRUPO, MQTT_HOST, MQTT_PORT, MQTT_BASE, MQTT_USER, MQTT_PASS, SIM_SPEED,
  MODBUS_TCP_PORT, MODBUS_RTU_PORT, S7_PORT, OPCUA_PORT
"""

import argparse
import asyncio
import os
import signal
import time

from camara_model import Camara


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def args():
    e = os.environ.get
    p = argparse.ArgumentParser(description="Simulador Câmara Climática ESP32")
    p.add_argument("--grupo", default=e("GRUPO", ""),
                   help="grupo do laboratório (ex.: lab05-a); define o tópico base <grupo>/camara")
    p.add_argument("--speed", type=float, default=float(e("SIM_SPEED", "1")),
                   help="fator de aceleração da dinâmica (1 = tempo real)")
    p.add_argument("--host", default="0.0.0.0", help="interface dos servidores")
    # MQTT
    p.add_argument("--mqtt-host", default=e("MQTT_HOST", "localhost"))
    p.add_argument("--mqtt-port", type=int, default=int(e("MQTT_PORT", "1883")))
    p.add_argument("--mqtt-base", default=e("MQTT_BASE", ""),
                   help="tópico base (padrão: <grupo>/camara, ou camara sem grupo)")
    p.add_argument("--mqtt-user", default=e("MQTT_USER"))
    p.add_argument("--mqtt-pass", default=e("MQTT_PASS"))
    p.add_argument("--mqtt-period", type=float, default=2.0)
    p.add_argument("--mqtt-v311", action="store_true", help="usar MQTT 3.1.1 em vez de 5")
    p.add_argument("--sem-mqtt", action="store_true")
    # Modbus / S7 / OPC-UA  (porta 0 = desliga)
    p.add_argument("--modbus-tcp-port", type=int, default=int(e("MODBUS_TCP_PORT", "502")))
    p.add_argument("--modbus-rtu-port", type=int, default=int(e("MODBUS_RTU_PORT", "5021")),
                   help="Modbus RTU sobre TCP (0 desliga)")
    p.add_argument("--s7-port", type=int, default=int(e("S7_PORT", "102")))
    p.add_argument("--opcua-port", type=int, default=int(e("OPCUA_PORT", "4840")))
    a = p.parse_args()
    if not a.mqtt_base:
        a.mqtt_base = f"{a.grupo}/camara" if a.grupo else "camara"
    return a


async def main():
    a = args()
    cam = Camara(speed=a.speed, log=log)
    log(f"[planta] câmara climática simulada{' do ' + a.grupo if a.grupo else ''}, speed={a.speed}x")

    modbus = s7 = opcua = mq = None
    tasks = []
    if a.modbus_tcp_port or a.modbus_rtu_port:
        from proto_modbus import ModbusAdapter
        modbus = ModbusAdapter(cam, log)
        tasks.append(asyncio.create_task(modbus.start(a.host, a.modbus_tcp_port, a.modbus_rtu_port)))
    if a.s7_port:
        from proto_s7 import S7Adapter
        s7 = S7Adapter(cam, log)
        s7.start(a.s7_port)
    if a.opcua_port:
        from proto_opcua import OpcUaAdapter
        opcua = OpcUaAdapter(cam, log)
        await opcua.start(a.host, a.opcua_port)
    if not a.sem_mqtt:
        from proto_mqtt import MqttAdapter
        mq = MqttAdapter(cam, log, a.mqtt_host, a.mqtt_port, a.mqtt_base,
                         a.mqtt_user, a.mqtt_pass, v5=not a.mqtt_v311)
        mq.start()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:      # Windows: Ctrl+C vira KeyboardInterrupt
            pass

    DT = 0.1
    n = 0
    t_mqtt = 0.0
    last = time.monotonic()
    try:
        while not stop.is_set():
            now = time.monotonic()
            cam.step(now - last)
            last = now
            n += 1
            if n % 5 == 0:                       # sincroniza protocolos a cada 0,5 s
                s = cam.snapshot()
                if modbus:
                    modbus.sync(s)
                if s7:
                    s7.sync(s)
                if opcua:
                    await opcua.sync(s)
            t_mqtt += DT
            if mq and t_mqtt >= a.mqtt_period:
                t_mqtt = 0.0
                mq.publish(cam.snapshot())
            for t in tasks:
                if t.done() and t.exception():
                    raise t.exception()
            try:
                await asyncio.wait_for(stop.wait(), DT)
            except asyncio.TimeoutError:
                pass
    finally:
        log("[planta] encerrando")
        if mq:
            mq.stop()
        if s7:
            s7.stop()
        if opcua:
            await opcua.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
