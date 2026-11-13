from pathlib import Path
from typing import Sequence

from matplotlib.backends.backend_pdf import FigureCanvasPdf
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure


def write_route_pdf(
    net,
    traversed_edge_ids: Sequence[str],
    output_path: Path,
    map_name: str,
) -> None:
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
    figure = Figure(figsize=(16, 11), facecolor="white")
    FigureCanvasPdf(figure)
    axes = figure.add_axes((0.025, 0.075, 0.95, 0.86))
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
    figure.savefig(output_path, format="pdf")
    figure.clear()
