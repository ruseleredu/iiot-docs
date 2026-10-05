import asyncio
import logging
import math
import struct
import sys
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

state = {"level": 65.0, "temperature": 27.0, "pressure": 2.1, "speed": 72.0, "running": True}


def process_loop():
    start = time.monotonic()
    while True:
        t = time.monotonic() - start
        state["level"] = 65 + 20 * math.sin(t / 60 * 2 * math.pi)
        state["temperature"] = 27 + 3 * math.sin(t / 45 * 2 * math.pi)
        state["pressure"] = 2 + .2 * math.sin(t / 30 * 2 * math.pi)
        state["speed"] = (70 + 10 * math.sin(t / 20 * 2 * math.pi)) if state["running"] else 0
        time.sleep(1)


def run_modbus():
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext
    from pymodbus.server import StartTcpServer

    hr = ModbusSequentialDataBlock(0, [0] * 20)
    co = ModbusSequentialDataBlock(0, [0] * 20)
    ctx = ModbusServerContext(devices=ModbusDeviceContext(hr=hr, co=co), single=True)

    def update():
        while True:
            hr.setValues(0, [
                int(state["level"] * 10), int(state["temperature"] * 10),
                int(state["pressure"] * 10), int(state["speed"] * 10)])
            co.setValues(0, [int(state["running"]), int(state["running"])])
            time.sleep(1)

    threading.Thread(target=update, daemon=True).start()
    logging.info("Modbus TCP: 0.0.0.0:502")
    StartTcpServer(context=ctx, address=("0.0.0.0", 502))


async def run_opcua_async():
    from asyncua import Server
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    idx = await server.register_namespace("urn:scada-lab")
    plant = await server.nodes.objects.add_object(idx, "Plant")
    tank = await plant.add_object(idx, "Tank")
    pump = await plant.add_object(idx, "Pump")
    level = await tank.add_variable(idx, "Level", 65.0)
    temperature = await tank.add_variable(idx, "Temperature", 27.0)
    pressure = await tank.add_variable(idx, "Pressure", 2.1)
    running = await pump.add_variable(idx, "Running", True)
    speed = await pump.add_variable(idx, "Speed", 72.0)
    for node in (level, temperature, pressure, running, speed):
        await node.set_writable()
    logging.info("OPC-UA: opc.tcp://0.0.0.0:4840/freeopcua/server/")
    async with server:
        while True:
            await level.write_value(float(state["level"]))
            await temperature.write_value(float(state["temperature"]))
            await pressure.write_value(float(state["pressure"]))
            await running.write_value(bool(state["running"]))
            await speed.write_value(float(state["speed"]))
            await asyncio.sleep(1)


def run_opcua():
    asyncio.run(run_opcua_async())


def run_s7():
    # Minimal S7 test server. Host port is mapped to 1102 by default because
    # TCP/102 can require elevated privileges on Linux. FUXA can target 1102.
    import snap7
    from snap7.server import Server, SrvArea

    db = bytearray(32)
    server = Server()
    server.register_area(SrvArea.DB, 1, db)

    def update():
        while True:
            db[0:4] = struct.pack(">f", state["level"])
            db[4:8] = struct.pack(">f", state["temperature"])
            db[8:12] = struct.pack(">f", state["pressure"])
            db[12:16] = struct.pack(">f", state["speed"])
            db[16] = 0x03 if state["running"] else 0x00
            time.sleep(1)

    threading.Thread(target=update, daemon=True).start()
    logging.info("S7 simulator: 0.0.0.0:1102")
    server.start(tcp_port=1102)
    try:
        while True:
            time.sleep(3600)
    finally:
        server.stop()


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"modbus", "opcua", "s7"}:
        raise SystemExit("Usage: server.py modbus|opcua|s7")
    threading.Thread(target=process_loop, daemon=True).start()
    {"modbus": run_modbus, "opcua": run_opcua, "s7": run_s7}[sys.argv[1]]()


if __name__ == "__main__":
    main()
