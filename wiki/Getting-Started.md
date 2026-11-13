# Getting started

## Prerequisites

- Python 3.10+.
- SUMO and its command-line tools. The scenario generator specifically uses
  SUMO's `randomTrips.py`; the controller uses SUMO and TraCI. `sumo-gui` is
  needed only for a graphical run.
- Python dependencies from `requirements.txt`: `matplotlib` and `networkx`.

Install SUMO using the
[official documentation](https://sumo.dlr.de/docs/Installing/index.html).
Create a virtual environment from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

The scenario runner looks for `randomTrips.py` in `SUMO_HOME`, SUMO-related
Python package locations, beside the `sumo` executable, and common Linux
install locations. If lookup fails, set `SUMO_HOME` to the SUMO installation
root, such as `/usr/share/sumo`. The `sumo`/`sumo-gui` executable must be
available on `PATH`, unless it is found in the packaged SUMO `bin` directory.

## First simulation

Run commands from the **repository root**:

```bash
python centar/scenario.py --gui
```

The default network is `centar`. For the full and Lite Skopje maps:

```bash
python centar/scenario.py --map skopje --gui
python centar/scenario.py --map skopjelite --gui
```

To run without opening a window, omit `--gui`:

```bash
python centar/scenario.py --map skopje
```

The defaults generate 1,200 passenger vehicles over 1,800 simulation seconds,
use seed `1`, and attempt to add one 60-second blockage with 20% probability.
The ambulance departs at 300 seconds. A small run for a quicker check:

```bash
python centar/scenario.py --map skopje --vehicles 100 \
  --duration 900 --seed 10 --accident-probability 0
```

Use `--ambulance-from-coordinates LAT LON` and
`--ambulance-to-coordinates LAT LON` together to select a route near map
coordinates. Coordinates are latitude then longitude. Instead, supply
`--ambulance-from EDGE_ID --ambulance-to EDGE_ID`. If neither pair is provided,
the generator uses a seeded, long, connected route.

## Run the controller on preconfigured files

For the central-area config and route files, change into `centar/`:

```bash
cd centar
python control.py --gui
```

This direct route bypasses scenario generation, so passenger and ambulance
routes must already be referenced by the SUMO config. See
[Ambulance routing](Ambulance-Routing.md) for all direct controller options.

## Help and tests

The CLIs print authoritative help text:

```bash
python centar/scenario.py --help
python centar/training.py --help
cd centar && python control.py --help
```

Run the focused Python tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

## Default run behavior

- Headless: ambulance signal priority is on unless `--no-preempt` is passed.
- GUI: normal signal cycles are used unless `--preempt` is passed.
- `--preempt` and `--no-preempt` are mutually exclusive.
- Normal cycles target `green-seconds + red-seconds`, retaining the existing
  yellow and other non-green phase durations.
- The default output directory is `scenario-output` under the selected map.
- `--duration` must be greater than `--ambulance-depart`.

For the complete flag descriptions and accepted ranges, see
[Scenario CLI](Scenario-CLI.md).
