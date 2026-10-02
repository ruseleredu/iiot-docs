"""
com2tcp.py - share a Windows serial port (e.g. COM1) over TCP so the ScadaBR
container can use it as /dev/ttyUSB0.

    pip install pyserial
    python com2tcp.py --port COM1 --baud 9600 --tcp-port 7000

Serial settings (baud, data bits, parity, stop bits) are applied HERE, on the
real port. Inside ScadaBR the device is a virtual tty, so whatever baud rate is
configured in the data source is ignored - keep them consistent anyway.

Only one TCP client (the container) is served at a time. If it disconnects the
bridge waits for it to come back; if the COM port disappears it retries.
"""
import argparse
import socket
import sys
import threading
import time

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial is missing - run:  pip install pyserial")

PARITY = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
          "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE}
STOPBITS = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}


def open_serial(args):
    while True:
        try:
            ser = serial.Serial(args.port, baudrate=args.baud, bytesize=args.bytesize,
                                parity=PARITY[args.parity], stopbits=STOPBITS[args.stopbits],
                                timeout=0.05, rtscts=args.rtscts, xonxoff=False)
            print(f"[serial] opened {args.port} {args.baud} {args.bytesize}{args.parity}{args.stopbits}", flush=True)
            return ser
        except serial.SerialException as e:
            print(f"[serial] cannot open {args.port}: {e} - retrying in 3 s", flush=True)
            time.sleep(3)


def serve(ser, conn, addr):
    print(f"[tcp] client connected from {addr[0]}:{addr[1]}", flush=True)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    stop = threading.Event()

    def serial_to_tcp():
        try:
            while not stop.is_set():
                data = ser.read(ser.in_waiting or 1)
                if data:
                    conn.sendall(data)
        except Exception as e:
            print(f"[serial->tcp] {e}", flush=True)
        stop.set()

    t = threading.Thread(target=serial_to_tcp, daemon=True)
    t.start()
    try:
        conn.settimeout(0.5)
        while not stop.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            ser.write(data)
    except Exception as e:
        print(f"[tcp->serial] {e}", flush=True)
    stop.set()
    t.join(1)
    conn.close()
    print("[tcp] client disconnected", flush=True)


def main():
    p = argparse.ArgumentParser(description="Serial port <-> TCP bridge for ScadaBR in Docker")
    p.add_argument("--port", default="COM1", help="serial port (default COM1)")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--bytesize", type=int, default=8, choices=[5, 6, 7, 8])
    p.add_argument("--parity", default="N", choices=list(PARITY))
    p.add_argument("--stopbits", default="1", choices=list(STOPBITS))
    p.add_argument("--rtscts", action="store_true", help="hardware flow control")
    p.add_argument("--bind", default="0.0.0.0", help="address to listen on (default all)")
    p.add_argument("--tcp-port", type=int, default=7000)
    args = p.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.bind, args.tcp_port))
    srv.listen(1)
    print(f"[tcp] listening on {args.bind}:{args.tcp_port}  (Ctrl+C to stop)", flush=True)

    ser = open_serial(args)
    try:
        while True:
            conn, addr = srv.accept()
            if not ser.is_open:
                ser = open_serial(args)
            ser.reset_input_buffer()
            serve(ser, conn, addr)
            try:
                ser.in_waiting  # still alive?
            except Exception:
                ser.close()
                ser = open_serial(args)
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        ser.close()
        srv.close()


if __name__ == "__main__":
    main()
