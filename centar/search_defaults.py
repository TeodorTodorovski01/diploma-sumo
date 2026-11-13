import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

DEFAULTS_FILE = Path(__file__).with_name("search_defaults.json")


@dataclass(frozen=True)
class SearchDefaults:
    search_algorithm: Literal["dijkstra", "astar"]
    replan_interval: float
    traffic_light_penalty: float | None
    astar_heuristic_weight: float


def load_search_defaults(path: Path = DEFAULTS_FILE) -> SearchDefaults:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError(f"Search defaults in {path} must be a JSON object.")

    algorithm = values.get("search_algorithm")
    if algorithm not in ("dijkstra", "astar"):
        raise ValueError(
            f"Invalid search_algorithm in {path}: expected 'dijkstra' or 'astar'."
        )

    replan_interval = values.get("replan_interval")
    if (
        isinstance(replan_interval, bool)
        or not isinstance(replan_interval, (int, float))
        or not math.isfinite(replan_interval)
        or replan_interval <= 0
    ):
        raise ValueError(f"Invalid replan_interval in {path}.")

    traffic_light_penalty = values.get("traffic_light_penalty")
    if traffic_light_penalty is not None and (
        isinstance(traffic_light_penalty, bool)
        or not isinstance(traffic_light_penalty, (int, float))
        or not math.isfinite(traffic_light_penalty)
        or traffic_light_penalty < 0
    ):
        raise ValueError(f"Invalid traffic_light_penalty in {path}.")

    astar_heuristic_weight = values.get("astar_heuristic_weight")
    if (
        isinstance(astar_heuristic_weight, bool)
        or not isinstance(astar_heuristic_weight, (int, float))
        or not math.isfinite(astar_heuristic_weight)
        or astar_heuristic_weight < 0
    ):
        raise ValueError(f"Invalid astar_heuristic_weight in {path}.")

    return SearchDefaults(
        search_algorithm=algorithm,
        replan_interval=float(replan_interval),
        traffic_light_penalty=(
            float(traffic_light_penalty)
            if traffic_light_penalty is not None else None
        ),
        astar_heuristic_weight=float(astar_heuristic_weight),
    )


def save_search_defaults(defaults: SearchDefaults, path: Path = DEFAULTS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(asdict(defaults), indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
