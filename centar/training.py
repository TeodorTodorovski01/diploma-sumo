"""Tune ambulance routing defaults with finite-difference SPSA."""

import argparse
import csv
import hashlib
import json
import math
import random
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from matplotlib.backends.backend_pdf import FigureCanvasPdf
from matplotlib.figure import Figure

from search_defaults import SearchDefaults, load_search_defaults, save_search_defaults

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_SCRIPT = Path(__file__).with_name("scenario.py")
PARAMETER_BOUNDS = {
    "replan_interval": (5.0, 60.0),
    "traffic_light_penalty": (0.0, 30.0),
    "astar_heuristic_weight": (0.5, 2.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Tune ambulance search settings on Skopje Lite using "
            "simulation trip time as the objective."
        )
    )
    parser.add_argument(
        "--search-algorithm",
        choices=("dijkstra", "astar"),
        default="astar",
        help="algorithm to tune (default: astar)",
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument(
        "--alpha", "--learning-rate", "--a", dest="alpha",
        type=float, default=0.05,
        help="gradient step size / learning rate (default: 0.05)",
    )
    parser.add_argument(
        "--perturbation", "--c", dest="perturbation", type=float, default=0.1,
        help="initial SPSA perturbation size (c)",
    )
    parser.add_argument(
        "--alpha-exponent", type=float, default=0.602,
        help="SPSA step-size decay exponent (default: 0.602)",
    )
    parser.add_argument(
        "--gamma", type=float, default=0.101,
        help="SPSA perturbation decay exponent (default: 0.101)",
    )
    parser.add_argument("--vehicles", type=int, default=100)
    parser.add_argument("--duration", type=float, default=900)
    parser.add_argument("--ambulance-depart", type=float, default=120)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--ambulance-from-coordinates",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        default=(41.976343, 21.549497),
    )
    parser.add_argument(
        "--ambulance-to-coordinates",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        default=(42.006512, 21.402385),
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "skopje" / "scenario-output" / "training"),
    )
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="report the best values without changing search_defaults.json",
    )
    options = parser.parse_args()
    if options.iterations <= 0:
        parser.error("--iterations must be greater than zero")
    if not math.isfinite(options.alpha) or options.alpha <= 0:
        parser.error("--alpha must be finite and greater than zero")
    if not math.isfinite(options.perturbation) or not 0 < options.perturbation <= 0.5:
        parser.error("--perturbation must be greater than zero and at most 0.5")
    if (
        not math.isfinite(options.alpha_exponent)
        or not 0.5 < options.alpha_exponent <= 1
    ):
        parser.error("--alpha-exponent must be greater than 0.5 and at most 1")
    if not math.isfinite(options.gamma) or not 0 < options.gamma <= 0.5:
        parser.error("--gamma must be greater than zero and at most 0.5")
    if options.vehicles <= 0:
        parser.error("--vehicles must be greater than zero")
    if not math.isfinite(options.ambulance_depart) or options.ambulance_depart < 0:
        parser.error("--ambulance-depart must be zero or greater")
    if (
        not math.isfinite(options.duration)
        or options.duration <= options.ambulance_depart
    ):
        parser.error("--duration must exceed --ambulance-depart")
    if any(
        not math.isfinite(value)
        for value in (*options.ambulance_from_coordinates,
                      *options.ambulance_to_coordinates)
    ):
        parser.error("Ambulance coordinates must be finite values")
    return options


def clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def normalize(parameters: dict[str, float], names: list[str]) -> list[float]:
    return [
        (parameters[name] - PARAMETER_BOUNDS[name][0])
        / (PARAMETER_BOUNDS[name][1] - PARAMETER_BOUNDS[name][0])
        for name in names
    ]


def denormalize(values: list[float], names: list[str]) -> dict[str, float]:
    return {
        name: PARAMETER_BOUNDS[name][0]
        + clamp(value) * (PARAMETER_BOUNDS[name][1] - PARAMETER_BOUNDS[name][0])
        for name, value in zip(names, values)
    }


