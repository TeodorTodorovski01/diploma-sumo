from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from matplotlib.backends.backend_pdf import FigureCanvasPdf
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

AXES_HEIGHT = 0.86
TABLE_MAX_PAGE_HEIGHT = 0.16


def write_route_pdf(
    net,
    traversed_edge_ids: Sequence[str],
    output_path: Path,
    map_name: str,
    parameters: Mapping[str, str],
) -> Path:
    all_edges = net.getEdges()
    edge_shapes = {edge.getID(): edge.getShape() for edge in all_edges}
    road_shapes = [
        shape for shape in edge_shapes.values() if len(shape) >= 2
    ]
    route_shapes = [
        edge_shapes[edge_id]
        for edge_id in traversed_edge_ids
        if edge_id in edge_shapes and len(edge_shapes[edge_id]) >= 2
    ]
    if not route_shapes:
        raise ValueError("The ambulance route contains no drawable road segments.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    number = 1
    numbered_path = output_path.with_name(
        f"{output_path.stem}-{number}{output_path.suffix}"
    )
    while numbered_path.exists():
        number += 1
        numbered_path = output_path.with_name(
            f"{output_path.stem}-{number}{output_path.suffix}"
        )

    figure = Figure(figsize=(16, 11), facecolor="white")
    FigureCanvasPdf(figure)
    axes = figure.add_axes((0.025, 0.075, 0.95, AXES_HEIGHT))
    axes.add_collection(LineCollection(
        road_shapes,
        colors="#cbd2d9",
        linewidths=0.45,
        zorder=1,
    ))
    axes.add_collection(LineCollection(
        route_shapes,
        colors="#e31a1c",
        linewidths=2.2,
        zorder=2,
    ))
    axes.autoscale()
    axes.set_aspect("equal", adjustable="datalim")
    axes.margins(0.015)
    axes.set_axis_off()
    parameter_items = list(parameters.items())
    split_index = (len(parameter_items) + 1) // 2
    left_items = parameter_items[:split_index]
    right_items = parameter_items[split_index:]
    table_rows = [
        [
            *left_item,
            *(right_items[index] if index < len(right_items) else ("", "")),
        ]
        for index, left_item in enumerate(left_items)
    ]
    table = axes.table(
        cellText=table_rows,
        colLabels=("Setting", "Value", "Setting", "Value"),
        colWidths=(0.25, 0.25, 0.25, 0.25),
        bbox=(0.49, 0, 0.49, TABLE_MAX_PAGE_HEIGHT / AXES_HEIGHT),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(6)
    table.set_zorder(3)
    for (row, _), cell in table.get_celld().items():
        cell.set_facecolor("#e4e7ec" if row == 0 else "#ffffff")
        cell.set_edgecolor("#98a2b3")
        cell.set_alpha(0.94)
        if row == 0:
            cell.get_text().set_fontweight("bold")

    figure.suptitle(
        f"Ambulance route taken - {map_name}",
        fontsize=18,
        fontweight="bold",
        y=0.975,
    )
    figure.text(
        0.5,
        0.035,
        f"Red: roads traversed ({len(traversed_edge_ids)} recorded segments)  |  "
        "Map data (c) OpenStreetMap contributors",
        ha="center",
        fontsize=9,
        color="#475467",
    )
    figure.savefig(numbered_path, format="pdf")
    figure.clear()
    return numbered_path


def write_runtime_comparison_pdf(
    output_path: Path,
    elapsed_by_map: Mapping[str, float],
    ambulance_trip_times: Mapping[str, str],
    scenario: Mapping[str, str],
) -> Path:
    skopje_seconds = elapsed_by_map["skopje"]
    skopjelite_seconds = elapsed_by_map["skopjelite"]
    saved_seconds = skopje_seconds - skopjelite_seconds
    saved_percent = saved_seconds / skopje_seconds * 100

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure = Figure(figsize=(11, 8.5), facecolor="white")
    FigureCanvasPdf(figure)
    axes = figure.add_axes((0.08, 0.24, 0.84, 0.48))
    axes.set_axis_off()
    table = axes.table(
        cellText=[
            [
                "Whole-run wall time",
                f"{skopje_seconds:.2f} s",
                f"{skopjelite_seconds:.2f} s",
            ],
            [
                "Ambulance route time",
                ambulance_trip_times["skopje"],
                ambulance_trip_times["skopjelite"],
            ],
            ["Time saved", "-", f"{saved_seconds:.2f} s"],
            ["Time reduction", "-", f"{saved_percent:.1f}%"],
        ],
        colLabels=("Measure", "Skopje", "Skopje Lite"),
        colWidths=(0.44, 0.28, 0.28),
        bbox=(0, 0, 1, 1),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    for (row, _), cell in table.get_celld().items():
        cell.set_facecolor("#e4e7ec" if row == 0 else "#ffffff")
        cell.set_edgecolor("#98a2b3")
        if row == 0:
            cell.get_text().set_fontweight("bold")

    figure.suptitle(
        "Skopje vs Skopje Lite - runtime comparison",
        fontsize=18,
        fontweight="bold",
        y=0.93,
    )
    scenario_text = "  |  ".join(
        f"{name}: {value}" for name, value in scenario.items()
    )
    figure.text(0.5, 0.78, scenario_text, ha="center", fontsize=11)
    figure.text(
        0.5,
        0.12,
        "Both runs used the same scenario settings and seed. "
        "Whole-run time includes route generation, SUMO simulation, "
        "and each run's route PDF generation. Ambulance route time is "
        "simulation time. A negative saving means Skopje Lite took longer.",
        ha="center",
        va="center",
        wrap=True,
        fontsize=10,
        color="#475467",
    )
    figure.text(
        0.5,
        0.045,
        f"Report created: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        ha="center",
        fontsize=9,
        color="#475467",
    )
    figure.savefig(output_path, format="pdf")
    figure.clear()
    return output_path
