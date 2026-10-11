# CN Project — Person 1: Mininet Topology + UDP Host Telemetry

**Status:** local implementation and testing complete for the current prototype; Ryu/monitoring-server integration is still pending.  
**Documentation date:** 10 October 2026.

## 1. Scope

Person 1 owns the Mininet topology, host-side management interfaces, UDP host telemetry agent, and local network/traffic tests. Person 2 owns the monitoring server and anomaly alerts. Person 3 owns the Ryu controller and controller statistics. This README describes Person 1's current local test setup and does not claim that the final end-to-end SDN behavior has already been integrated.

## 2. Files

```text
CN_Project/
├── topology.py
├── topology_data_plane_backup.py
├── udp_agent.py
├── udp_listener.py                 # temporary local test receiver
└── config/
    └── network_config.json
```

## 3. Topology

### Data plane

- Hosts: h1 `10.0.0.1/24`, h2 `10.0.0.2/24`, h3 `10.0.0.3/24`, h4 `10.0.0.4/24`.
- Switches: s1, s2, s3, configured for OpenFlow 1.3.
- Direct path: h1 → s1 → s3 → h4; s1–s3 is shaped to **5 Mbps**.
- Alternate path: h1 → s1 → s2 → s3 → h4; s1–s2 and s2–s3 are shaped to **100 Mbps** each.
- Port map:
  - s1 p1–h1, p2–h2, p3–s2, p4–s3.
  - s2 p1–h3, p2–s1, p3–s3.
  - s3 p1–h4, p2–s2, p3–s1.

### Management plane

A separate management bridge s4 connects host management interfaces and a temporary local test host called `mon`.

| Node | Management interface/IP |
|---|---|
| h1 | `h1-eth1` — `192.168.100.11/24` |
| h2 | `h2-eth1` — `192.168.100.12/24` |
| h3 | `h3-eth1` — `192.168.100.13/24` |
| h4 | `h4-eth1` — `192.168.100.14/24` |
| mon (temporary test endpoint) | `192.168.100.254/24` |

**Important:** `mon` is only a temporary local receiver. It is not Person 2's real monitoring server and does not act as an external gateway. Confirm real server reachability and route configuration during group integration.

## 4. Configuration

`config/network_config.json`:

```json
{
  "endpoints": {
    "monitoring_server": {
      "bind_host": "0.0.0.0",
      "mgmt_ip": "192.168.100.254",
      "telemetry_port": 9998,
      "stats_port": 9999
    }
  }
}
```

The telemetry agent reads `cfg["endpoints"]["monitoring_server"]["mgmt_ip"]` and `telemetry_port` from this file. Host telemetry is UDP port **9998**, one message per second. Controller statistics are expected on UDP port **9999** every two seconds, sent by Person 3's Ryu controller.

## 5. Host telemetry packet

The agent transmits JSON with:

- `version`: `"1.0"`
- `type`: `"host_telemetry"`
- `host_id`: h1–h4
- `timestamp`: Unix seconds (`time.time()`)
- `seq`: starts at 1 and increments per message
- `load.cpu_percent`: whole-VM CPU, informational only
- `load.synthetic_load`: 0.0 normally; set to 0.9 for overload demo test
- `traffic.packets_sent`, `packets_recv`, `bytes_sent`, `bytes_recv`: cumulative counters from the telemetry UDP socket itself

Messages are checked to remain below 1024 bytes. Because the counters belong to the telemetry socket, they do **not** represent total data-plane application traffic. In the local test the receiver sends no replies, so receive counters remain zero.

## 6. Run and test

### Start the topology

From Ubuntu/WSL in the project folder:

```bash
python3 -m py_compile topology.py udp_agent.py
sudo python3 topology.py
```

The current topology uses temporary standalone/STP switch settings for local tests. Wait for the `mininet>` prompt.

### Check data-plane connectivity and links

```text
pingall
h1 ping -c 4 10.0.0.4
links
```

During testing, the first `pingall` run showed transient packet loss, and a second run reached `0% dropped (12/12 received)`. h1-to-h4 ping returned 4/4 replies.

### Check shaping classes

```text
sh tc class show dev s1-eth4
sh tc class show dev s1-eth3
```

