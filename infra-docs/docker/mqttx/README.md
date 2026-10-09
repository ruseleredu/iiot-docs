# MQTT Stack (Mosquitto + Web Clients)

Complete Docker stack with:

- **Eclipse Mosquitto** – MQTT broker
- **MQTTX Web** – Modern web MQTT client (similar to HiveMQ WebSocket Client)
- **MQTT Explorer** – Excellent topic explorer with hierarchical view

---

## Quick Start

```bash
docker compose up -d
```

---

## Services & Ports

| Service                 | URL / Address         | Credentials      | Notes                            |
| ----------------------- | --------------------- | ---------------- | -------------------------------- |
| **Mosquitto MQTT**      | `localhost:1883`      | Anonymous        | For ESP32, Arduino, desktop apps |
| **Mosquitto WebSocket** | `ws://localhost:9001` | Anonymous        | For browser clients              |
| **MQTTX Web**           | http://localhost:8080 | —                | Beautiful chat-style client      |
| **MQTT Explorer**       | http://localhost:3000 | admin / admin123 | Hierarchical topic explorer      |

---

## How to connect the web clients

### MQTTX Web (http://localhost:8080)
1. Click **New Connection**
2. Settings:
   - Name: `Local Mosquitto`
   - Host: `localhost` (or your machine IP)
   - Port: `9001`
   - Protocol: **WebSocket**
   - Path: leave empty or `/`
3. Click **Connect**

### MQTT Explorer (http://localhost:3000)
1. Login with `admin` / `admin123`
2. Create a new connection:
   - Protocol: **mqtt** or **ws**
   - Host: `localhost` (or your machine IP)
   - Port: `1883` (for mqtt) or `9001` (for WebSocket)
3. Connect and explore topics in a tree view

---

## Useful commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f mosquitto
docker compose logs -f mqtt-explorer

# Restart only Mosquitto
docker compose restart mosquitto
```

---

## Optional: Enable authentication

1. Create a password file:
```bash
docker run -it --rm -v $(pwd)/mosquitto/config:/mosquitto/config \
  eclipse-mosquitto mosquitto_passwd -c /mosquitto/config/passwd youruser
```

2. Edit `mosquitto/config/mosquitto.conf` and change:
```conf
allow_anonymous false
password_file /mosquitto/config/passwd
```

3. Restart:
```bash
docker compose restart mosquitto
```

---

## Project structure

```
.
├── docker-compose.yml
├── README.md
└── mosquitto/
    ├── config/
    │   └── mosquitto.conf
    ├── data/
    └── log/
```
