import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "centar"))

from route_pdf import write_route_pdf
from smart_city import collect_smart_city_metrics


class SmartCityMetricsTests(unittest.TestCase):
    def test_collection_keeps_each_edges_peak_values(self) -> None:
        occupancy = {"edge-a": 18.0, "edge-b": 42.0}
        waiting = {"edge-a": 25.0, "edge-b": 8.0}
        previous = {"edge-a": (20.0, 10.0)}

        result = collect_smart_city_metrics(
            ("edge-a", "edge-b"),
            previous,
            occupancy.__getitem__,
            waiting.__getitem__,
        )

        self.assertEqual(
            result,
            {"edge-a": (20.0, 25.0), "edge-b": (42.0, 8.0)},
        )
        self.assertEqual(previous, {"edge-a": (20.0, 10.0)})


class RoutePdfTrafficHeatmapTests(unittest.TestCase):
    def test_writes_green_route_and_traffic_heatmap_pdf(self) -> None:
        edges = [
            SimpleNamespace(
                getID=lambda: "edge-a",
                getShape=lambda: [(0.0, 0.0), (1.0, 0.0)],
            ),
            SimpleNamespace(
                getID=lambda: "edge-b",
                getShape=lambda: [(1.0, 0.0), (2.0, 1.0)],
            ),
        ]
        network = SimpleNamespace(getEdges=lambda: edges)

        with tempfile.TemporaryDirectory() as directory:
            output = write_route_pdf(
                network,
                ["edge-a"],
                Path(directory) / "ambulance-route.pdf",
                "Test map",
                {"SmartCity samples": "3"},
                traffic_metrics={
                    "edge-a": (72.0, 35.0),
                    "edge-b": (14.0, 6.0),
                },
            )

            self.assertTrue(output.is_file())
            self.assertTrue(output.read_bytes().startswith(b"%PDF"))
            self.assertEqual(output.name, "ambulance-route-1.pdf")


if __name__ == "__main__":
    unittest.main()