Observed output showed 5 Mbit on `s1-eth4` and 100 Mbit on `s1-eth3`.

### Start a temporary UDP listener

Create/keep `udp_listener.py` in the project folder. At the `mininet>` prompt:

```text
mon python3 -u udp_listener.py > /tmp/udp_listener.log 2>&1 &
mon cat /tmp/udp_listener.log
```

Expected startup line: `Listening for UDP telemetry on port 9998...`.

### Start one host agent

Use `--host=h1` with an equals sign in the Mininet CLI; passing `--host h1` may be rewritten by Mininet's command parser.

```text
h1 python3 -u udp_agent.py --host=h1
```

Stop with Ctrl+C. Repeat with `h2`, `h3`, and `h4`.

To inspect the listener for a source address:

```text
mon grep '192.168.100.11' /tmp/udp_listener.log
mon grep '192.168.100.12' /tmp/udp_listener.log
mon grep '192.168.100.13' /tmp/udp_listener.log
mon grep '192.168.100.14' /tmp/udp_listener.log
```

For a synthetic overload test:

```text
h1 python3 -u udp_agent.py --host=h1 --synthetic-load=0.9
```

Stop after several seconds with Ctrl+C. Confirm `synthetic_load` by checking the agent output or listener log. Person 2's real server must still be used to verify that the alert is actually raised.

### TCP throughput test

In the Mininet CLI:

```text
h4 iperf -s -p 5001 &
h1 iperf -c 10.0.0.4 -p 5001 -t 5
```

Observed preliminary throughput: about 93.9 Mbps when alternate links were available, and about 6.93 Mbps in a test where the two alternate inter-switch links were disabled. A later capture showed 4.82 Mbps for a direct-only run. Repeat the measurements during final controller-managed testing before reporting definitive benchmark numbers.

### Management-plane independence check

Temporarily disable data-plane inter-switch links:

```text
link s1 s2 down
link s2 s3 down
link s1 s3 down
h1 ping -c 3 192.168.100.254
h1 python3 -u udp_agent.py --host=h1
```

The local management ping succeeded with 0% loss and the listener showed newly received h1 telemetry while the data-plane links were down. Restore the links after testing:

```text
link s1 s2 up
link s2 s3 up
link s1 s3 up
links
```

Make sure the links are up before doing further data-plane tests.

### Exit/cleanup

```text
exit
```

From Ubuntu shell:

```bash
sudo mn -c
```

## 7. Observed local test results

| Test | Observed result |
|---|---|
| `pingall` | Second run: 0% dropped (12/12 received) |
| `h1` → `h4` ping | 4 received, 0% loss; average RTT reported 0.478 ms |
| HTB shaping classes | 5 Mbit direct class; 100 Mbit alternate class (inspected interfaces) |
| TCP throughput | 93.9 Mbps with alternate links available; 6.93 Mbps in a direct-only isolation run |
| Host telemetry | Receiver showed packets sourced from all four host management IPs |
| Synthetic load | Received packet had `synthetic_load = 0.9` |
| Data-plane link failure | Management ping and new h1 telemetry still worked with all three inter-switch links down |

These are local prototype results, not final integrated SDN benchmark results.

## 8. Required work before final submission

1. Verify current link state; restore all inter-switch links after failure tests.
2. Configure final Ryu connection and replace standalone/STP test forwarding with Person 3's controller-managed rules.
3. Confirm that `192.168.100.254` is the reachable real monitoring server from the team's run environment; test UDP 9998 against Person 2's server.
4. Confirm Person 2 raises an alert for `synthetic_load >= 0.85`.
5. Coordinate the rerouting command channel and exact commands `REROUTE h1 h4` / `DIRECT h1 h4` with Person 3.
6. Verify Ryu sends `controller_stats` to UDP 9999 using the field names Person 2 expects.
7. Repeat throughput/latency tests with controller-managed direct and alternate paths, and archive final evidence.

## 9. Warning interpretation

The `sch_htb: quantum of class 50001 is big. Consider r2q change.` warning appeared during Mininet startup. The topology still started and class queries showed the configured rates. It is a warning, not by itself proof of failure. Re-evaluate the shaping and performance during the final integrated test.
