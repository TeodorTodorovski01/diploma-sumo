import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "centar"))

import training
from search_defaults import SearchDefaults


class TrainingBestPersistenceTests(unittest.TestCase):
    def test_checkpoint_round_trip_and_scenario_validation(self) -> None:
        signature = {"seed": 10, "network_sha256": "abc"}
        best = {
            "parameters": {
                "replan_interval": 20.0,
                "traffic_light_penalty": 1.0,
                "astar_heuristic_weight": 1.1,
            },
            "ambulance_trip_time_seconds": 42.0,
            "objective_seconds": 42.0,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "training-best.json"
            training.save_best_checkpoint(path, signature, best, "created")

            self.assertEqual(training.load_best_checkpoint(path, signature), best)
            with self.assertRaises(ValueError):
                training.load_best_checkpoint(path, {"seed": 11})

    def test_later_run_keeps_and_resumes_previous_best(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            signature = {"seed": 10, "network_sha256": "abc"}
            options = SimpleNamespace(
                output_dir=str(output_dir),
                search_algorithm="astar",
                iterations=0,
                alpha=0.05,
                alpha_exponent=0.602,
                perturbation=0.1,
                gamma=0.101,
                vehicles=100,
                duration=900,
                ambulance_depart=120,
                ambulance_from_coordinates=(41.9, 21.5),
                ambulance_to_coordinates=(42.0, 21.4),
                seed=10,
                no_apply=False,
            )
            def run_once(
                trip_times: list[float],
            ) -> tuple[dict[str, object], dict[str, float]]:
                baseline_parameters: dict[str, float] | None = None

                def fake_evaluation(
                    _options: object,
                    parameters: dict[str, float],
                    evaluation: int,
                    _output_dir: Path,
                ) -> dict[str, object]:
                    nonlocal baseline_parameters
                    if evaluation == 0:
                        baseline_parameters = parameters.copy()
                    trip_time = trip_times[evaluation]
                    return {
                        "evaluation": evaluation,
                        "parameters": parameters,
                        "ambulance_trip_time_seconds": trip_time,
                        "objective_seconds": trip_time,
                    }

                with (
                    patch.object(training, "scenario_signature", return_value=signature),
                    patch.object(
                        training,
                        "load_search_defaults",
                        return_value=SearchDefaults("astar", 30.0, 0.0, 1.0),
                    ),
                    patch.object(training, "save_search_defaults"),
                    patch.object(training, "run_evaluation", side_effect=fake_evaluation),
                    patch.object(
                        training,
                        "write_training_artifacts",
                        return_value=(
                            output_dir / "report.pdf",
                            output_dir / "results.csv",
                            "created",
                        ),
                    ),
                ):
                    training.optimize(options)
                report = json.loads(
                    (output_dir / "training-results.json").read_text(encoding="utf-8")
                )
                if baseline_parameters is None:
                    self.fail("Training did not evaluate a baseline")
                return report, baseline_parameters

            first_report, _ = run_once([40.0, 45.0])
            best_parameters = first_report["best_result"]["parameters"]
            second_report, resumed_parameters = run_once([60.0, 65.0])

            self.assertEqual(
                resumed_parameters,
                {
                    "replan_interval": best_parameters["replan_interval"],
                    "traffic_light_penalty": best_parameters["traffic_light_penalty"],
                    "astar_heuristic_weight": best_parameters["astar_heuristic_weight"],
                },
            )
            self.assertEqual(
                second_report["previous_best_result"]["ambulance_trip_time_seconds"],
                40.0,
            )
            self.assertEqual(
                second_report["best_result"]["ambulance_trip_time_seconds"],
                40.0,
            )
            improved_report, _ = run_once([35.0, 37.0])
            self.assertEqual(
                improved_report["previous_best_result"][
                    "ambulance_trip_time_seconds"
                ],
                40.0,
            )
            self.assertEqual(
                improved_report["best_result"]["ambulance_trip_time_seconds"],
                35.0,
            )
            checkpoint = json.loads(
                Path(improved_report["best_checkpoint"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                checkpoint["best_result"]["ambulance_trip_time_seconds"], 35.0
            )


if __name__ == "__main__":
    unittest.main()
