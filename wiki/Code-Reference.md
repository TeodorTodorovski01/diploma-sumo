# Python code reference

This page documents the functions and class defined by the project's Python
scripts. The command-line flags are documented separately in
[Scenario CLI](Scenario-CLI.md), [Ambulance routing](Ambulance-Routing.md),
and [Training](Training.md). `centar/control.py` parses arguments and starts
SUMO at module load, so it is an executable script rather than a side-effect
free import library.

## `centar/scenario.py`

| Function | What it does |
|---|---|
| `find_sumo_tools() -> Path` | Searches `SUMO_HOME`, SUMO Python package locations, the `sumo` executable's install tree, and common system directories for `tools/randomTrips.py`. Raises a clear `RuntimeError` if the tools cannot be found. |
| `add_random_blockage(route_file, network_file, ambulance_file, seed, duration) -> str` | Reads generated passenger XML and network data, selects a suitable passenger route before ambulance departure, appends one timed `<stop>` on a passenger lane, colors that vehicle red, saves XML, and returns its ID. Raises if the ambulance or a suitable passenger/lane is missing. |
| `generate_ambulance_route(network_file, route_file, seed, depart=300, source_id=None, destination_id=None, source_coordinates=None, destination_coordinates=None) -> tuple[str, str, int]` | Builds and saves an emergency-class ambulance route. Accepts an edge pair, coordinate pair (nearest connected emergency roads within 250 m), or no pair (seeded search for a long connected route). Returns source ID, destination ID, and number of edges. |
| `parse_args() -> argparse.Namespace` | Defines the scenario CLI, loads search defaults, parses and validates option pairs, ranges, map restrictions, and comparison/GUI compatibility. |
| `read_ambulance_trip_time(tripinfo_file, max_trip_time) -> str` | Streams tripinfo XML for `amb0`; returns a formatted duration, `Unavailable`, or a not-completed message. |
| `run_map_time_comparison(options) -> None` | Runs the selected scenario settings once on full Skopje and once on Skopje Lite, measures whole-run wall time and trip times, and writes `runtime-comparison.pdf`. |
| `main() -> None` | Resolves map/config/output paths, prepares SUMO tools environment, generates and validates passenger trips, makes the ambulance route and optional blockage, builds controller arguments, and launches the controller. In comparison mode, dispatches the comparison workflow instead. |

`scenario.py`'s main guard calls `main()` when executed as a script.

## `centar/control.py`

These are module-level functions inside an executable script; its argument
parsing and `traci.start()` happen before these definitions are reached.

| Function | What it does |
|---|---|
| `weight(eid)` | Returns current SUMO travel time for edge `eid`, plus `TLS_PENALTY` if the edge ends at a traffic-light node. |
| `build_routing_graph()` | Builds a directed NetworkX graph over emergency-accessible road edges; graph arc weight is the cost of the edge being left. |
| `plan(G, src, dst, algorithm)` | Returns the least-weight edge path using Dijkstra or A*. A* requires a positive maximum emergency-road speed and uses a straight-line time heuristic scaled by the configured weight. |
| `set_normal_signal_cycles(green_seconds, red_seconds)` | For every traffic light, scales green-only phases to fit the requested total cycle while preserving yellow and other fixed phase durations. Raises if the active program cannot fit that cycle. |
| `green_phase(tls, link)` | Finds and caches the first signal phase that provides a green state for a traffic-light link. Returns `None` if no phase is found. |
| `preempt(t)` | Checks the ambulance's next traffic lights within 120 m; requests the applicable green phase or extends an about-to-end green for five seconds. |
| `run_once()` | Executes one simulation, samples city-wide edge occupancy/waiting metrics, tracks traversed ambulance edges, collects trip measurements, periodically replans, performs optional signal priority, and writes a route PDF if the ambulance traveled over recorded roads. |

Notable controller constants: `AMB` is the fixed vehicle ID `amb0`;
`DIST` is the 120 m signal lookahead; `AMBULANCE_SPEED_FACTOR` is `1.3` and
is used when estimating the maximum speed for A*; `REPLAN`,
`TLS_PENALTY`, `SEARCH_ALGORITHM`, and `ASTAR_HEURISTIC_WEIGHT` come from
parsed CLI options and/or search defaults. Smart City traffic metrics are
sampled no more frequently than every 30 simulation seconds (or the configured
replan interval, when larger).

## `centar/smart_city.py`

| Name | What it does |
|---|---|
| `EdgeTrafficMetric` | Type alias for `(peak_occupancy_percent, peak_summed_waiting_seconds)`. |
| `collect_smart_city_metrics(edge_ids, previous, get_occupancy, get_waiting_time) -> dict[str, EdgeTrafficMetric]` | Samples occupancy and summed waiting time for currently occupied edges, retaining independent per-edge peaks across snapshots. Returns a new mapping without modifying the previous mapping. |

