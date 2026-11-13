# SUMO Traffic and Ambulance Simulation

This project uses [SUMO](https://sumo.dlr.de/) (Simulation of Urban MObility)
to simulate passenger traffic, traffic lights, and an emergency vehicle in
Skopje. It includes a configurable scenario generator and two road networks:
the original central-area network and a larger urban Skopje network.

## Features

- Run a simulation in SUMO-GUI or headlessly.
- Select the central-area or Skopje road network.
- Generate a configurable number of passenger vehicles.
- Generate a long emergency-vehicle route for Skopje, or use the existing
  ambulance trip for the central-area map.
- Dynamically replan the ambulance route using current edge travel times.
- Optionally give the ambulance traffic-light priority.
- Configure the nominal signal-cycle duration while preserving yellow and
  other clearance phases when normal signal cycles are used.
- Optionally add one stopped passenger vehicle to simulate a temporary
  road blockage.
- Save generated routes and trip information for each scenario.
- Export a PDF map with the ambulance's actually traversed roads highlighted
  in red.

## Requirements

- Python 3.10 or later.
- SUMO and its tools, including `randomTrips.py` and `sumolib`.
- SUMO-GUI (`sumo-gui`) to view simulations graphically.
- Python packages `matplotlib` and `networkx`.

Install SUMO using the instructions for your operating system in the
[official SUMO documentation](https://sumo.dlr.de/docs/Installing/index.html).
The scenario script searches common system locations and SUMO's Python package
location for the SUMO tools. If it cannot find them, set `SUMO_HOME` to your
SUMO installation directory (the directory containing `tools/`).

Create a Python environment and install the project dependencies:

```bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with:

```powershell
venv\Scripts\Activate.ps1
```

If SUMO is installed outside the locations searched by the scenario script,
set `SUMO_HOME` before running it. For example:

```bash
export SUMO_HOME=/usr/share/sumo
```

Use the SUMO installation directory appropriate for your system.

## Run a scenario

From the repository root, start a graphical central-area scenario:

```bash
python centar/scenario.py --gui
```

Run the larger Skopje scenario:

```bash
python centar/scenario.py --map skopje --gui
```

To run the editable copy `skopje/skopjelite.net.xml`:

```bash
python centar/scenario.py --map skopjelite --gui
```

Compare the whole-run time on both networks using identical scenario settings
and a fixed seed. This runs headlessly and writes a timing table to
`skopje/scenario-output/runtime-comparison.pdf`. The table includes whole-run
wall time, ambulance trip duration in simulation seconds, the time saved, and
the report creation date/time:

```bash
python centar/scenario.py --map skopjelite --compare-time \
  --vehicles 100 --duration 900 \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 120 --accident-probability 0 --seed 10
```

For a headless run, omit `--gui`:

```bash
python centar/scenario.py --map skopje
```

The scenario generator defaults to 1,200 passenger vehicles over 1,800
simulation seconds, a 20% chance of one 60-second blockage, seed `1`, and a
nominal 25+25-second signal cycle. By default, the ambulance departs at 300
seconds. The simulation duration must be greater than the ambulance departure
time.

### Common options

```text
--map {centar,skopje,skopjelite}  Road network (default: centar)
--vehicles N                      Number of passenger vehicles (default: 1200)
--duration SECONDS                Traffic generation and simulation limit (default: 1800)
--ambulance-from EDGE_ID          Skopje ambulance start edge (default: random)
--ambulance-to EDGE_ID            Skopje ambulance destination edge (default: random)
source venv/bin/activate
export SUMO_HOME="$PWD/venv/lib64/python3.15/site-packages/sumo"
python centar/scenario.py --map skopje --gui \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 0 \
  --duration 1800 \
  --accident-probability 0--ambulance-from-coordinates LAT LON   Skopje start latitude and longitude
--ambulance-to-coordinates LAT LON     Skopje destination latitude and longitude
--ambulance-depart SECONDS        Skopje ambulance departure time (default: 300)
--accident-probability PERCENT    Chance of one blockage, from 0 to 100 (default: 20)
--accident-duration SECONDS       Blockage duration (default: 60)
--seed N                          Random seed (default: 1)
--green-seconds SECONDS           Green-time contribution to cycle (default: 25)
--red-seconds SECONDS             Red-time contribution to cycle (default: 25)
--output-dir PATH                 Generated-file directory (default: scenario-output)
--gui                             Run in SUMO-GUI
--preempt                         Give the ambulance traffic-light priority
--no-preempt                      Keep normal traffic-light cycles
```

For example, run a small Skopje GUI scenario without a blockage:

```bash
python centar/scenario.py \
  --map skopje \
  --gui \
  --vehicles 100 \
  --duration 900 \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 120 \
  --accident-probability 0 \
  --seed 10
```

Coordinates are entered as two values in latitude then longitude order. The
generator selects nearby emergency-accessible roads that have a connecting
route. Alternatively, use `--ambulance-from EDGE_ID` and `--ambulance-to
EDGE_ID` to specify road edge IDs directly. Omit both pairs to generate a long
random route. The simulation duration must be greater than the ambulance
departure time.

To make the ambulance receive signal priority in GUI mode, add `--preempt`.
Headless runs enable priority by default; use `--no-preempt` to disable it.
GUI runs use normal cycles by default unless `--preempt` is specified.

When priority is disabled, `--green-seconds` plus `--red-seconds` sets the
target total signal cycle. Existing yellow and clearance phases are retained;
the remaining time is distributed among the program's green phases. These
values do not independently force every signal's red and green portions to
match exactly.

### Route search settings

The checked-in defaults use weighted Dijkstra, minimizing estimated travel
time. The algorithm and numeric settings are read from
[`centar/search_defaults.json`](centar/search_defaults.json), which training
can update. Select `--search-algorithm astar` to use A* with a straight-line
travel-time heuristic. `--astar-heuristic-weight` defaults to `1`; values
above `1` may find a route faster but can sacrifice optimality. Tune how often
the route is recalculated with `--replan-interval` (seconds). Adjust the
per-traffic-light cost with `--traffic-light-penalty` (seconds); if unset,
the default is `0` with priority enabled and `15` otherwise.

For example:

```bash
python centar/scenario.py --map skopje --search-algorithm astar \
  --astar-heuristic-weight 1.2 --replan-interval 15 \
  --traffic-light-penalty 5 --gui
```

### Tune search defaults

`centar/training.py` uses simultaneous perturbation stochastic approximation
(SPSA), a finite-difference gradient method, to minimize the ambulance's
measured trip duration on Skopje Lite. SUMO routing is discrete and
non-differentiable, so this is an approximate gradient rather than
backpropagation. It tunes the replan interval and traffic-light penalty, plus
the A* heuristic weight when training A*. It uses a fixed seed and disables
simulated blockages to make parameter comparisons more repeatable.

Run a short training session:

```bash
python centar/training.py --search-algorithm astar \
  --iterations 3 --alpha 0.05 --vehicles 100 --duration 900 --seed 10
```

Training runs a baseline, two perturbed scenarios per iteration, and a final
scenario, so the default three iterations require eight SUMO runs.
`--alpha` (aliases `--learning-rate` and `--a`) is the gradient step size.
Because SUMO's routing objective is not differentiable, SPSA estimates the
gradient using perturbations. Their size and decay are optional controls:
`--perturbation`/`--c` (default `0.1`), `--alpha-exponent` (default `0.602`),
and `--gamma` (default `0.101`). You only need to set `--alpha` for a basic
run; the PDF report records all optimizer settings.

When at least one ambulance trip completes, the best observed parameters
automatically update [`centar/search_defaults.json`](centar/search_defaults.json).
Both the scenario runner and direct controller read that file on their next
launch; there is no manual copy step. If no trip completes, or if you pass
`--no-apply`, defaults remain unchanged.

Training writes `training-report.pdf` (objective graph and before/after
parameter table), `training-results.csv` (one row per evaluation), and
`training-results.json` under `skopje/scenario-output/training/`. The report
states whether defaults were applied. A profile-specific
`training-best-<id>.json` also remembers the best completed ambulance trip and
its parameters across runs. Repeated runs with the same algorithm, seed,
vehicle count, duration, route, and Skopje Lite network resume from and compare
against that best. Different scenarios use separate best records and are not
compared. After training on Skopje Lite, validate the learned settings on the
full Skopje network.

The blockage setting adds at most one stopped passenger vehicle to the
generated routes when the seeded probability check succeeds. It is a simple
temporary blockage, not a detailed collision or damage model.

## Run the controller directly

The scenario generator is the recommended way to create passenger routes and
start a simulation. To run the preconfigured central-area routes directly:

```bash
cd centar
python control.py
```

Open the same simulation in SUMO-GUI:

```bash
python control.py --gui
```

Direct controller options include `--preempt`, `--no-preempt`,
`--green-seconds`, and `--red-seconds`. Run `python control.py --help` for the
full list. The scenario script passes the selected map, generated route files,
and simulation time limit to the controller automatically.

## Generated files

Scenario files are written under the selected map directory:

- Central-area scenarios: `centar/scenario-output/`
- Skopje scenarios: `skopje/scenario-output/`

Each run generates passenger trips and validated routes. Skopje runs also
generate an ambulance route. Runs where the ambulance travels also create
`ambulance-route-N.pdf` (with an incrementing number), showing the city road
network and the roads actually traversed by the ambulance in red. The
lower-right table lists the scenario settings and route-search parameters and
is limited to 16% of the PDF page height. It also reports simulation wall
time for the controller loop, measured ambulance trip duration in SUMO
simulation seconds, and the Dijkstra-optimal ETA estimate from the initial
route calculation. If the ambulance does not arrive before the simulation
ends, the measured trip row reports elapsed time and marks it incomplete. The
SUMO trip-information output records vehicle departure, arrival, and
travel-time information. Generated scenario folders are ignored by Git.

## Repository layout

```text
centar/
  control.py       SUMO/TraCI simulation controller
  scenario.py      Configurable route generation and scenario launcher
  training.py     Search-parameter training on Skopje Lite
  search_defaults.json
                   Defaults shared by the scenario runner and controller
  run.sumocfg      Central-area SUMO configuration
  net.net.xml      Central-area SUMO road network
  amb.rou.xml      Preconfigured central-area ambulance trip
  routes.rou.xml   Preconfigured passenger routes
skopje/
  README.md        Skopje map details and rebuild instructions
  skopje.sumocfg   Skopje SUMO configuration
  net.net.xml.gz   Compressed Skopje SUMO road network
  map.osm          OpenStreetMap source extract
```

The `control.py` controller replans the ambulance's route periodically using
current road travel times and can request a green phase near traffic lights
when preemption is enabled.

## Skopje map and attribution

The Skopje network covers the wider urban area and is clipped to longitude
21.30–21.55 and latitude 41.90–42.10. The original OpenStreetMap extract is
included in [`skopje/map.osm`](skopje/map.osm). See
[`skopje/README.md`](skopje/README.md) for map details and instructions for
rebuilding the SUMO network.

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).

## Troubleshooting

- **SUMO tools or `randomTrips.py` not found:** Install the SUMO tools and set
  `SUMO_HOME` to the SUMO installation directory.
- **`sumo` or `sumo-gui` not found:** Add the SUMO `bin` directory to `PATH`.
- **GUI does not open:** Confirm SUMO-GUI is installed and that your desktop
  session supports graphical applications. Use a headless run without `--gui`
  if you only need simulation output.
- **Route-generation or network errors:** Confirm you selected the intended
  map and that the SUMO network file is present. For Skopje, the network is
  `skopje/net.net.xml.gz`.
