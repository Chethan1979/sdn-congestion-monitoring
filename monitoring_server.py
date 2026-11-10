
import csv
import json
import socket
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Load network configuration
with open(BASE_DIR / "network_config.json", "r") as file:
    config = json.load(file)

server_config = config["endpoints"]["monitoring_server"]
HOST = server_config["bind_host"]
PORT = server_config["telemetry_port"]

# Load congestion thresholds
with open(BASE_DIR / "thresholds.json", "r") as file:
    threshold_config = json.load(file)

thresholds = threshold_config["thresholds"]

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

CSV_FILE = LOG_DIR / "telemetry.csv"
ALERT_FILE = BASE_DIR / threshold_config["alert_settings"]["log_file"]

hosts = {}
last_alert_levels = {}


def classify_utilization(value):
    if value is None:
        return "NO LINK DATA"

    if value >= thresholds["critical"]:
        return "CRITICAL"
    elif value >= thresholds["high"]:
        return "HIGH"
    elif value >= thresholds["warning"]:
        return "WARNING"
    return "NORMAL"


def log_telemetry(data):
    file_exists = CSV_FILE.exists()

    with open(CSV_FILE, "a", newline="") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "received_at", "host_id", "timestamp",
                "cpu_percent", "synthetic_load",
                "packets_sent", "packets_recv",
                "bytes_sent", "bytes_recv",
                "link_utilization_percent"
            ])

        load = data.get("load", {})
        traffic = data.get("traffic", {})

        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            data["host_id"],
            data.get("timestamp"),
            load.get("cpu_percent"),
            load.get("synthetic_load"),
            traffic.get("packets_sent"),
            traffic.get("packets_recv"),
            traffic.get("bytes_sent"),
            traffic.get("bytes_recv"),
            data.get("link_utilization_percent")
        ])


def check_alert(host_id, utilization):
    if not threshold_config["alert_settings"]["enabled"]:
        return

    level = classify_utilization(utilization)

    if level in ("NO LINK DATA", "NORMAL"):
        last_alert_levels[host_id] = level
        return

    if last_alert_levels.get(host_id) != level:
        message = (
            f"{datetime.now().isoformat(timespec='seconds')} | "
            f"HOST: {host_id} | "
            f"UTILIZATION: {utilization:.2f}% | "
            f"STATUS: {level}"
        )

        print("\n[CONGESTION ALERT]", message)

        with open(ALERT_FILE, "a") as file:
            file.write(message + "\n")

    last_alert_levels[host_id] = level


def display_dashboard():
    print("\033[2J\033[H", end="")
    print("=" * 90)
    print("                 HOST TRAFFIC MONITORING DASHBOARD")
    print("=" * 90)
    print(
        f"{'HOST':<10}{'CPU %':<12}{'SYNTHETIC':<14}"
        f"{'PACKETS SENT':<16}{'PACKETS RECV':<16}"
        f"{'LINK UTIL %':<14}{'STATUS'}"
    )
    print("-" * 90)

    if not hosts:
        print("Waiting for telemetry from hosts...")
    else:
        for host_id in sorted(hosts):
            data = hosts[host_id]
            load = data.get("load", {})
            traffic = data.get("traffic", {})
            utilization = data.get("link_utilization_percent")

            cpu = load.get("cpu_percent", 0)
            synthetic = load.get("synthetic_load", 0)
            sent = traffic.get("packets_sent", 0)
            received = traffic.get("packets_recv", 0)

            util_display = (
                f"{utilization:.2f}" if isinstance(utilization, (int, float))
                else "--"
            )

            status = classify_utilization(utilization)

            print(
                f"{host_id:<10}{cpu:<12.2f}{synthetic:<14.2f}"
                f"{sent:<16}{received:<16}"
                f"{util_display:<14}{status}"
            )

    print("-" * 90)
    print(f"Telemetry port: UDP {PORT}")
    print(f"Last dashboard update: {datetime.now().strftime('%H:%M:%S')}")
    print("Press Ctrl+C to stop the server.")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, PORT))
    server.settimeout(1.0)

    print(f"Monitoring server listening on {HOST}:{PORT}")

    last_dashboard_update = 0

    try:
        while True:
            try:
                raw_data, address = server.recvfrom(65535)

                data = json.loads(raw_data.decode("utf-8"))

                if data.get("type") != "host_telemetry":
                    continue

                host_id = data.get("host_id")

                if not host_id:
                    continue

                if not isinstance(data.get("load", {}), dict):
                    continue

                if not isinstance(data.get("traffic", {}), dict):
                    continue

                hosts[host_id] = data

                log_telemetry(data)
                check_alert(
                    host_id,
                    data.get("link_utilization_percent")
                )

            except socket.timeout:
                pass
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as error:
                print("\nInvalid telemetry received:", error)

            if time.time() - last_dashboard_update >= 2:
                display_dashboard()
                last_dashboard_update = time.time()

    except KeyboardInterrupt:
        print("\nMonitoring server stopped.")

    finally:
        server.close()


if __name__ == "__main__":
    main()