def read_trip_time(tripinfo_file: Path) -> float | None:
    with tripinfo_file.open("rb") as tripinfo:
        for _, entry in ET.iterparse(tripinfo, events=("end",)):
            if entry.tag == "tripinfo" and entry.get("id") == "amb0":
                duration = entry.get("duration")
                if duration is None:
                    return None
                return float(duration)
    return None


def scenario_signature(options: argparse.Namespace) -> dict[str, object]:
    network_file = REPO_ROOT / "skopje" / "skopjelite.net.xml"
    network_hash = hashlib.sha256()
    with network_file.open("rb") as network:
        for chunk in iter(lambda: network.read(1024 * 1024), b""):
            network_hash.update(chunk)
    return {
        "training_map": "skopjelite",
        "network_sha256": network_hash.hexdigest(),
        "search_algorithm": options.search_algorithm,
        "vehicles": options.vehicles,
        "duration": float(options.duration),
        "ambulance_depart": float(options.ambulance_depart),
        "ambulance_from_coordinates": [
            float(value) for value in options.ambulance_from_coordinates
        ],
        "ambulance_to_coordinates": [
            float(value) for value in options.ambulance_to_coordinates
        ],
        "seed": options.seed,
        "accident_probability": 0,
        "preempt": True,
        "green_seconds": 25,
        "red_seconds": 25,
    }


def load_best_checkpoint(
    path: Path,
    signature: dict[str, object],
) -> dict[str, object] | None:
    if not path.exists():
        return None
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(checkpoint, dict) or checkpoint.get("scenario") != signature:
        raise ValueError(f"Training checkpoint does not match its profile: {path}")
    best = checkpoint.get("best_result")
    if not isinstance(best, dict) or not isinstance(best.get("parameters"), dict):
        raise ValueError(f"Invalid best-result data in training checkpoint: {path}")
    trip_time = best.get("ambulance_trip_time_seconds")
    if (
        isinstance(trip_time, bool)
        or not isinstance(trip_time, (int, float))
        or not math.isfinite(trip_time)
        or trip_time < 0
    ):
        raise ValueError(f"Invalid trip time in training checkpoint: {path}")
    return best


