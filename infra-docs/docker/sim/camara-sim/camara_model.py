"""
Modelo da Câmara Climática com ESP32 (planta + firmware simulados).

Hardware representado
---------------------
  ESP32 DevKit
  ├─ DHT22 (GPIO4)  ............ temperatura (°C) e umidade relativa (%UR), leitura a cada 2 s
  ├─ Potenciômetro (GPIO34) .... ADC 12 bits (0..4095) -> setpoint local 20..55 °C
  ├─ Aquecedor (GPIO25) ........ PWM LEDC 8 bits via MOSFET (resistência ~25 W)
  ├─ Ventilador (GPIO26) ....... PWM LEDC 8 bits (troca de ar com o ambiente)
  ├─ OLED SSD1306 128x64 (I2C SDA21/SCL22) ... 6 linhas de 21 caracteres
  └─ LEDs de estado: verde (GPIO16), amarelo (GPIO17), vermelho (GPIO5)

Modelo físico (2 estados térmicos + umidade absoluta)
------------------------------------------------------
  C_h dTh/dt = P - k_hc (Th - Tc)                       (resistência)
  C_c dTc/dt = k_hc (Th - Tc) - k_loss (Tc - T_amb)     (ar + paredes)
  dAH/dt     = S + k_v (AH_amb - AH)                    (umidade absoluta g/m³)
  UR         = AH / AH_sat(Tc) * 100                    (Magnus)
  P = Pmax * aquecedor/100;  k_loss e k_v crescem com o ventilador.

Aquecer reduz a umidade relativa (mesma água, ar mais quente) e ventilar puxa
temperatura e umidade de volta para as do ambiente.

Firmware simulado (laço de controle a cada 1 s)
-----------------------------------------------
  modo 0 MANUAL : PWMs = aquecedor_cmd / ventilador_cmd (controle externo, ex.: Node-RED)
  modo 1 ON/OFF : histerese ±0,5 °C no aquecedor; ventilador 100 % se T > SP+2
  modo 2 PI     : Kp=15 %/°C, Ki=0,15 %/(°C·s), anti-windup; ventilador resfria se T > SP

  Proteções: T >= 60 °C (sobretemperatura) ou falha do DHT22 -> ALARME:
  aquecedor 0 %, ventilador 100 %; libera com T < 55 °C e sensor OK.

  Estados: 0 DESLIGADO, 1 AQUECENDO (e > 1), 2 RESFRIANDO (e < -1),
           3 ESTAVEL (|e| <= 1), 4 ALARME          (e = SP - T)
"""

import math
import random
import threading
import time

ESTADOS = ["DESLIGADO", "AQUECENDO", "RESFRIANDO", "ESTAVEL", "ALARME"]
MODOS = ["MANUAL", "ON/OFF", "PI"]
ALM_SOBRETEMP, ALM_SENSOR = 1, 2

SP_MIN, SP_MAX = 20.0, 55.0
T_ALARME, T_LIBERA = 60.0, 55.0


