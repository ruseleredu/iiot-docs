# ScadaBR in Docker (Derby + Windows serial port)

Runs [ScadaBR 1.2](https://github.com/ScadaBR/ScadaBR) on Tomcat 9 / Java 8 with the
embedded **Derby** database. A Windows serial port (e.g. **COM1**) is made available
inside the container as **`/dev/ttyUSB0`**, for Modbus RTU and other serial protocols.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Compiles ScadaBR from GitHub and packages it on `tomcat:9.0-jdk8-temurin` |
| `docker-compose.yml` | Runs the container with persistent volumes and the serial bridge |
| `docker-entrypoint.sh` | Writes `env.properties`, creates `/dev/ttyUSB0`, starts Tomcat |
| `com2tcp.py` | Runs **on Windows**: shares COM1 over TCP port 7000 |

## Requirements

- Windows 11 with **Docker Desktop** (WSL 2 backend)
- **Python 3** for Windows + `pyserial` (only for the serial bridge)

## Quick start

```powershell
cd scadabr-docker
docker compose up -d --build
docker compose logs -f scadabr      # wait for "Server startup in ..."
```

Open **http://localhost:8080/ScadaBR** and log in with **admin / admin**.
Change the password right away (*Users* menu).

The first build downloads the source and compiles it (a few minutes). The first start
creates the Derby database (about a minute).

## Serial port on Windows 11: COM1 → /dev/ttyUSB0

Docker Desktop cannot pass Windows COM ports into a container directly. Two ways
around it:

| | Option A: TCP bridge (default) | Option B: usbipd-win |
|---|---|---|
| Works with | Any COM port, **including built-in COM1** and USB adapters | **USB**-serial adapters only |
| Serial settings (baud, parity) | Set in `com2tcp.py` on Windows | Set in ScadaBR |
| Extra software | Python + pyserial | usbipd-win |
| Timing | Adds a few ms of latency | Native |

### Option A: TCP bridge (enabled by default)

```
[device] ── COM1 ── com2tcp.py (Windows, TCP 7000) ── socat ── /dev/ttyUSB0 ── ScadaBR
```

1. Install the Python dependency (once):

   ```powershell
   pip install pyserial
   ```

2. Start the bridge, using the same serial settings as your field device:

   ```powershell
   python com2tcp.py --port COM1 --baud 9600 --parity N --stopbits 1 --tcp-port 7000
   ```

   Other options: `--bytesize 7`, `--parity E`, `--stopbits 2`, `--rtscts`.
   Check the real port name in *Device Manager → Ports (COM & LPT)*.

3. If Windows Firewall asks, allow Python on **Private** networks. Or create the rule
   yourself in an admin PowerShell:

   ```powershell
   New-NetFirewallRule -DisplayName "ScadaBR serial bridge" -Direction Inbound `
     -Protocol TCP -LocalPort 7000 -Action Allow -Profile Private
   ```

   > Anyone who can reach port 7000 can talk to your serial device. Do not open it
   > on Public networks.

4. Start or restart the container: `docker compose up -d`.
   In the logs you should see `Serial bridge: /dev/ttyUSB0 <-> tcp:host.docker.internal:7000`,
   and the bridge window shows `client connected`.

5. In ScadaBR, create the data source (e.g. *Modbus Serial*) with port
   **`/dev/ttyUSB0`**. Set the same baud rate as the bridge; the real serial settings
   are the ones in `com2tcp.py`. For Modbus RTU, use a timeout of **1000 ms or more**.

**Start the bridge with Windows** by creating `start-bridge.bat` and putting a shortcut
to it in `shell:startup` (Win+R → `shell:startup`):

```bat
@echo off
cd /d %~dp0
python com2tcp.py --port COM1 --baud 9600 --tcp-port 7000
```

If the bridge is restarted, the container reconnects on its own within about 5 s.
Disable and re-enable the data source in ScadaBR afterwards so it reopens the port.

### Option B: USB-serial adapter with usbipd-win

This works only if your COM port is a USB adapter (FTDI, CH340, CP210x, PL2303).

1. Install usbipd-win in an admin PowerShell, then list the devices:

   ```powershell
   winget install usbipd
   usbipd list
   ```

   Note the **BUSID** of the adapter (e.g. `2-3`).

2. Share the adapter and attach it to WSL. Use admin for `bind`; you only need it
   once.

   ```powershell
   usbipd bind --busid 2-3
   usbipd attach --wsl --busid 2-3 --auto-attach
   ```

   Keep this window open while `--auto-attach` is running. It re-attaches the
   adapter after a replug.

3. Check that the adapter appears from any WSL distro: `ls -l /dev/ttyUSB*`.
   FTDI, CH340, CP210x and PL2303 adapters appear as `/dev/ttyUSB0`. Devices that
   use the USB CDC class (many Arduino-type boards) appear as `/dev/ttyACM0`.

4. In `docker-compose.yml`, **delete the `SERIAL_TCP` line** and uncomment:

   ```yaml
   devices:
     - /dev/ttyUSB0:/dev/ttyUSB0
   ```

   For an ACM device use `- /dev/ttyACM0:/dev/ttyUSB0`.
   Then run `docker compose up -d`.

> If the device is not attached, the container **will not start** with this option.

## Configuration

These are environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|---|---|---|
| `DB_TYPE` | `derby` | Database type |
| `DB_URL` | `/data/scadabrDB` | Derby database folder (inside the `scadabr-data` volume) |
| `SERIAL_TCP` | `host.docker.internal:7000` | Bridge address. Leave empty to disable |
| `SERIAL_DEVICE` | `/dev/ttyUSB0` | Device name created in the container |
| `SERIAL_PORTS` | = `SERIAL_DEVICE` | Ports listed by ScadaBR, `:`-separated (e.g. `/dev/ttyUSB0:/dev/ttyUSB1`) |
| `TZ` | `America/Sao_Paulo` | Time zone used for timestamps |
| `CATALINA_OPTS` | `-Xms256m -Xmx1024m ...` | JVM memory and options |
| `API_AUTHENTICATION` | `disabled` | SOAP API authentication (`enabled`/`disabled`) |

To build a different branch or tag, change `SCADABR_REF` under `build.args`.

**More than one serial port:** run one `com2tcp.py` per port on different TCP ports
(7000, 7001, ...). The container only creates one bridged device, so for extra
ports use Option B or extend `docker-entrypoint.sh` with another `socat` loop.

## Data and backups

| Volume | Contents |
|---|---|
| `scadabr_scadabr-data` | Derby database (configuration + history) |
| `scadabr_scadabr-uploads` | Background images of graphical views |
| `scadabr_scadabr-filedata` | Image data points |
| `scadabr_scadabr-logs` | Tomcat / ScadaBR logs |

**Back up** the database. Stop the container first, because Derby must not be
copied while it is running.

```powershell
docker compose stop scadabr
docker run --rm -v scadabr_scadabr-data:/data -v ${PWD}:/backup alpine tar czf /backup/scadabr-data.tgz -C /data .
docker compose start scadabr
```

**Restore:**

```powershell
docker compose stop scadabr
docker run --rm -v scadabr_scadabr-data:/data -v ${PWD}:/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/scadabr-data.tgz -C /data"
docker compose start scadabr
```

You can also export the project as JSON from *Import/Export* in ScadaBR. ZIP
export does not work in ScadaBR 1.2.

## Common commands

```powershell
docker compose up -d --build          # build and start
docker compose logs -f scadabr        # follow logs
docker compose restart scadabr        # restart
docker compose down                   # stop (data kept)
docker compose down -v                # stop and DELETE all data
docker compose exec scadabr ls -l /dev/ttyUSB0   # check the serial device
```

## Troubleshooting

- **`/dev/ttyUSB0` not in the port list.** Run
  `docker compose exec scadabr ls -l /dev/ttyUSB0`. If it is missing, check the
  logs for the `Serial bridge` line. You can also type the port name by hand in the
  data source.
- **Bridge never shows `client connected`.**
  - Check that `com2tcp.py` is running.
  - Check the firewall rule.
  - Test from the container:
    `docker compose exec scadabr bash -c "echo > /dev/tcp/host.docker.internal/7000 && echo ok"`.
- **`could not open port COM1` in the bridge.** Another program (or a second bridge)
  has the port open. Close it.
- **Modbus timeouts with Option A.** Increase the data source timeout and retries.
  Check that the baud rate and parity in `com2tcp.py` match the device.
- **E-mail alarms fail with `SSLHandshakeException`.** This is a known Java 8 TLS
  issue in ScadaBR; see the upstream README.

## Notes

- The upstream `build.xml` needs SVN tooling, so the image compiles with `javac`
  directly. Three classes that the code needs (`br.org.scadabr.vo.permission`) live
  in the repo's `test/` folder and are included in the build.
- License: ScadaBR is GPL-3.0-or-later.
