# camara-sim: Câmara Climática ESP32 simulada

Simulador **isolado** de uma câmara climática com ESP32, DHT22, OLED, potenciômetro (ADC)
e aquecedor e ventilador por PWM. Não traz broker, Node-RED nem MQTT Explorer: ele **se
conecta** ao que já existe. Pode ser o LAB IoT, o kit do grupo (`gen_iot_scada_portal.py`)
ou qualquer broker.

A mesma planta é exposta ao mesmo tempo por:

| Protocolo | Porta | Biblioteca |
|---|---|---|
| MQTT 5 (cliente, como o ESP32 real) | broker:1883 | paho-mqtt 2.1 |
| Modbus TCP | 502 | pymodbus 3.9.2 |
| Modbus RTU sobre TCP (quadro RTU + CRC, sem porta serial) | 5021 | pymodbus |
| Siemens S7 (ISO-on-TCP) | 102 | python-snap7 3.2 |
| OPC-UA | 4840 | asyncua 2.1 |

Um comando enviado por qualquer protocolo (por exemplo, o setpoint) aparece em todos os outros.

## Compatibilidade com o LAB IoT (`gen_iot_scada_portal.py`)

| Convenção do LAB IoT | No simulador |
|---|---|
| Tópicos do grupo `<grupo>/...` (a ponte do kit só repassa `<grupo>/#`) | `<grupo>/camara/telemetria`, `/cmd`, `/cmd/<campo>`, `/status`, `/oled` |
| Serviços na rede `labnet`, nomes `<grupo>-nodered`, `<grupo>-fuxa` | host **`<grupo>-camara`** (ex.: `lab05-a-camara`) |
| Broker `mosquitto:1883`, anônimo | `MQTT_HOST=mosquitto` ao entrar na rede do lab/kit |
| Node-RED em `/<grupo>/` (httpNodeRoot) | dashboard em `/<grupo>/dashboard/camara` |
| Volume `/data` do grupo | SQLite em `/data/camara.sqlite` |
| ntfy: `NTFY_URL`, `NTFY_TOPIC`, `NTFY_TOKEN` no Node-RED | alarmes da câmara viram notificação no celular |
| Nós do Dockerfile do lab (modbus, s7, opcua, sqlite, dashboard 2) | os fluxos usam só esses (nada de serial nem `ui-led`) |

O endereço OPC-UA se adapta ao cliente: o servidor devolve o mesmo host que o cliente usou
(`localhost`, IP do PC ou `lab05-a-camara`). UaExpert, Node-RED e FUXA conectam sem
configurar nada.

## 1. Rodar

Escolha **uma** das três formas.

### A) Python (direto do repositório)

```powershell
py -m pip install -r requirements.txt
py camara_sim.py --grupo lab05-a                       # broker em localhost:1883 (kit no PC)
py camara_sim.py --grupo lab05-a --mqtt-host 192.168.0.10   # broker do laboratório
py camara_sim.py --grupo lab05-a --sem-mqtt            # só Modbus/S7/OPC-UA
```

No Linux e no macOS, as portas 102 e 502 exigem administrador. Use outras portas, por exemplo
`--s7-port 1102 --modbus-tcp-port 5020`. Todas as opções aparecem em `py camara_sim.py --help`.

### B) Docker, sozinho

```powershell
copy .env.example .env          # ajuste GRUPO e, se precisar, as portas
docker compose up -d --build
docker compose logs -f
```

Se o kit do grupo estiver rodando no mesmo PC, o simulador publica no mosquitto dele
(`host.docker.internal:1883`).

### C) Docker, dentro da rede do kit ou do laboratório

Assim o Node-RED e o FUXA do grupo enxergam `lab05-a-camara` (Modbus/S7/OPC-UA).

```powershell
docker network ls                 # procure <pasta-do-kit>_labnet, ex.: lab05-a_labnet
# no .env:  LAB_REDE=lab05-a_labnet
docker compose -f docker-compose.yml -f docker-compose.lab.yml up -d --build
```

**Professor, uma câmara por grupo no servidor do laboratório:**

```powershell
py gerar_compose_lab.py --lab lab05 --grupos 10          # mesmo --lab/--grupos do portal
docker compose -f docker-compose.camaras.yml up -d --build
```

Isso cria `lab05-a-camara` … `lab05-j-camara` na rede `lab05_labnet`, sem abrir portas no
servidor.

### Testar

```powershell
py testar_clientes.py --grupo lab05-a      # escreve o setpoint por um protocolo e lê pelos outros
```

## 2. Node-RED do grupo

```powershell
py gerar_flows.py --grupo lab05-a          # -> flows/camara-lab05-a.json
```

No Node-RED do grupo, vá em Menu ☰ → *Import* → selecione o arquivo → *Import* → *Deploy*.
O arquivo cria quatro abas:

