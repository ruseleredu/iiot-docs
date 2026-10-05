# SCADA Lab — laboratório multiprotocolo

Ambiente didático em Docker para comparar **MQTT, Modbus TCP, OPC-UA e Siemens S7** usando a mesma planta simulada.

## Arquitetura

```text
                 +----------------------+
                 |       FUXA           |
                 |     SCADA / HMI      |
                 +----+------+------+---+
                      |      |      |
                  Modbus   OPC-UA   S7
                      |      |      |
               +------+------+------+ 
               |   Simuladores       |
               +---------------------+

 ESP32/cliente MQTT
        |
        v
 +-------------+       +-------------+
 |  Mosquitto  +------>+  Node-RED   |
 +-------------+       +------+------+ 
                               |      |
                               v      v
                            SQLite Dashboard
```


## Subir

```bash
docker compose up -d --build
```

PowerShell:

```powershell
.\scripts\up.ps1
```

## Acessos

| Serviço | Endereço |
|---|---|
| Node-RED | http://localhost:1880 |
| Dashboard | http://localhost:1880/dashboard |
| FUXA | http://localhost:1881 |
| MQTT | localhost:1883 |
| Modbus TCP | localhost:502 |
| OPC-UA | localhost:4840 |
| S7 | localhost:1102 |

## Por que S7 usa 1102?

A porta padrão do protocolo S7 é TCP/102. Para manter o laboratório simples em Windows, macOS e Linux, o container escuta em 1102. Se quiser usar 102 no host, altere `S7_PORT` no `.env` e o `tcp_port` do simulador conforme a plataforma.

## Node-RED

A imagem instala automaticamente:

- `@flowfuse/node-red-dashboard` 1.32.0
- `node-red-node-sqlite` 2.0.1

O projeto usa o FlowFuse Dashboard, sucessor do Node-RED Dashboard original.

Banco:

```text
node-red/data/scada.sqlite
```

## MQTT

Exemplo:

```bash
docker compose exec mosquitto mosquitto_pub -h localhost -t lab/plant/level -m 65.5
```

Tópicos sugeridos:

```text
lab/plant/level
lab/plant/temperature
lab/plant/pressure
lab/plant/pump/state
lab/plant/pump/command
```

## Modbus TCP

Dentro do Docker:

```text
Host: modbus-sim
Port: 502
Unit ID: 1
```

Mapa:

| Área | Endereço lógico | Variável | Escala |
|---|---:|---|---:|
| Holding Register | 40001 | Level | x10 |
| Holding Register | 40002 | Temperature | x10 |
| Holding Register | 40003 | Pressure | x10 |
| Holding Register | 40004 | PumpSpeed | x10 |
| Coil | 00001 | PumpRunning | BOOL |
| Coil | 00002 | PumpCommand | BOOL |

## OPC-UA

Endpoint interno:

```text
opc.tcp://opcua-sim:4840/freeopcua/server/
```

Árvore:

```text
Objects
└── Plant
    ├── Tank
    │   ├── Level
    │   ├── Temperature
    │   └── Pressure
    └── Pump
        ├── Running
        └── Speed
```

## Siemens S7

Endpoint interno:

```text
s7-sim:1102
```

DB1:

```text
DBD0    Level
DBD4    Temperature
DBD8    Pressure
DBD12   PumpSpeed
DBX16.0 PumpRunning
DBX16.1 PumpCommand
```

O servidor S7 é uma emulação para laboratório; não representa um PLC Siemens físico.

## FUXA

No FUXA, crie dispositivos apontando para:

```text
Modbus TCP  -> modbus-sim:502
OPC-UA      -> opcua-sim:4840
S7          -> s7-sim:1102
MQTT        -> mosquitto:1883
```

## Exercícios

1. ESP32/Wokwi → MQTT → Mosquitto → Node-RED.
2. MQTT → Node-RED → SQLite.
3. MQTT → Node-RED → Dashboard.
4. Modbus TCP → FUXA.
5. OPC-UA → FUXA.
6. S7 → FUXA.
7. Comparar a mesma variável nos quatro protocolos.
8. Integrar FUXA + Node-RED + SQLite + Dashboard.

## Parar

```bash
docker compose down
```

Para apagar volumes nomeados:

```bash
docker compose down -v
```

## Segurança

O Mosquitto está deliberadamente configurado com `allow_anonymous true` para laboratório local. Não use esta configuração em produção.
