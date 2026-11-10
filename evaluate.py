
import csv
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
GRAPHS_DIR = BASE_DIR / "graphs"

INPUT_FILE = RESULTS_DIR / "experiment_results.csv"
SUMMARY_FILE = RESULTS_DIR / "comparison_summary.csv"

METRICS = {
    "latency_ms": ("Average Latency", "Milliseconds"),
    "throughput_mbps": ("Average Throughput", "Mbps"),
    "packet_loss_percent": ("Packet Loss", "Percent"),
    "recovery_time_s": ("Recovery Time", "Seconds"),
    "utilization_percent": ("Link Utilisation", "Percent")
}

SCENARIOS = ["static", "dynamic"]


def create_template():
    RESULTS_DIR.mkdir(exist_ok=True)
    GRAPHS_DIR.mkdir(exist_ok=True)

    if not INPUT_FILE.exists():
        with open(INPUT_FILE, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                "scenario",
                "latency_ms",
                "throughput_mbps",
                "packet_loss_percent",
                "recovery_time_s",
                "utilization_percent"
            ])

        print("Created experiment_results.csv template.")


def load_results():
    measurements = defaultdict(list)

    with open(INPUT_FILE, newline="") as file:
        reader = csv.DictReader(file)

        for row_number, row in enumerate(reader, start=2):
            scenario = row.get("scenario", "").strip().lower()

            if scenario not in SCENARIOS:
                print(f"Skipping row {row_number}: invalid scenario.")
                continue

            for metric in METRICS:
                value = row.get(metric, "").strip()

                if not value:
                    continue

                try:
                    number = float(value)

                    if number < 0:
                        raise ValueError

                    measurements[(scenario, metric)].append(number)

                except ValueError:
                    print(f"Skipping invalid {metric} in row {row_number}.")

    return measurements


def calculate_averages(measurements):
    averages = {}

    for scenario in SCENARIOS:
        for metric in METRICS:
            values = measurements.get((scenario, metric), [])

            if values:
                averages[(scenario, metric)] = sum(values) / len(values)

    return averages


def save_summary(averages, measurements):
    with open(SUMMARY_FILE, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "scenario",
            "metric",
            "average_value",
            "number_of_trials"
        ])

        for scenario in SCENARIOS:
            for metric in METRICS:
                key = (scenario, metric)

                if key in averages:
                    writer.writerow([
                        scenario,
                        metric,
                        round(averages[key], 3),
                        len(measurements[key])
                    ])


def generate_graphs(averages):
    GRAPHS_DIR.mkdir(exist_ok=True)

    for metric, details in METRICS.items():
        title, unit = details

        # A fair comparison requires both scenarios.
        keys = [(scenario, metric) for scenario in SCENARIOS]

        if not all(key in averages for key in keys):
            print(f"Skipping {metric}: both static and dynamic data required.")
            continue

        values = [averages[key] for key in keys]

        plt.figure(figsize=(7, 5))
        plt.bar(["Static", "Dynamic"], values)
        plt.title(f"Static vs Dynamic Routing: {title}")
        plt.ylabel(unit)
        plt.xlabel("Routing Method")
        plt.tight_layout()

        output_file = GRAPHS_DIR / f"{metric}.png"
        plt.savefig(output_file, dpi=300)
        plt.close()

        print(f"Graph saved: {output_file}")


def main():
    create_template()

    measurements = load_results()

    if not measurements:
        print("No experiment measurements found.")
        print(f"Add actual results to: {INPUT_FILE}")
        return

    averages = calculate_averages(measurements)

    save_summary(averages, measurements)
    generate_graphs(averages)

    print("\nPERFORMANCE COMPARISON")
    print("-" * 65)

    for metric, details in METRICS.items():
        print(f"\n{details[0]} ({details[1]}):")

        for scenario in SCENARIOS:
            key = (scenario, metric)

            if key in averages:
                print(f"  {scenario.capitalize()}: {averages[key]:.3f}")
            else:
                print(f"  {scenario.capitalize()}: No data")

    print("\nSummary saved:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
