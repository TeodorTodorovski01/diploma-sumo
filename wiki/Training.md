# Routing-parameter training

## What training does

`centar/training.py` uses simultaneous perturbation stochastic approximation
(SPSA) to tune route-search parameters against the ambulance's SUMO trip
duration. It runs on `skopjelite` with a fixed scenario seed and no simulated
blockage, then measures `amb0`'s duration from `tripinfo.xml`.

SUMO route selection and traffic simulation are discrete and non-differentiable.
The finite-difference gradient SPSA estimates is approximate; this is not
backpropagation or a neural-network trainer. A better measured value on the
training scenario is not a guarantee of better results on the full Skopje map
or under different traffic.

## Command

From the repository root:

```bash
python centar/training.py [options]
```

Example:

```bash
python centar/training.py --search-algorithm astar \
  --iterations 3 --alpha 0.05 --vehicles 100 --duration 900 --seed 10
```

The baseline, two perturbation evaluations per iteration, and final candidate
mean a total of `2 + 2 × iterations` evaluations; three iterations take eight
SUMO runs.

## Options and keywords

| Option | Default | Meaning |
|---|---:|---|
| `--search-algorithm {dijkstra,astar}` | `astar` | Selects the scenario controller algorithm and parameters to tune. Dijkstra tunes interval and penalty. A* tunes those plus heuristic weight. |
| `--iterations N` | `3` | Number of SPSA updates; must be positive. Each iteration evaluates a positive and negative perturbation. |
| `--alpha`, `--learning-rate`, `--a` | `0.05` | Aliases for the SPSA step-size coefficient; finite and greater than zero. |
| `--perturbation`, `--c` | `0.1` | Aliases for initial perturbation size; must be greater than zero and at most `0.5`. |
| `--alpha-exponent` | `0.602` | Decay exponent for the step size; greater than `0.5` and at most `1`. |
| `--gamma` | `0.101` | Decay exponent for perturbation magnitude; greater than zero and at most `0.5`. |
| `--vehicles N` | `100` | Passenger vehicle count; greater than zero. |
| `--duration SECONDS` | `900` | Scenario end time; must be greater than departure. |
| `--ambulance-depart SECONDS` | `120` | Ambulance departure time; non-negative. |
| `--seed N` | `1` | Fixed scenario and SPSA random seed. |
| `--ambulance-from-coordinates LAT LON` | `41.976343 21.549497` | Skopje Lite origin, latitude then longitude. |
| `--ambulance-to-coordinates LAT LON` | `42.006512 21.402385` | Skopje Lite destination, latitude then longitude. |
| `--output-dir PATH` | `skopje/scenario-output/training` | Directory for evaluations, reports, and persistent best checkpoints. |
| `--no-apply` | off | Do not modify `centar/search_defaults.json`; still report results. |
| `--help` | — | Display help and exit. |

The optimizer normalizes parameters into `[0, 1]`, clamps candidate values to
that interval, and maps them to these ranges:

| Parameter | Training range |
|---|---:|
| `replan_interval` | 5–60 simulation seconds |
| `traffic_light_penalty` | 0–30 estimated seconds |
| `astar_heuristic_weight` | 0.5–2.0 (A* only) |

`alpha` controls the update size; `alpha-exponent` decays that size over
iterations. `perturbation` is the initial parameter-space perturbation;
`gamma` decays it. A seeded random direction picks a `-1` or `+1` perturbation
for each tuned value. The optimizer estimates each gradient component from the
two measured objectives, bounds the estimate, updates the center, and keeps
the best observed evaluation.

## Objective and incomplete trips

The objective is the ambulance trip duration in simulation seconds. If the
ambulance does not complete before the time limit, training assigns a penalty
larger than the available trip window so completed trips are preferred. A
training run does not apply defaults unless at least one trip completed or a
valid matching prior best exists.

Training is deterministic only to the extent that the fixed seed, SUMO
behavior, environment, and network files produce repeatable evaluations.

## Saved defaults and checkpoints

After a completed trip, training applies its best parameters to
`centar/search_defaults.json`, unless `--no-apply` was supplied. Scenario runs
and direct controller launches read this file on their next start.

Training also writes a profile-specific
`training-best-<profile-id>.json` checkpoint. Its profile includes the
Skopje Lite network SHA-256, algorithm, vehicle count, duration, departure,
coordinates, seed, and fixed no-blockage/preemption/signal settings. A later
run with the same profile resumes from and compares against the stored best.
A different profile is not compared with it. Invalid or mismatched checkpoint
data raises an error rather than being silently used.

## Artifacts

Default output directory: `skopje/scenario-output/training/`.

- `training-report.pdf` — objective curve and previous/default/learned
  parameter table, optimizer settings, completion measurements, and whether
  defaults were applied.
- `training-results.csv` — one row per evaluation, including objective, trip
  time, and parameters.
- `training-results.json` — full scenario signature, optimizer configuration,
  best and previous-best results, evaluation data, checkpoint path, and
  artifact paths.
- `training-best-<profile-id>.json` — persistent best result for the scenario
  profile.
- `evaluation-NNN/` — generated routes, tripinfo, and route PDF for each SUMO
  evaluation.