def save_best_checkpoint(
    path: Path,
    signature: dict[str, object],
    best_result: dict[str, object],
    created_at: str,
) -> None:
    checkpoint = {
        "scenario": signature,
        "best_result": best_result,
        "updated_at": created_at,
    }
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(checkpoint, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def display_number(value: float | None) -> str:
    return "automatic" if value is None else f"{value:g}"


def write_training_artifacts(
    output_dir: Path,
    initial_defaults: SearchDefaults,
    learned_defaults: SearchDefaults,
    evaluations: list[dict[str, object]],
    applied: bool,
    seed: int,
    optimizer_settings: dict[str, float],
    previous_best_trip_time: float | None,
    best_trip_time: float | None,
) -> tuple[Path, Path, str]:
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    report_path = output_dir / "training-report.pdf"
    csv_path = output_dir / "training-results.csv"

    evaluation_numbers = [
        int(result["evaluation"]) for result in evaluations
    ]
    objectives = [
        float(result["objective_seconds"]) for result in evaluations
    ]
    best_so_far = [
        min(objectives[:index + 1])
        for index in range(len(objectives))
    ]

    figure = Figure(figsize=(11, 8.5), facecolor="white")
    FigureCanvasPdf(figure)
    axes = figure.add_axes((0.10, 0.57, 0.82, 0.29))
    axes.plot(
        evaluation_numbers,
        objectives,
        marker="o",
        color="#667085",
        label="Evaluation objective",
    )
    axes.plot(
        evaluation_numbers,
        best_so_far,
        marker=".",
        color="#175cd3",
        label="Best this run",
    )
    if previous_best_trip_time is not None:
        axes.axhline(
            previous_best_trip_time,
            color="#d92d20",
            linestyle="--",
            label="Best before this run",
        )
    axes.set_title("Ambulance trip-time objective")
    axes.set_xlabel("Evaluation")
    axes.set_ylabel("Objective (simulation seconds)")
    axes.grid(True, alpha=0.25)
    axes.legend()

    current_best_trip_time = min(
        (
            float(result["ambulance_trip_time_seconds"])
            for result in evaluations
            if result["ambulance_trip_time_seconds"] is not None
        ),
        default=None,
    )
    table_rows = [
        [
            "Search algorithm",
            initial_defaults.search_algorithm,
            learned_defaults.search_algorithm,
            "Yes" if applied else "No",
        ],
        [
            "Replan interval (s)",
            f"{initial_defaults.replan_interval:g}",
            f"{learned_defaults.replan_interval:g}",
            "Yes" if applied else "No",
        ],
        [
            "Traffic-light penalty (s)",
            display_number(initial_defaults.traffic_light_penalty),
            display_number(learned_defaults.traffic_light_penalty),
            "Yes" if applied else "No",
        ],
        [
            "A* heuristic weight",
            f"{initial_defaults.astar_heuristic_weight:g}",
            f"{learned_defaults.astar_heuristic_weight:g}",
            "Yes" if applied else "No",
        ],
        [
            "Best trip this run (s)",
            "-",
            f"{current_best_trip_time:.1f}"
            if current_best_trip_time is not None
            else "Not completed",
            "-",
        ],
        [
            "Best before this run (s)",
            "-",
            f"{previous_best_trip_time:.1f}"
            if previous_best_trip_time is not None else "None",
            "-",
        ],
        [
            "Best across runs (s)",
            "-",
            f"{best_trip_time:.1f}" if best_trip_time is not None
            else "Not completed",
            "-",
        ],
        ["Training seed", "-", str(seed), "-"],
    ]
    table_axes = figure.add_axes((0.05, 0.14, 0.90, 0.34))
    table_axes.set_axis_off()
    table = table_axes.table(
        cellText=table_rows,
        colLabels=("Setting", "Previous default", "Training result", "Applied"),
        colWidths=(0.31, 0.25, 0.25, 0.19),
        bbox=(0, 0, 1, 1),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row, _), cell in table.get_celld().items():
        cell.set_facecolor("#e4e7ec" if row == 0 else "#ffffff")
        cell.set_edgecolor("#98a2b3")
        if row == 0:
            cell.get_text().set_fontweight("bold")

    figure.suptitle(
        "Skopje Lite search-parameter training",
        fontsize=17,
        fontweight="bold",
        y=0.96,
    )
    figure.text(
        0.5,
        0.89,
        "SPSA settings: "
        f"alpha={optimizer_settings['alpha']:g}, "
        f"alpha exponent={optimizer_settings['alpha_exponent']:g}, "
        f"c={optimizer_settings['perturbation']:g}, "
        f"gamma={optimizer_settings['gamma']:g}",
        ha="center",
        fontsize=9,
        color="#475467",
    )
    figure.text(
        0.5,
        0.08,
        f"Defaults applied: {'yes' if applied else 'no'}  |  "
        f"Created: {created_at}",
        ha="center",
        fontsize=9,
        color="#475467",
    )
    figure.savefig(report_path, format="pdf")
    figure.clear()

    with csv_path.open("w", newline="", encoding="utf-8") as results_file:
        writer = csv.DictWriter(
            results_file,
            fieldnames=(
                "evaluation",
                "objective_seconds",
                "ambulance_trip_time_seconds",
                "replan_interval",
                "traffic_light_penalty",
                "astar_heuristic_weight",
            ),
        )
        writer.writeheader()
        for result in evaluations:
            row = {
                key: result[key]
                for key in (
                    "evaluation",
                    "objective_seconds",
                    "ambulance_trip_time_seconds",
                )
            }
            row.update(result["parameters"])
            writer.writerow(row)
    return report_path, csv_path, created_at


def run_evaluation(
    options: argparse.Namespace,
    parameters: dict[str, float],
    evaluation: int,
    output_dir: Path,
) -> dict[str, object]:
    evaluation_dir = output_dir / f"evaluation-{evaluation:03d}"
    command = [
        sys.executable,
        str(SCENARIO_SCRIPT),
        "--map",
        "skopjelite",
        "--vehicles",
        str(options.vehicles),
        "--duration",
        str(options.duration),
        "--ambulance-depart",
        str(options.ambulance_depart),
        "--ambulance-from-coordinates",
        *(str(value) for value in options.ambulance_from_coordinates),
        "--ambulance-to-coordinates",
        *(str(value) for value in options.ambulance_to_coordinates),
        "--accident-probability",
        "0",
        "--seed",
        str(options.seed),
        "--search-algorithm",
        options.search_algorithm,
        "--replan-interval",
        str(parameters["replan_interval"]),
        "--traffic-light-penalty",
        str(parameters["traffic_light_penalty"]),
        "--astar-heuristic-weight",
        str(parameters["astar_heuristic_weight"]),
        "--output-dir",
        str(evaluation_dir),
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)

    trip_time = read_trip_time(evaluation_dir / "tripinfo.xml")
    max_trip_time = options.duration - options.ambulance_depart
    objective = (
        trip_time
        if trip_time is not None
        else max_trip_time + max(300.0, max_trip_time)
    )
    return {
        "evaluation": evaluation,
        "parameters": parameters,
        "ambulance_trip_time_seconds": trip_time,
        "objective_seconds": objective,
    }


def optimize(options: argparse.Namespace) -> None:
    defaults = load_search_defaults()
    initial_defaults = defaults
    names = ["replan_interval", "traffic_light_penalty"]
    if options.search_algorithm == "astar":
        names.append("astar_heuristic_weight")

    output_dir = Path(options.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    signature = scenario_signature(options)
    profile_id = hashlib.sha256(
        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12]
    checkpoint_path = output_dir / f"training-best-{profile_id}.json"
    previous_best = load_best_checkpoint(checkpoint_path, signature)

    parameters = {
        "replan_interval": defaults.replan_interval,
        "traffic_light_penalty": (
            defaults.traffic_light_penalty
            if defaults.traffic_light_penalty is not None else 0.0
        ),
        "astar_heuristic_weight": defaults.astar_heuristic_weight,
    }
    if previous_best is not None:
        previous_parameters = previous_best["parameters"]
        if not isinstance(previous_parameters, dict):
            raise ValueError(f"Invalid parameter data in {checkpoint_path}")
        for name in parameters:
            value = previous_parameters.get(name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(
                    f"Invalid {name} value in training checkpoint: "
                    f"{checkpoint_path}"
                )
            parameters[name] = float(value)
        print(
            "Loaded previous best trip: "
            f"{float(previous_best['ambulance_trip_time_seconds']):.1f} s "
            f"from {checkpoint_path}"
        )
    center = [clamp(value) for value in normalize(parameters, names)]
    randomizer = random.Random(options.seed)
    evaluations: list[dict[str, object]] = []
    evaluation_number = 0

    def evaluate(vector: list[float]) -> dict[str, object]:
        nonlocal evaluation_number
        candidate = denormalize(vector, names)
        full_parameters = {**parameters, **candidate}
        result = run_evaluation(
            options, full_parameters, evaluation_number, output_dir
        )
        evaluation_number += 1
        evaluations.append(result)
        trip_time = result["ambulance_trip_time_seconds"]
        report_time = (
            f"{trip_time:.1f} s" if isinstance(trip_time, float)
            else "incomplete"
        )
        print(
            f"Evaluation {result['evaluation']}: "
            f"trip {report_time}; objective "
            f"{result['objective_seconds']:.1f} s; "
            f"parameters {candidate}"
        )
        return result

    current_best = evaluate(center)
    for iteration in range(options.iterations):
        perturbation = (
            options.perturbation / (iteration + 1) ** options.gamma
        )
        direction = [
            randomizer.choice((-1.0, 1.0))
            for _ in names
        ]
        plus = [clamp(value + perturbation * sign)
                for value, sign in zip(center, direction)]
        minus = [clamp(value - perturbation * sign)
                 for value, sign in zip(center, direction)]
        positive_result = evaluate(plus)
        negative_result = evaluate(minus)
        positive_score = float(positive_result["objective_seconds"])
        negative_score = float(negative_result["objective_seconds"])
        best_score = float(current_best["objective_seconds"])
        if positive_score < best_score:
            current_best = positive_result
        if negative_score < float(current_best["objective_seconds"]):
            current_best = negative_result

        rate = options.alpha / (iteration + 10) ** options.alpha_exponent
        gradient = [
            max(
                -10.0,
                min(
                    10.0,
                    (positive_score - negative_score)
                    / (2 * perturbation * sign),
                ),
            )
            for sign in direction
        ]
        center = [
            clamp(value - rate * slope)
            for value, slope in zip(center, gradient)
        ]

    final_result = evaluate(center)
    if float(final_result["objective_seconds"]) < float(
        current_best["objective_seconds"]
    ):
        current_best = final_result

    best = current_best
    if previous_best is not None and float(
        previous_best["objective_seconds"]
    ) <= float(current_best["objective_seconds"]):
        best = previous_best

    best_parameters = best["parameters"]
    if not isinstance(best_parameters, dict):
        raise TypeError("Best training result has invalid parameter data.")
    current_best_trip_time = current_best["ambulance_trip_time_seconds"]
    previous_best_trip_time = (
        float(previous_best["ambulance_trip_time_seconds"])
        if previous_best is not None else None
    )
    best_trip_time = (
        float(best["ambulance_trip_time_seconds"])
        if best["ambulance_trip_time_seconds"] is not None else None
    )
    has_completed_trip = previous_best is not None or any(
        result["ambulance_trip_time_seconds"] is not None
        for result in evaluations
    )
    apply_defaults = not options.no_apply and has_completed_trip
    learned_defaults = SearchDefaults(
        search_algorithm=options.search_algorithm,
        replan_interval=float(best_parameters["replan_interval"]),
        traffic_light_penalty=float(best_parameters["traffic_light_penalty"]),
        astar_heuristic_weight=float(best_parameters["astar_heuristic_weight"]),
    )
    if (
        current_best_trip_time is not None
        and (
            previous_best_trip_time is None
            or float(current_best_trip_time) < previous_best_trip_time
        )
    ):
        checkpoint_created_at = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        save_best_checkpoint(
            checkpoint_path,
            signature,
            current_best,
            checkpoint_created_at,
        )

    if apply_defaults:
        save_search_defaults(learned_defaults)

    report_path, csv_path, created_at = write_training_artifacts(
        output_dir,
        initial_defaults,
        learned_defaults,
        evaluations,
        apply_defaults,
        options.seed,
        {
            "alpha": options.alpha,
            "alpha_exponent": options.alpha_exponent,
            "perturbation": options.perturbation,
            "gamma": options.gamma,
        },
        previous_best_trip_time,
        best_trip_time,
    )
    report = {
        "training_map": "skopjelite",
        "scenario": signature,
        "objective": "minimize ambulance trip duration",
        "search_algorithm": options.search_algorithm,
        "seed": options.seed,
        "optimizer_settings": {
            "alpha": options.alpha,
            "alpha_exponent": options.alpha_exponent,
            "perturbation": options.perturbation,
            "gamma": options.gamma,
        },
        "created_at": created_at,
        "best_result": best,
        "current_run_best": current_best,
        "previous_best_result": previous_best,
        "best_checkpoint": str(checkpoint_path),
        "applied_to_defaults": apply_defaults,
        "evaluations": evaluations,
        "artifacts": {
            "pdf": str(report_path),
            "csv": str(csv_path),
        },
    }
    (output_dir / "training-results.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Best result: {best}")
    if best_trip_time is not None:
        print(f"Best trip across training runs: {best_trip_time:.1f} s")
    if checkpoint_path.exists():
        print(f"Persistent best checkpoint: {checkpoint_path}")
    print(f"Training report: {report_path}")
    print(f"Evaluation table: {csv_path}")
    if not has_completed_trip:
        print(
            "No ambulance trip completed; defaults were not updated. "
            "Increase --duration or adjust the start/destination."
        )
    elif options.no_apply:
        print("Defaults unchanged; rerun without --no-apply to apply them.")
    else:
        print(f"Updated defaults: {Path(__file__).with_name('search_defaults.json')}")


if __name__ == "__main__":
    optimize(parse_args())
