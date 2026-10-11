
#!/usr/bin/env python3

import argparse
import json
import socket
import time
from pathlib import Path


# Each Mininet host has a dedicated management IP.
MANAGEMENT_IPS = {
    "h1": "192.168.100.11",
    "h2": "192.168.100.12",
    "h3": "192.168.100.13",
    "h4": "192.168.100.14",
}

CONFIG_PATH = (
    Path(__file__).resolve().parent
    / "config"
    / "network_config.json"
)


def load_config():
    """Read the monitoring server address and port from JSON config."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    server_config = config["endpoints"]["monitoring_server"]

    server_ip = server_config["mgmt_ip"]
    server_port = int(server_config["telemetry_port"])

    return server_ip, server_port


def read_cpu_times():
    """Read aggregate CPU counters from the Linux VM."""

    try:
        with open("/proc/stat", "r", encoding="utf-8") as file:
            fields = file.readline().split()

        if not fields or fields[0] != "cpu":
            return None

        values = [int(value) for value in fields[1:]]

        total = sum(values)
        idle = values[3] + (
            values[4] if len(values) > 4 else 0
        )

        return total, idle

    except (OSError, ValueError, IndexError):
        return None


def calculate_cpu_percent(previous, current):
    """Calculate CPU usage between two samples."""

    if previous is None or current is None:
        return 0.0

    previous_total, previous_idle = previous
    current_total, current_idle = current

    total_difference = current_total - previous_total
    idle_difference = current_idle - previous_idle

    if total_difference <= 0:
        return 0.0

    busy_difference = total_difference - idle_difference

    return round(
        max(0.0, min(100.0, busy_difference / total_difference * 100)),
        1
    )


def drain_socket(sock, counters):
    """Count datagrams received by this agent's UDP socket."""

    while True:
        try:
            data, _address = sock.recvfrom(65535)
            counters["packets_recv"] += 1
            counters["bytes_recv"] += len(data)

        except BlockingIOError:
            break

        except OSError as error:
            print(f"UDP receive error: {error}")
            break


def run_agent(host_id, synthetic_load, interval):

    if host_id not in MANAGEMENT_IPS:
        raise ValueError("Host must be h1, h2, h3, or h4.")

    if not 0.0 <= synthetic_load <= 1.0:
        raise ValueError("Synthetic load must be between 0.0 and 1.0.")

    server_ip, server_port = load_config()
    source_ip = MANAGEMENT_IPS[host_id]

    # A single UDP socket sends telemetry and counts any replies.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind to this host's management IP so telemetry uses eth1.
    sock.bind((source_ip, 0))
    sock.setblocking(False)

    counters = {
        "packets_sent": 0,
        "packets_recv": 0,
        "bytes_sent": 0,
        "bytes_recv": 0,
    }

    seq = 1
    previous_cpu = read_cpu_times()

    print(f"Telemetry agent started for {host_id}")
    print(f"Source IP: {source_ip}")
    print(f"Monitoring server: {server_ip}:{server_port}")
    print(f"Interval: {interval} second(s)")
    print(f"Synthetic load: {synthetic_load:.2f}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:

            current_cpu = read_cpu_times()
            cpu_percent = calculate_cpu_percent(
                previous_cpu, current_cpu
            )
            previous_cpu = current_cpu

            # Count any replies received since the previous sample.
            drain_socket(sock, counters)

            telemetry = {
                "version": "1.0",
                "type": "host_telemetry",
                "host_id": host_id,
                "timestamp": time.time(),
                "seq": seq,
                "load": {
                    "cpu_percent": cpu_percent,
                    "synthetic_load": synthetic_load,
                },
                "traffic": {
                    "packets_sent": counters["packets_sent"],
                    "packets_recv": counters["packets_recv"],
                    "bytes_sent": counters["bytes_sent"],
                    "bytes_recv": counters["bytes_recv"],
                },
            }

            data = json.dumps(
                telemetry, separators=(",", ":")
            ).encode("utf-8")

            # Person 2 requires every message to be under 1024 bytes.
            if len(data) >= 1024:
                print("ERROR: Telemetry message is too large.")
                time.sleep(interval)
                continue

            try:
                sent_bytes = sock.sendto(
                    data, (server_ip, server_port)
                )

                counters["packets_sent"] += 1
                counters["bytes_sent"] += sent_bytes

                print(data.decode("utf-8"))

            except OSError as error:
                print(f"UDP send failed: {error}")

            # Advance the sequence number for the next message.
            seq += 1

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\nTelemetry agent stopped for {host_id}.")

    finally:
        sock.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="UDP host telemetry agent for Mininet"
    )

    parser.add_argument(
        "--host",
        required=True,
        choices=["h1", "h2", "h3", "h4"],
        help="Mininet host ID"
    )

    parser.add_argument(
        "--synthetic-load",
        type=float,
        default=0.0,
        help="Application load from 0.0 to 1.0"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Telemetry interval in seconds"
    )

    args = parser.parse_args()

    if not 0.0 <= args.synthetic_load <= 1.0:
        parser.error("--synthetic-load must be between 0.0 and 1.0")

    if args.interval <= 0:
        parser.error("--interval must be greater than zero")

    try:
        run_agent(
            args.host,
            args.synthetic_load,
            args.interval
        )

    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
