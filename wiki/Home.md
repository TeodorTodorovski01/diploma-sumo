# SUMO Traffic and Ambulance Simulation Wiki

Welcome. This project creates SUMO traffic scenarios and tests ambulance
routing and traffic-signal behavior in central Skopje and two wider-area
networks.

## Pages

- [Getting started](Getting-Started.md) — software setup, first run, and
  run-mode behavior.
- [Scenario CLI](Scenario-CLI.md) — every `scenario.py` option and its defaults.
- [Ambulance routing](Ambulance-Routing.md) — Dijkstra, A*, signal priority,
  controller command, and controller options.
- [Training](Training.md) — SPSA training, optimizer keywords, checkpoints,
  and artifacts.
- [Code reference](Code-Reference.md) — every Python function and class in the
  project scripts.
- [Outputs and data](Outputs-and-Data.md) — generated files, XML vocabulary,
  configuration keys, and terminology.
- [Troubleshooting](Troubleshooting.md) — common installation and run errors.

## Project at a glance

`centar/scenario.py` is the normal entry point. It generates passenger trips,
creates a generated ambulance route for the two Skopje networks, optionally
adds one stopped passenger vehicle, and starts `centar/control.py`.
`control.py` advances SUMO with TraCI, periodically updates the ambulance
route, optionally adjusts traffic lights, and writes a route PDF.
`centar/training.py` repeatedly runs controlled Skopje Lite scenarios and
optimizes selected routing values against the ambulance trip duration.

## Network choices

| CLI value | Network files | Description |
|---|---|---|
| `centar` | `centar/net.net.xml`, `centar/run.sumocfg` | Central-area map; uses the preconfigured `centar/amb.rou.xml` ambulance trip. |
| `skopje` | `skopje/net.net.xml.gz`, `skopje/skopje.sumocfg` | Larger Skopje network. |
| `skopjelite` | `skopje/skopjelite.net.xml`, `skopje/skopjelite.sumocfg` | Smaller editable network; used by the training workflow. |

The central-area scenario uses its preconfigured ambulance trip. Ambulance
start, destination, and departure CLI options are supported only for
`skopje` and `skopjelite`.

## Important distinction

This repository's training is **simulation-based routing-parameter tuning**.
It uses SPSA (simultaneous perturbation stochastic approximation) to tune
replanning interval, traffic-light penalty, and—when using A*—heuristic weight.
It does not train a neural network or use backpropagation.