| Aba | O que faz |
|---|---|
| Câmara - Dashboard | `/<grupo>/dashboard/camara`: medidores, gráficos, LEDs, réplica do OLED, comandos, simulação |
| Câmara - Banco SQLite | `/data/camara.sqlite`, 1 amostra a cada 10 s, consultas prontas e histórico no dashboard |
| Câmara - Controle Node-RED | controlador externo (ON/OFF + ventilador P) e **alarmes → ntfy** do grupo |
| Câmara - Modbus / S7 / OPC-UA | lê a câmara por cada protocolo e republica em `<grupo>/camara/via/<protocolo>` |

> Já existe um Dashboard 2.0 no Node-RED do grupo? O Dashboard 2.0 aceita só um `ui-base`.
> Ao importar, aponte a página "Câmara Climática" para o `ui-base` que já existe e apague o
> importado.

## 3. FUXA do grupo (não testado aqui; confira os nomes dos campos na versão 1.3.4)

| Conexão no FUXA | Configuração |
|---|---|
| MQTT client | `mqtt://mosquitto:1883`, assinar `lab05-a/camara/telemetria` (JSON) e publicar em `lab05-a/camara/cmd/<campo>` |
| Modbus TCP | IP `lab05-a-camara`, porta 502, slave 1. Input Registers 0–17 e Holding 0–7 (tabelas abaixo; float32 em ABCD) |
| Siemens S7 | IP `lab05-a-camara`, rack 0, slot 1. DB1 (tabela abaixo) |
| OPC-UA | `opc.tcp://lab05-a-camara:4840`, segurança None, anônimo. Navegue em `Objects/Camara` |

## 4. A câmara

### Objetivos de projeto atendidos

| Objetivo | Implementação |
|---|---|
| Medir temperatura e umidade | DHT22: leitura a cada 2 s, ruído ±0,1 °C e ±0,5 %UR, 1 % de erros de leitura |
| Setpoint configurável | `setpoint` remoto (20–55 °C) ou pelo potenciômetro (`fonte_sp = 1`) |
| Aquecedor e ventilador por PWM | 0–100 % e duty LEDC de 8 bits (0–255) |
| Tela OLED | 6 linhas × 21 caracteres (SSD1306 128×64) |
| Potenciômetro | ADC de 12 bits (0–4095) |
| Estratégia de controle | MANUAL (controle externo), ON/OFF com histerese e PI com anti-windup |
| Estado da planta | DESLIGADO, AQUECENDO, RESFRIANDO, ESTÁVEL e ALARME; LEDs verde, amarelo e vermelho |

### Pinagem sugerida para a câmara real

| Componente | ESP32 |
|---|---|
| DHT22 | GPIO4 (pull-up 10 kΩ) |
| Potenciômetro 10 kΩ | GPIO34 (ADC1_CH6) |
| Aquecedor (~25 W) | GPIO25 → MOSFET, LEDC 8 bits |
| Ventilador 12 V | GPIO26 → MOSFET, LEDC 8 bits, 25 kHz |
| OLED SSD1306 | SDA GPIO21 / SCL GPIO22 (0x3C) |
| LEDs verde, amarelo e vermelho | GPIO16, GPIO17 e GPIO5 |

### Modelo e firmware

- **Térmico:** dois estados (resistência e câmara) e perdas para o ambiente (25 °C).
  O ventilador aumenta a troca de calor.
- **Umidade:** umidade absoluta mais uma carga úmida interna. A UR sai pela fórmula de Magnus,
  por isso **aquecer derruba a UR**.
- **Tempo:** em tempo real, a câmara vai de 25 °C a 35 °C em cerca de 1,5 min. `SIM_SPEED=5`
  ou `10` acelera.
- **Modos:**
  - `0` MANUAL usa `aquecedor_cmd` e `ventilador_cmd`.
  - `1` ON/OFF tem histerese de ±0,5 °C; o ventilador vai a 100 % se T > SP + 2.
  - `2` PI usa Kp = 15 e Ki = 0,15, com anti-windup.
- **Proteções:** com T ≥ 60 °C ou falha do DHT22, o estado vai para ALARME. O aquecedor vai a
  0 % e o ventilador a 100 %. O alarme é liberado com T < 55 °C e o sensor OK.
- **`estado`:** 0 DESLIGADO · 1 AQUECENDO (e > 1) · 2 RESFRIANDO (e < −1) · 3 ESTAVEL
  (|e| ≤ 1) · 4 ALARME. Os bits de `alarme` são 1 = sobretemperatura e 2 = sensor.

### MQTT (base `<grupo>/camara`)

| Tópico | Sentido | Conteúdo |
|---|---|---|
| `…/status` | ESP32 → | `online`/`offline` (retido, *Last Will*) |
| `…/telemetria` | ESP32 → | JSON a cada 2 s |
| `…/oled` | ESP32 → | texto da tela |
| `…/cmd` | → ESP32 | JSON parcial, ex.: `{"setpoint": 40, "modo": 2}` |
| `…/cmd/<campo>` | → ESP32 | valor simples |

Campos de comando: `habilitado`, `modo`, `fonte_sp`, `setpoint`, `aquecedor_cmd`,
`ventilador_cmd`, `pot_raw` (simulação) e `falha_dht` (simulação). Valores fora da faixa são
saturados.

