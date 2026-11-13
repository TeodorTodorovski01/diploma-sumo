from collections.abc import Callable, Iterable, Mapping
from typing import TypeAlias

EdgeTrafficMetric: TypeAlias = tuple[float, float]


def collect_smart_city_metrics(
    edge_ids: Iterable[str],
    previous: Mapping[str, EdgeTrafficMetric],
    get_occupancy: Callable[[str], float],
    get_waiting_time: Callable[[str], float],
) -> dict[str, EdgeTrafficMetric]:
    """Keep each edge's peak sampled occupancy and summed vehicle waiting time."""
    metrics = dict(previous)
    for edge_id in edge_ids:
        occupancy = get_occupancy(edge_id)
        waiting_time = get_waiting_time(edge_id)
        previous_occupancy, previous_waiting_time = metrics.get(
            edge_id, (0.0, 0.0)
        )
        metrics[edge_id] = (
            max(previous_occupancy, occupancy),
            max(previous_waiting_time, waiting_time),
        )
    return metrics
