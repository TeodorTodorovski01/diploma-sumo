# Ambulance routing and controller

## Routing model

During a run, the controller builds a directed graph whose nodes represent
road edges accessible to SUMO's `emergency` vehicle class. A graph connection
means the ambulance can drive from one road edge directly to the next.
The estimated cost of an edge is its current SUMO travel time plus an optional
traffic-light penalty when the edge ends at a traffic-light node.

The route is calculated from the ambulance's current edge to the destination
edge, periodically at `--replan-interval`. Dynamic replanning uses the
travel-time values available at that simulation step. If SUMO or NetworkX
reports a route-planning error, the controller logs it and continues the
simulation.

### Dijkstra

`dijkstra` computes a least-weight route under the current edge-time and
traffic-light-penalty costs. It is the checked-in default and is used by the
controller's initial ETA estimate.

### A*

`astar` uses the same weighted graph and a straight-line travel-time heuristic:
distance from the current edge's destination node to the destination edge's
origin node, divided by the maximum emergency-road speed estimate. The
`--astar-heuristic-weight` multiplier scales that estimate. Weight `1` uses the
unscaled heuristic; values above `1` can expand fewer nodes but are not
guaranteed to return the least-cost route. A weight of `0` removes the
heuristic contribution.

### Replan interval and penalty

- `--replan-interval` is measured in simulation seconds and must be greater
  than zero.
- `--traffic-light-penalty` is an added estimated cost, in seconds, per
  edge whose endpoint is a traffic light. It is not a measured signal wait.
- If the JSON penalty is `null` and the CLI option is omitted, the controller
  chooses zero with preemption and 15 seconds without it.
- These values affect route selection, not the underlying SUMO vehicle travel
  speed.

## Signal behavior

Signal priority is on by default for headless runs and off by default for GUI
runs. `--preempt` enables priority; `--no-preempt` disables it. The two flags
cannot be used together.

When enabled, the controller looks ahead to the next signal on the ambulance
route. Within 120 m it requests the signal phase that gives the ambulance's
link a green, holding that phase for a short five-second interval. If the
current state is already green but it is about to switch in less than five
seconds, it extends the current phase. This is a simple simulation control
strategy; it is not a citywide signal coordination policy.

When priority is off, the controller updates the active signal programs. The
sum `--green-seconds + --red-seconds` is the target cycle duration; existing
yellow and other non-green phases are preserved, and green phases are scaled
to fill the remaining time. Consequently, these options do not force each
intersection's individual green and red intervals to equal the two values.

## Direct controller command

The scenario generator invokes the controller for you. To run it directly
with the central-area SUMO config, from the `centar/` directory:

```bash
python control.py --gui
```

Run `python control.py --help` for current help. All controller options:

| Option | Default | Meaning |
|---|---|---|
| `--gui` | off | Use `sumo-gui`; otherwise use `sumo`. |
| `--preempt` | off | Request signal priority. |
| `--no-preempt` | off | Explicitly disable priority. Mutually exclusive with `--preempt`. Headless defaults to priority; GUI defaults to normal operation. |
| `--sumo-route` | off | Keep SUMO's existing route instead of assigning the controller's own planned route. Signal handling remains independently selectable. |
| `--passenger-routes PATH` | none | Use this passenger route file and the ambulance route file as the SUMO route files. |
| `--ambulance-route PATH` | `amb.rou.xml` | Ambulance route file, used with `--passenger-routes`. |
| `--config-file PATH` | `run.sumocfg` | SUMO configuration file. |
| `--network-file PATH` | `net.net.xml` | Network loaded for route graph and PDF map drawing. |
| `--tripinfo-output PATH` | mode-tagged `tripinfo_*.xml` | SUMO trip-info output file. The default name distinguishes own/SUMO routes and preemption state. |
| `--route-pdf PATH` | `ambulance-route.pdf` | Base filename for the route map. A numbered suffix is added to avoid overwriting an existing PDF. |
| `--map-name NAME` | current directory title | Display name used in the route PDF title. |
| `--search-algorithm {dijkstra,astar}` | JSON setting | Route search algorithm. |
| `--replan-interval SECONDS` | JSON setting | Route recalculation interval; finite and positive. |
| `--traffic-light-penalty SECONDS` | JSON setting or automatic | Non-negative cost added at traffic-light edges. |
| `--astar-heuristic-weight N` | JSON setting | Non-negative A* heuristic multiplier. |
| `--scenario-parameters JSON` | `{}` | JSON object of extra setting/value pairs printed in the route PDF table. |
| `--end-time SECONDS` | config limit | Optional simulation end time. |
| `--green-seconds SECONDS` | `25` | Green contribution used for normal signal cycles. |
| `--red-seconds SECONDS` | `25` | Red contribution used for normal signal cycles. |
| `--help` | — | Display help and exit. |

`control.py` expects the configured route files to contain vehicle `amb0`.
The generated scenario passes absolute paths and scenario metadata to the
controller automatically.

## Route PDF measurements

The route map highlights recorded ambulance road segments in red. The
parameter table includes the search settings, simulation wall time, measured
ambulance trip duration (or an incomplete/not-started status), and the
initial Dijkstra ETA when available. That ETA is an estimate based on initial
edge costs, not the eventual observed trip duration.
