"""
Adaptador S7 (S7comm / ISO-on-TCP, porta 102) da câmara - python-snap7.

DB1 - comandos (graváveis)        nodes7 (node-red-contrib-s7)
  DBX0.0  habilitado   BOOL        DB1,X0.0
  DBX0.1  fonte_sp     BOOL        DB1,X0.1   (0 remoto, 1 potenciômetro)
  DBX0.2  falha_dht    BOOL        DB1,X0.2   (SIMULAÇÃO)
  DBW2    modo         INT         DB1,INT2   (0 MANUAL, 1 ON/OFF, 2 PI)
  DBD4    setpoint     REAL        DB1,REAL4  (°C)
  DBD8    aquecedor_cmd REAL       DB1,REAL8  (%)
  DBD12   ventilador_cmd REAL      DB1,REAL12 (%)
  DBW16   pot_raw      INT         DB1,INT16  (SIMULAÇÃO 0..4095)

DB1 - estado (somente leitura)
  DBD20   temp           REAL      DB1,REAL20
  DBD24   umid           REAL      DB1,REAL24
  DBD28   sp_efetivo     REAL      DB1,REAL28
  DBD32   aquecedor_pwm  REAL      DB1,REAL32
  DBD36   ventilador_pwm REAL      DB1,REAL36
  DBW40   estado         INT       DB1,INT40
  DBW42   alarme         INT       DB1,INT42
  DBX44.0 led_verde  44.1 led_amarelo  44.2 led_vermelho  44.3 dht_ok   (DB1,X44.0 ...)
  DBW46   pot_raw (ADC)  INT       DB1,INT46
  DBD48   heartbeat      DINT      DB1,DINT48
  DBD52   uptime         DINT      DB1,DINT52

Imagem de processo (como num CLP):
  IW0 = potenciômetro (0..4095)   Q0.0/Q0.1/Q0.2 = LEDs verde/amarelo/vermelho
  QB2 = duty do aquecedor (0..255) QB3 = duty do ventilador (0..255)
"""

import struct

import snap7
from snap7.type import SrvArea

DB_SIZE = 64
CMD_LEN = 18


class S7Adapter:
    def __init__(self, camara, log):
        self.cam, self.log = camara, log
        self.db1 = bytearray(DB_SIZE)
        self.pe = bytearray(16)
        self.pa = bytearray(16)
        self.mk = bytearray(64)
        self._cmd = None
        self.server = None

    def start(self, port=102):
        self.server = snap7.server.Server(log=False)
        self.server.register_area(SrvArea.DB, 1, self.db1)
        self.server.register_area(SrvArea.PE, 0, self.pe)
        self.server.register_area(SrvArea.PA, 0, self.pa)
        self.server.register_area(SrvArea.MK, 0, self.mk)
        self.server.start(tcp_port=port)
        self.log(f"[s7] servidor na porta {port} (DB1, I, Q, M)")

    def _decode_cmd(self, b):
        modo, = struct.unpack_from(">h", b, 2)
        sp, aq, ve = struct.unpack_from(">fff", b, 4)
        pot, = struct.unpack_from(">h", b, 16)
        return {"habilitado": b[0] & 1, "fonte_sp": (b[0] >> 1) & 1, "falha_dht": (b[0] >> 2) & 1,
                "modo": modo, "setpoint": round(sp, 1), "aquecedor_cmd": round(aq, 1),
                "ventilador_cmd": round(ve, 1), "pot_raw": pot}

    def _encode_cmd(self, c):
        b = bytearray(CMD_LEN)
        b[0] = int(c["habilitado"]) | int(c["fonte_sp"]) << 1 | int(c["falha_dht"]) << 2
        struct.pack_into(">h", b, 2, c["modo"])
        struct.pack_into(">fff", b, 4, c["setpoint"], c["aquecedor_cmd"], c["ventilador_cmd"])
        struct.pack_into(">h", b, 16, c["pot_raw"])
        return b

    def sync(self, s):
        self.server.lock_area(SrvArea.DB, 1)
        try:
            atual = bytes(self.db1[:CMD_LEN])
            if self._cmd is not None and atual != self._cmd:
                novo, velho = self._decode_cmd(atual), self._decode_cmd(self._cmd)
                for k, v in novo.items():
                    if v != velho[k]:
                        self.cam.aplicar(k, v, "s7")
                s = self.cam.snapshot()
            cmd = self._encode_cmd(dict(self.cam.cmd))
            self.db1[:CMD_LEN] = cmd
            struct.pack_into(">fffff", self.db1, 20, s["temp"], s["umid"], s["sp_efetivo"],
                             s["aquecedor_pwm"], s["ventilador_pwm"])
            struct.pack_into(">hh", self.db1, 40, s["estado"], s["alarme"])
            self.db1[44] = s["led_verde"] | s["led_amarelo"] << 1 | s["led_vermelho"] << 2 | s["dht_ok"] << 3
            struct.pack_into(">hii", self.db1, 46, s["pot_raw"], s["heartbeat"], s["uptime"])
            self._cmd = bytes(cmd)
        finally:
            self.server.unlock_area(SrvArea.DB, 1)
        struct.pack_into(">H", self.pe, 0, s["pot_raw"])
        self.pa[0] = s["led_verde"] | s["led_amarelo"] << 1 | s["led_vermelho"] << 2
        self.pa[2], self.pa[3] = s["aquecedor_duty"], s["ventilador_duty"]

    def stop(self):
        if self.server:
            self.server.stop()
            self.server.destroy()
