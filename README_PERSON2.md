# Person 2 – Monitoring Server, Anomaly Detection and Performance Evaluation

## Overview
This module monitors host telemetry, detects congestion conditions, generates alerts, and evaluates network performance.

## Files

- `monitoring_server.py` – UDP monitoring server that receives JSON telemetry from multiple hosts.
- `thresholds.json` – Configuration for congestion thresholds and alert settings.
- `evaluate.py` – Analyses experiment measurements and generates comparison graphs.
- `logs/telemetry.csv` – Stores received host telemetry.
- `logs/alerts.log` – Stores congestion alerts.
- `results/experiment_results.csv` – Stores static and dynamic network experiment measurements.
- `graphs/` – Stores generated performance comparison graphs.

## Congestion Thresholds

| Utilisation | Status |
|---|---|
| Below 60% | NORMAL |
| 60% to below 75% | WARNING |
| 75% to below 90% | HIGH |
| 90% or above | CRITICAL |

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