def ah_sat(t):
    """Umidade absoluta de saturação (g/m³) - fórmula de Magnus."""
    return 6.112 * math.exp(17.67 * t / (t + 243.5)) * 2.1674 / (273.15 + t) * 100


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Camara:
    # parâmetros físicos
    T_AMB, UR_AMB = 25.0, 60.0
    P_MAX = 25.0                   # W
    C_H, C_C = 20.0, 120.0         # J/K
    S_UMID = 0.01                  # g/m³/s (carga úmida dentro da câmara)

    # comandos graváveis: nome -> (tipo, mínimo, máximo)
    COMANDOS = {
        "habilitado": (bool, 0, 1),
        "modo": (int, 0, 2),
        "fonte_sp": (int, 0, 1),          # 0 remoto, 1 potenciômetro
        "setpoint": (float, SP_MIN, SP_MAX),
        "aquecedor_cmd": (float, 0, 100),  # % (modo manual)
        "ventilador_cmd": (float, 0, 100),
        "pot_raw": (int, 0, 4095),         # SIMULAÇÃO: "girar o potenciômetro"
        "falha_dht": (bool, 0, 1),         # SIMULAÇÃO: injeta falha no sensor
    }

    def __init__(self, speed=1.0, log=print):
        self.lock = threading.RLock()
        self.speed = speed
        self.log = log
        self.t0 = time.monotonic()
        # comandos
        self.cmd = {"habilitado": True, "modo": 1, "fonte_sp": 0, "setpoint": 35.0,
                    "aquecedor_cmd": 0.0, "ventilador_cmd": 20.0, "pot_raw": 1755,
                    "falha_dht": False}
        # estados físicos
        self.Tc = self.Th = self.T_AMB
        self.AH_amb = ah_sat(self.T_AMB) * self.UR_AMB / 100
        self.AH = self.AH_amb
        # firmware
        self.temp, self.umid = self.T_AMB, self.UR_AMB   # última leitura válida do DHT22
        self.dht_ok, self.dht_erros, self._falhas_seg = True, 0, 0
        self.pot_lido = self.cmd["pot_raw"]
        self.aquecedor_pwm = self.ventilador_pwm = 0.0
        self.integral = 0.0
        self.onoff_aquecendo = False
        self.alarme = 0
        self.estado = 0
        self.heartbeat = 0
        self._t_dht = self._t_ctrl = 0.0

    # ------------------------------------------------------------ comandos
    def aplicar(self, nome, valor, origem="?"):
        """Valida e aplica um comando vindo de qualquer protocolo. Retorna True se mudou."""
        if nome not in self.COMANDOS:
            return False
        tipo, lo, hi = self.COMANDOS[nome]
        try:
            if isinstance(valor, str):
                valor = valor.strip().lower()
                valor = {"true": 1, "false": 0, "on": 1, "off": 0}.get(valor, valor)
            v = float(valor)
            if math.isnan(v):
                return False
        except (TypeError, ValueError):
            self.log(f"[cmd] {origem}: valor inválido para {nome}: {valor!r}")
            return False
        v = _clamp(v, lo, hi)
        v = bool(round(v)) if tipo is bool else int(round(v)) if tipo is int else round(v, 1)
        with self.lock:
            if self.cmd[nome] == v:
                return False
            self.cmd[nome] = v
            if nome == "modo":
                self.integral = 0.0
        self.log(f"[cmd] {origem}: {nome} = {v}")
        return True

    # ------------------------------------------------------------ simulação
    @property
    def sp_efetivo(self):
        if self.cmd["fonte_sp"] == 1:
            sp = SP_MIN + self.pot_lido / 4095 * (SP_MAX - SP_MIN)
            return round(sp * 2) / 2          # passos de 0,5 °C
        return self.cmd["setpoint"]

    def _fisica(self, dt):
        fan = self.ventilador_pwm / 100
        p = self.P_MAX * self.aquecedor_pwm / 100
        k_hc = 1.0 + 1.0 * fan
        k_loss = 0.4 + 1.6 * fan
        k_v = 0.002 + 0.02 * fan
        n = max(1, int(dt / 0.05))
        h = dt / n
        for _ in range(n):
            q_hc = k_hc * (self.Th - self.Tc)
            self.Th += h * (p - q_hc) / self.C_H
            self.Tc += h * (q_hc - k_loss * (self.Tc - self.T_AMB)) / self.C_C
            self.AH += h * (self.S_UMID + k_v * (self.AH_amb - self.AH))

    def _ler_dht22(self):
        falhou = self.cmd["falha_dht"] or random.random() < 0.01   # 1 % de erros de checksum
        if falhou:
            self.dht_erros += 1
            self._falhas_seg += 1
        else:
            self._falhas_seg = 0
            ur = _clamp(self.AH / ah_sat(self.Tc) * 100, 0, 100)
            self.temp = round(self.Tc + random.gauss(0, 0.1), 1)
            self.umid = round(_clamp(ur + random.gauss(0, 0.5), 0, 100), 1)
        self.dht_ok = self._falhas_seg < 3

    def _ler_pot(self):
        self.pot_lido = int(_clamp(self.cmd["pot_raw"] + random.randint(-3, 3), 0, 4095))

    def _controle(self, dt):
        c = self.cmd
        sp = self.sp_efetivo
        e = sp - self.temp

        # proteções (com histerese de liberação)
        alm = self.alarme
        if not self.dht_ok:
            alm |= ALM_SENSOR
        elif alm & ALM_SENSOR:
            alm &= ~ALM_SENSOR
        if self.temp >= T_ALARME:
            alm |= ALM_SOBRETEMP
        elif alm & ALM_SOBRETEMP and self.temp < T_LIBERA:
            alm &= ~ALM_SOBRETEMP
        if alm != self.alarme:
            self.log(f"[planta] alarme {self.alarme} -> {alm}")
        self.alarme = alm

        if self.alarme:
            aq, ve = 0.0, 100.0
        elif not c["habilitado"]:
            aq, ve = 0.0, 0.0
            self.integral = 0.0
        elif c["modo"] == 0:                          # MANUAL
            aq, ve = c["aquecedor_cmd"], c["ventilador_cmd"]
        elif c["modo"] == 1:                          # ON/OFF com histerese
            if self.temp < sp - 0.5:
                self.onoff_aquecendo = True
            elif self.temp > sp + 0.5:
                self.onoff_aquecendo = False
            aq = 100.0 if self.onoff_aquecendo else 0.0
            ve = 100.0 if self.temp > sp + 2 else 20.0
        else:                                         # PI
            kp, ki = 15.0, 0.15
            u = kp * e + self.integral
            if 0 < u < 100 or (u >= 100 and e < 0) or (u <= 0 and e > 0):
                self.integral = _clamp(self.integral + ki * e * dt, 0, 100)
            aq = _clamp(kp * e + self.integral, 0, 100)
            ve = 20.0 + _clamp(30 * (-e - 0.5), 0, 80)
        self.aquecedor_pwm, self.ventilador_pwm = round(aq, 1), round(ve, 1)

        if self.alarme:
            self.estado = 4
        elif not c["habilitado"]:
            self.estado = 0
        elif abs(e) <= 1:
            self.estado = 3
        else:
            self.estado = 1 if e > 0 else 2

    def step(self, dt_real):
        """Avança a simulação dt_real segundos (multiplicado por speed)."""
        with self.lock:
            dt = dt_real * self.speed
            self._fisica(dt)
            self._t_dht += dt
            self._t_ctrl += dt
            if self._t_dht >= 2.0:                     # DHT22: no máximo 0,5 Hz
                self._t_dht = 0.0
                self._ler_dht22()
            if self._t_ctrl >= 1.0:
                self._ler_pot()
                self._controle(self._t_ctrl)
                self._t_ctrl = 0.0
                self.heartbeat = (self.heartbeat + 1) & 0xFFFF

    # ------------------------------------------------------------ saídas
    def oled(self):
        """Conteúdo da tela OLED (6 linhas x 21 caracteres)."""
        c = self.cmd
        fonte = "POT" if c["fonte_sp"] else "REM"
        linhas = [
            "CAMARA CLIMATICA",
            f"T:{self.temp:5.1f}C UR:{self.umid:5.1f}%" if self.dht_ok else "T: --.-C UR: --.-%",
            f"SP:{self.sp_efetivo:5.1f}C {fonte} {MODOS[c['modo']]}",
            f"AQ:{self.aquecedor_pwm:3.0f}% VENT:{self.ventilador_pwm:3.0f}%",
            f"EST: {ESTADOS[self.estado]}",
            ("!SOBRETEMP " if self.alarme & ALM_SOBRETEMP else "")
            + ("!SENSOR" if self.alarme & ALM_SENSOR else "") or f"UP {self.uptime()}s",
        ]
        return [ln[:21] for ln in linhas]

    def uptime(self):
        return int(time.monotonic() - self.t0)

    def snapshot(self):
        with self.lock:
            c = self.cmd
            return {
                # medições
                "temp": self.temp,
                "umid": self.umid,
                "pot_raw": self.pot_lido,
                "sp_efetivo": self.sp_efetivo,
                # atuadores (valor aplicado)
                "aquecedor_pwm": self.aquecedor_pwm,
                "ventilador_pwm": self.ventilador_pwm,
                "aquecedor_duty": round(self.aquecedor_pwm * 255 / 100),
                "ventilador_duty": round(self.ventilador_pwm * 255 / 100),
                # comandos atuais
                "habilitado": int(c["habilitado"]),
                "modo": c["modo"],
                "modo_txt": MODOS[c["modo"]],
                "fonte_sp": c["fonte_sp"],
                "setpoint": c["setpoint"],
                "aquecedor_cmd": c["aquecedor_cmd"],
                "ventilador_cmd": c["ventilador_cmd"],
                "falha_dht": int(c["falha_dht"]),
                "pot_sim": c["pot_raw"],          # posição simulada do potenciômetro
                # estado da planta
                "estado": self.estado,
                "estado_txt": ESTADOS[self.estado],
                "alarme": self.alarme,
                "led_verde": int(self.estado == 3),
                "led_amarelo": int(self.estado in (1, 2)),
                "led_vermelho": int(self.estado == 4),
                "dht_ok": int(self.dht_ok),
                "dht_erros": self.dht_erros,
                "heartbeat": self.heartbeat,
                "uptime": self.uptime(),
                "oled": self.oled(),
            }
