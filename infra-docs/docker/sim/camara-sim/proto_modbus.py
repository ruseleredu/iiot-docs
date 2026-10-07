"""
Adaptador Modbus da câmara (escravo/servidor, unit id 1, endereços base 0).

Um único banco de dados Modbus é servido em 2 portas TCP (sem porta serial):
  - Modbus TCP (cabeçalho MBAP) ............. --modbus-tcp-port   (padrão 502)
  - Modbus RTU sobre TCP (quadro RTU + CRC) . --modbus-rtu-port   (padrão 5021, 0 desliga)
    É o que um gateway serial-Ethernet "transparente" entrega: o mesmo quadro do RS-485,
    só que num socket TCP. No node-red-contrib-modbus use o tipo TCP "TELNET".

COILS (FC1 lê, FC5/FC15 escreve)
  0  habilitado          1 = câmara ligada
  1  falha_dht           SIMULAÇÃO: 1 = injeta falha no DHT22

DISCRETE INPUTS (FC2, somente leitura)
  0  led_verde   1 led_amarelo   2 led_vermelho   3 dht_ok   4 alarme ativo

HOLDING REGISTERS (FC3 lê, FC6/FC16 escreve) - comandos
  0  habilitado          0/1
  1  modo                0 MANUAL, 1 ON/OFF, 2 PI
  2  fonte_sp            0 remoto (HR3), 1 potenciômetro
  3  setpoint x10        °C x 10   (350 = 35,0 °C; faixa 200..550)
  4  aquecedor_cmd       %  (usado no modo MANUAL)
  5  ventilador_cmd      %  (usado no modo MANUAL)
  6  pot_raw             SIMULAÇÃO: posição do potenciômetro 0..4095
  7  falha_dht           SIMULAÇÃO: 0/1

INPUT REGISTERS (FC4, somente leitura) - medições e estado
  0  temp x10            int16, °C x 10
  1  umid x10            %UR x 10
  2  sp_efetivo x10      °C x 10 (remoto ou potenciômetro)
  3  aquecedor_pwm       % aplicado
  4  ventilador_pwm      % aplicado
  5  pot_raw             leitura do ADC 0..4095
  6  estado              0 DESLIGADO 1 AQUECENDO 2 RESFRIANDO 3 ESTAVEL 4 ALARME
  7  alarme              bit0 sobretemperatura, bit1 falha do sensor
  8  leds                bit0 verde, bit1 amarelo, bit2 vermelho
  9  dht_erros           contador de leituras com erro
  10 heartbeat           contador (1 Hz)
  11 uptime              s (módulo 65536)
  12-13 temp             float32 big-endian (ABCD)
  14-15 umid             float32 ABCD
  16 aquecedor_duty      0..255 (LEDC 8 bits)
  17 ventilador_duty     0..255
"""

import asyncio
import struct

from pymodbus import FramerType
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import ModbusTcpServer

FC_CO, FC_DI, FC_HR, FC_IR = 1, 2, 3, 4
UNIT = 1


def _f32(v):
    return list(struct.unpack(">HH", struct.pack(">f", float(v))))


def _i16(v):
    return int(round(v)) & 0xFFFF


class ModbusAdapter:
    def __init__(self, camara, log):
        self.cam, self.log = camara, log
        self.dev = ModbusSlaveContext(
            co=ModbusSequentialDataBlock(0, [False] * 16),
            di=ModbusSequentialDataBlock(0, [False] * 16),
            hr=ModbusSequentialDataBlock(0, [0] * 32),
            ir=ModbusSequentialDataBlock(0, [0] * 32),
        )
        self.context = ModbusServerContext(slaves={UNIT: self.dev}, single=False)
        self.identity = ModbusDeviceIdentification(info_name={
            "VendorName": "UTFPR", "ProductCode": "CAMARA-ESP32",
            "ProductName": "Camara Climatica ESP32 (simulador)", "MajorMinorRevision": "2.0"})
        self._hr = self._co = None
        self.servers = []

    # comandos <-> holding registers
    @staticmethod
    def _cmd_to_hr(s):
        return [s["habilitado"], s["modo"], s["fonte_sp"], _i16(s["setpoint"] * 10),
                _i16(s["aquecedor_cmd"]), _i16(s["ventilador_cmd"]), s["pot_raw_cmd"], s["falha_dht"]]

    def sync(self, s):
        """Chamado periodicamente (sem await no meio: atômico no asyncio)."""
        hr = list(self.dev.getValues(FC_HR, 0, 8))
        co = [int(b) for b in self.dev.getValues(FC_CO, 0, 2)]
        if self._hr is not None:
            nomes = ["habilitado", "modo", "fonte_sp", "setpoint", "aquecedor_cmd",
                     "ventilador_cmd", "pot_raw", "falha_dht"]
            for i, nome in enumerate(nomes):
                if hr[i] != self._hr[i]:
                    v = hr[i] / 10 if nome == "setpoint" else hr[i]
                    self.cam.aplicar(nome, v, "modbus")
            if co[0] != self._co[0]:
                self.cam.aplicar("habilitado", co[0], "modbus coil")
            if co[1] != self._co[1]:
                self.cam.aplicar("falha_dht", co[1], "modbus coil")
            s = self.cam.snapshot()

        s = dict(s, pot_raw_cmd=self.cam.cmd["pot_raw"])
        hr = self._cmd_to_hr(s)
        co = [s["habilitado"], s["falha_dht"]]
        ir = [_i16(s["temp"] * 10), _i16(s["umid"] * 10), _i16(s["sp_efetivo"] * 10),
              _i16(s["aquecedor_pwm"]), _i16(s["ventilador_pwm"]), s["pot_raw"], s["estado"],
              s["alarme"], s["led_verde"] | s["led_amarelo"] << 1 | s["led_vermelho"] << 2,
              s["dht_erros"] & 0xFFFF, s["heartbeat"], s["uptime"] & 0xFFFF,
              *_f32(s["temp"]), *_f32(s["umid"]), s["aquecedor_duty"], s["ventilador_duty"]]
        di = [s["led_verde"], s["led_amarelo"], s["led_vermelho"], s["dht_ok"], int(s["alarme"] > 0)]
        self.dev.setValues(FC_HR, 0, hr)
        self.dev.setValues(FC_CO, 0, [bool(x) for x in co])
        self.dev.setValues(FC_IR, 0, ir)
        self.dev.setValues(FC_DI, 0, [bool(x) for x in di])
        self._hr, self._co = hr, co

    async def start(self, host, tcp_port, rtu_port):
        tasks = []
        if tcp_port:
            srv = ModbusTcpServer(self.context, framer=FramerType.SOCKET,
                                  identity=self.identity, address=(host, tcp_port))
            tasks.append(srv.serve_forever())
            self.log(f"[modbus] TCP em {host}:{tcp_port} (unit {UNIT})")
        if rtu_port:
            srv = ModbusTcpServer(self.context, framer=FramerType.RTU,
                                  identity=self.identity, address=(host, rtu_port))
            tasks.append(srv.serve_forever())
            self.log(f"[modbus] RTU sobre TCP em {host}:{rtu_port}")
        await asyncio.gather(*tasks)
