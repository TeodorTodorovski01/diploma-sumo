# Scenario CLI reference

The scenario generator is run from the repository root:

```bash
python centar/scenario.py [options]
```

It generates passenger trips, selects or creates the ambulance trip, may
insert a temporary stopped-vehicle blockage, and launches the controller.
`python centar/scenario.py --help` prints the command's help.

## Options

| Option | Default | Meaning |
|---|---:|---|
| `--map {centar,skopje,skopjelite}` | `centar` | Selects network/config files. `centar` uses the preconfigured ambulance trip; the other two generate one. |
| `--vehicles N` | `1200` | Number of passenger vehicles requested from `randomTrips.py`; must be greater than zero. The script verifies the generated count. |
| `--duration SECONDS` | `1800` | End of passenger-trip generation and controller simulation limit. Must exceed ambulance departure. |
| `--ambulance-from EDGE_ID` | random | Skopje start edge ID; must be supplied with `--ambulance-to`. |
| `--ambulance-to EDGE_ID` | random | Skopje destination edge ID; must be supplied with `--ambulance-from`. |
| `--ambulance-from-coordinates LAT LON` | random | Skopje starting coordinates, in latitude/longitude order. Both coordinate options must be supplied together. |
| `--ambulance-to-coordinates LAT LON` | random | Skopje destination coordinates, in latitude/longitude order. Nearby emergency roads are searched within 250 m. |
| `--ambulance-depart SECONDS` | `300` | Departure time for a generated Skopje ambulance route; must be non-negative. Only supported on Skopje maps. |
| `--accident-probability PERCENT` | `20` | Chance from `0` to `100` of adding one stopped passenger vehicle. Despite the option's name, this inserts a simple blockage, not a collision/damage model. |
| `--accident-duration SECONDS` | `60` | Stop duration for the inserted blockage; must be positive. |
| `--seed N` | `1` | Seed for passenger route generation, random ambulance route selection, and blockage selection. |
| `--green-seconds SECONDS` | `25` | Green contribution to the target cycle duration when normal cycles are active; must be positive. |
| `--red-seconds SECONDS` | `25` | Red contribution to the target cycle duration when normal cycles are active; must be positive. |
| `--search-algorithm {dijkstra,astar}` | from JSON (`dijkstra`) | Controller route search method. |
| `--replan-interval SECONDS` | from JSON (`30`) | Minimum simulation-time interval between ambulance route calculations; must be finite and positive. |
| `--traffic-light-penalty SECONDS` | from JSON (`0`) | Extra estimated cost for each route edge ending at a traffic light; finite and non-negative. If omitted and JSON says `null`, controller selects `0` with priority or `15` without it. |
| `--astar-heuristic-weight N` | from JSON (`1`) | Multiplier on A*'s straight-line travel-time estimate; finite and non-negative. Values above `1` can trade route optimality for faster search. |
| `--output-dir PATH` | `scenario-output` | Output folder. Relative paths resolve under `centar/` for the central network and `skopje/` for either Skopje network. |
| `--compare-time` | off | Runs the same headless scenario on both `skopje` and `skopjelite`, then writes a runtime-comparison PDF. Requires a Skopje map selection and cannot be combined with `--gui`. |
| `--gui` | off | Opens SUMO-GUI instead of running headlessly. |
| `--preempt` | mode-dependent | Enable ambulance signal priority; mutually exclusive with `--no-preempt`. |
| `--no-preempt` | mode-dependent | Keep normal signal operation; mutually exclusive with `--preempt`. |
| `--help` | — | Display help and exit. |

## Route selection validation

The following pairs are mutually exclusive and must be complete:

```text
--ambulance-from EDGE_ID --ambulance-to EDGE_ID
--ambulance-from-coordinates LAT LON --ambulance-to-coordinates LAT LON
```

Use exactly one pair or neither. Both pairs are only supported on `skopje` and
`skopjelite`. For coordinate input, the generator projects the latitude and
longitude into SUMO map coordinates, finds emergency-accessible roads within
250 meters, and selects the nearest connected candidate pair. Edge IDs must
exist and allow emergency vehicles. If no pair is provided, seeded random
candidate pairs are tried until a long connected route is found.

## Examples

Small headless run, with no blockage:

```bash
python centar/scenario.py --map skopje --vehicles 100 --duration 900 \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 120 --accident-probability 0 --seed 10
```

Run the GUI with priority and tune route search:

```bash
python centar/scenario.py --map skopje --gui --preempt \
  --search-algorithm astar --astar-heuristic-weight 1.2 \
  --replan-interval 15 --traffic-light-penalty 5
```

Compare network runtimes with identical settings:

```bash
python centar/scenario.py --map skopje --compare-time \
  --vehicles 100 --duration 900 \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 120 --accident-probability 0 --seed 10
```

The comparison command runs headlessly even if a GUI is available. It measures
whole-run wall time (including route generation, simulation, and route PDF
generation), along with simulation-time ambulance durations when completed.

## How passenger trips and blockages are made

The passenger generation interval is `duration / vehicles`; generated trips
are validated and distributed from time zero to the requested duration.
`randomTrips.py` receives the chosen seed and passenger vehicle class.

When the seeded probability draw passes, the script chooses a qualifying
passenger vehicle that departs before the ambulance. It finds a lane in that
vehicle's route which admits passenger vehicles and is at least 20 m long,
then adds a SUMO `<stop>` of the requested duration. At most one stop is added.

See [Outputs and data](Outputs-and-Data.md) for generated file names.
