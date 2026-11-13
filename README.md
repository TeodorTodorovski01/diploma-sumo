# SUMO Traffic and Ambulance Simulation

This project uses [SUMO (Simulation of Urban MObility)](https://sumo.dlr.de/)
to generate and simulate passenger traffic and an emergency vehicle on a
central Skopje map or a wider Skopje road network. During a run, the ambulance
can periodically replan around current traffic and can request signal priority.
Training tools can tune the route-search settings against measured ambulance
trip times.

## What it can do

- Generate validated passenger trips with SUMO's `randomTrips.py`.
- Select the central `centar`, full-city `skopje`, or smaller `skopjelite`
  network.
- Choose a Skopje ambulance route from edge IDs, latitude/longitude
  coordinates, or a seeded long random route.
- Recalculate an emergency-accessible route using Dijkstra or A* and current
  edge travel times.
- Enable ambulance signal preemption, or preserve normal signal cycles while
  setting their target cycle duration.
- Optionally add one temporary stopped passenger vehicle as a road blockage.
- Save trip information, generated routes, a PDF of the roads the ambulance
  actually traveled, and optional map runtime comparisons.
- Use SPSA training to tune route-search parameters and optionally apply the
  best completed result as the defaults for later runs.

## Requirements and installation

- Python 3.10 or newer.
- SUMO, including `sumo`, `sumo-gui` (for graphical runs), `sumolib`,
  TraCI, `netconvert` (only when rebuilding networks), and the SUMO tools
  containing `randomTrips.py`.
- Python packages listed in [`requirements.txt`](requirements.txt): `matplotlib`
  and `networkx`.

Install SUMO using the
[official installation instructions](https://sumo.dlr.de/docs/Installing/index.html).
Create a Python environment and install the project packages:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

In PowerShell, activate with `.venv\Scripts\Activate.ps1`. The scenario
generator searches common SUMO locations and Python package paths for the
tools. If it cannot find `randomTrips.py`, set `SUMO_HOME` to the SUMO
installation directory (the directory containing `tools/`), for example:

```bash
export SUMO_HOME=/usr/share/sumo
```

The SUMO `bin` directory must also be on `PATH` when the executable cannot be
found automatically.

## Quick start

From the repository root, run the preconfigured central-area scenario:

```bash
python centar/scenario.py --gui
```

Run the larger Skopje map or its editable Lite network:

```bash
python centar/scenario.py --map skopje --gui
python centar/scenario.py --map skopjelite --gui
```

Omit `--gui` for a headless run. A compact, reproducible example with a fixed
ambulance route and no blockage is:

```bash
python centar/scenario.py --map skopje \
  --vehicles 100 --duration 900 --seed 10 \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 120 --accident-probability 0
```

Coordinates are specified as `LAT LON`, in that order. Both start and
destination must be specified together. Edge-ID inputs can be used instead:
`--ambulance-from EDGE_ID --ambulance-to EDGE_ID`.

Run training on Skopje Lite:

```bash
python centar/training.py --search-algorithm astar \
  --iterations 3 --vehicles 100 --duration 900 --seed 10
```

Training launches `2 + 2 × iterations` SUMO evaluations (eight for three
iterations). It writes reports under
`skopje/scenario-output/training/`. See the [wiki index](wiki/Home.md) for the
full command reference, configuration keys, algorithms, function reference,
and output descriptions.

## Key behavior and defaults

The scenario command defaults to 1,200 passenger vehicles, an 1,800-second
simulation, seed `1`, and a 20% chance of one 60-second blockage. The
preconfigured central ambulance route departs at 300 seconds. A generated
Skopje ambulance route also departs at 300 seconds unless changed.
`--duration` must be greater than the ambulance departure time.

Headless runs enable signal priority by default; GUI runs use normal signal
cycles by default. `--preempt` explicitly enables priority and `--no-preempt`
explicitly disables it. Without an explicit `--traffic-light-penalty`, the
controller uses a zero-second penalty when signal priority is active and
15 seconds otherwise. The checked-in route-search defaults are read from
[`centar/search_defaults.json`](centar/search_defaults.json); training may
update them after a trip completes. See [Ambulance routing](wiki/Ambulance-Routing.md)
and [Training](wiki/Training.md) for details.

## Repository map

```text
centar/
  scenario.py             Scenario CLI, traffic generation, and launcher
  control.py              TraCI controller, route replanning, signal handling
  training.py             SPSA optimizer and evaluation reports
  search_defaults.py      Validated search-defaults load/save helpers
  search_defaults.json    Shared default route-search settings
  route_pdf.py             Route and runtime-comparison PDF generation
  make_amb.py              Standalone random long-route generator
  run.sumocfg, net.net.xml Central-area SUMO config and road network
  amb.rou.xml              Preconfigured central-area ambulance trip
  routes.rou.xml           Preconfigured central-area passenger routes
skopje/
  README.md                Map notes and network rebuild instructions
  map.osm                  OpenStreetMap source data
  net.net.xml.gz            Full Skopje network
  skopjelite.net.xml        Skopje Lite network used for training
  *.sumocfg                 SUMO configurations
tests/
  test_training.py         Focused training-checkpoint tests
wiki/                       Detailed project documentation
```

Generated scenario and training output is placed in each map's
`scenario-output/` directory and is ignored by Git. Full details are in
[Outputs and data](wiki/Outputs-and-Data.md).

## Map attribution

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
The Skopje network extent, input files, and rebuild command are documented in
[`skopje/README.md`](skopje/README.md).

## Documentation and support

- [Wiki home](wiki/Home.md)
- [Getting started](wiki/Getting-Started.md)
- [Scenario command reference](wiki/Scenario-CLI.md)
- [Ambulance routing and controller](wiki/Ambulance-Routing.md)
- [Training and SPSA settings](wiki/Training.md)
- [Python function reference](wiki/Code-Reference.md)
- [Outputs, formats, and glossary](wiki/Outputs-and-Data.md)
- [Troubleshooting](wiki/Troubleshooting.md)

Useful first checks:

```bash
python centar/scenario.py --help
python centar/training.py --help
cd centar && python control.py --help
```