### Modbus (TCP e RTU sobre TCP): unit 1, endereços base 0

| Tabela | End. | Variável |
|---|---|---|
| Coil | 0 / 1 | habilitado / falha_dht |
| Discrete input | 0–4 | led_verde, led_amarelo, led_vermelho, dht_ok, alarme ativo |
| Holding | 0 / 1 / 2 | habilitado / modo / fonte_sp |
| Holding | 3 | setpoint × 10 (350 = 35,0 °C) |
| Holding | 4 / 5 | aquecedor_cmd / ventilador_cmd (%) |
| Holding | 6 / 7 | pot_raw / falha_dht (simulação) |
| Input | 0 / 1 / 2 | temp×10 / umid×10 / sp_efetivo×10 |
| Input | 3 / 4 / 5 | aquecedor_pwm / ventilador_pwm / pot_raw |
| Input | 6 / 7 / 8 | estado / alarme / leds (bit0 verde, bit1 amarelo, bit2 vermelho) |
| Input | 9 / 10 / 11 | dht_erros / heartbeat / uptime |
| Input | 12–13 / 14–15 | temp / umid em float32 ABCD |
| Input | 16 / 17 | aquecedor_duty / ventilador_duty (0–255) |

No `node-red-contrib-modbus`, o RTU sobre TCP usa o tipo **TELNET**. O tipo "RTU-BUFFERED"
envia, na verdade, Modbus TCP.

### S7: DB1 (sem acesso otimizado), rack 0, slot 1

| Endereço | nodes7 | Variável |
|---|---|---|
| DBX0.0 / 0.1 / 0.2 | `DB1,X0.0` … | habilitado / fonte_sp / falha_dht (graváveis) |
| DBW2 | `DB1,INT2` | modo (gravável) |
| DBD4 / 8 / 12 | `DB1,REAL4` … | setpoint / aquecedor_cmd / ventilador_cmd (graváveis) |
| DBW16 | `DB1,INT16` | pot_raw simulação (gravável) |
| DBD20 / 24 / 28 / 32 / 36 | `DB1,REAL20` … | temp / umid / sp_efetivo / aquecedor_pwm / ventilador_pwm |
| DBW40 / 42 | `DB1,INT40` / `INT42` | estado / alarme |
| DBX44.0–44.3 | `DB1,X44.0` … | led_verde, led_amarelo, led_vermelho, dht_ok |
| DBW46, DBD48, DBD52 | `DB1,INT46`, `DINT48`, `DINT52` | pot_raw (ADC), heartbeat, uptime |

Imagem de processo: `IW0` = potenciômetro; `Q0.0–Q0.2` = LEDs; `QB2`/`QB3` = duty do
aquecedor e do ventilador.

### OPC-UA: `ns=2;s=Camara.<variável>` (URI `urn:utfpr:camara-climatica`)

```
Objects/Camara/
  Medicoes/   temp, umid, sp_efetivo (Double) · pot_raw (Int32)
  Atuadores/  aquecedor_pwm, ventilador_pwm (Double) · aquecedor_duty, ventilador_duty (Int32)
  Estado/     estado, alarme, dht_erros, heartbeat, uptime (Int32) · estado_txt, oled (String)
              led_verde, led_amarelo, led_vermelho, dht_ok (Boolean)
  Comandos/   habilitado (Boolean) · modo, fonte_sp (Int32) · setpoint, aquecedor_cmd,
              ventilador_cmd (Double)                                         [graváveis]
  Simulacao/  pot_raw_sim (Int32) · falha_dht (Boolean)                       [graváveis]
```

## 5. Atividades sugeridas

1. Comparar ON/OFF, PI e o controlador do Node-RED pela consulta "Erro médio |SP − T| por modo" no SQLite.
2. Escrever o próprio controlador na aba *Controle Node-RED* (P, PI, PID, fuzzy).
3. Observar o acoplamento térmico e de umidade: ventilar e aquecer, e ver o que acontece com a UR.
4. Provocar o alarme (MANUAL, aquecedor 100 %, ventilador 0 %) e receber o aviso no celular pelo ntfy.
5. Ler a mesma variável por MQTT, Modbus, S7 e OPC-UA e comparar formatos (int×10, float32, REAL) e latência.
6. Parar o simulador (`docker compose stop`) e ver o *Last Will* `offline` no dashboard.

## Arquivos

| Arquivo | Função |
|---|---|
| `camara_model.py` | planta, DHT22, ADC, PWM, controle, estados e OLED |
| `camara_sim.py` | programa principal (opções por argumento ou variável de ambiente) |
| `proto_mqtt.py`, `proto_modbus.py`, `proto_s7.py`, `proto_opcua.py` | um adaptador por protocolo |
| `testar_clientes.py` | teste de ponta a ponta em todos os protocolos |
| `gerar_flows.py` | fluxos do Node-RED para um grupo |
| `gerar_compose_lab.py` | uma câmara por grupo no servidor do laboratório |
| `docker-compose.yml`, `docker-compose.lab.yml`, `.env.example` | Docker sozinho / na rede do lab ou do kit |