## `centar/training.py`

| Function | What it does |
|---|---|
| `parse_args() -> argparse.Namespace` | Defines and validates training, SPSA, scenario, coordinate, output, and apply options. |
| `clamp(value) -> float` | Limits a normalized optimizer value to `[0, 1]`. |
| `normalize(parameters, names) -> list[float]` | Maps named real-valued parameters to normalized values using `PARAMETER_BOUNDS`. |
| `denormalize(values, names) -> dict[str, float]` | Maps normalized values back to bounded parameters, clamping each normalized value first. |
| `read_trip_time(tripinfo_file) -> float | None` | Streams tripinfo XML and returns the numeric duration of `amb0`, or `None` if the trip has no duration or no entry. |
| `scenario_signature(options) -> dict[str, object]` | Captures fixed training scenario inputs and the SHA-256 of Skopje Lite network data, so checkpoints are only reused for matching profiles. |
| `load_best_checkpoint(path, signature) -> dict[str, object] | None` | Returns no result if absent; otherwise verifies profile and stored best-trip data before returning it. Invalid data raises `ValueError`. |
| `save_best_checkpoint(path, signature, best_result, created_at) -> None` | Writes the profile and best result through a temporary file followed by replacement. |
| `display_number(value) -> str` | Formats a number for reports, using `automatic` for `None`. |
| `write_training_artifacts(...) -> tuple[Path, Path, str]` | Creates the PDF and CSV evaluation report, returning their paths and the report timestamp. |
| `run_evaluation(options, parameters, evaluation, output_dir) -> dict[str, object]` | Runs one Skopje Lite scenario as a checked subprocess and returns evaluation number, parameters, trip time, and objective. |
| `optimize(options) -> None` | Loads defaults and matching best checkpoint, evaluates baseline and SPSA perturbations, retains the best, conditionally saves defaults/checkpoint, and writes the JSON/PDF/CSV reports. |

`PARAMETER_BOUNDS` contains the training bounds for replanning interval,
traffic-light penalty, and A* heuristic weight. The module's main guard calls
`optimize(parse_args())`.

## `centar/search_defaults.py`

| Name | What it does |
|---|---|
| `DEFAULTS_FILE` | Path to the adjacent `search_defaults.json`. |
| `SearchDefaults` | Frozen dataclass containing `search_algorithm`, `replan_interval`, `traffic_light_penalty`, and `astar_heuristic_weight`. |
| `load_search_defaults(path=DEFAULTS_FILE) -> SearchDefaults` | Parses and validates a JSON object; validates allowed algorithm, finite numeric values, positive interval, and non-negative optional penalty/weight. Invalid content raises `ValueError`. |
| `save_search_defaults(defaults, path=DEFAULTS_FILE) -> None` | Creates parent directories and atomically replaces the JSON file via a `.tmp` sibling. Writes indented JSON with a final newline. |

## `centar/route_pdf.py`

| Function or constant | What it does |
|---|---|
| `TABLE_MAX_PAGE_HEIGHT` | Maximum page-height fraction reserved for the route's settings table. |
| `write_route_pdf(net, traversed_edge_ids, output_path, map_name, parameters, traffic_metrics=None) -> Path` | Draws peak occupancy and waiting-time heat maps, overlays recorded ambulance edges in green, and adds a settings table, title, and attribution. Adds an incrementing numeric suffix to avoid overwriting a previous route PDF. Raises `ValueError` if no route segment can be drawn. |
| `write_runtime_comparison_pdf(output_path, elapsed_by_map, ambulance_trip_times, scenario) -> Path` | Creates the comparison table for full Skopje and Skopje Lite wall times, trip times, saved time/percentage, scenario summary, and report timestamp. |

## `centar/make_amb.py`

This standalone script has no functions or CLI parser. When run in `centar/`,
it seeds Python's random generator with `1`, samples passenger-accessible
edges, picks the longest connected route found in up to 300 attempts, and
writes `amb.rou.xml` with `amb0` departing at 300 seconds. It prints the
selected source/destination and approximate length. The regular
`scenario.py` uses its own `generate_ambulance_route()` for generated Skopje
routes.

## Tests

`tests/test_smart_city.py` checks peak metric accumulation and creates a route
PDF with heat-map data. `tests/test_training.py` checks training checkpoint
round-tripping, profile validation, resuming, retaining, and improving the
best result.

Run the tests with
`python -m unittest discover -s tests -v`.
