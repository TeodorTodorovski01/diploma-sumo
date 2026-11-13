# Troubleshooting

## `randomTrips.py` or SUMO tools not found

Install the SUMO tools and set `SUMO_HOME` to the SUMO installation root,
which contains `tools/`. The scenario generator searches common locations, but
custom installations may not be detected.

```bash
export SUMO_HOME=/path/to/sumo
```

## `sumo` / `sumo-gui` not found

Add SUMO's `bin` directory to `PATH`. `sumo-gui` is only required when using
`--gui`; omit the flag for a headless run.

## Missing Python imports

Activate the project's virtual environment and install the listed Python
requirements:

```bash
python -m pip install -r requirements.txt
```

The simulation additionally needs the Python modules supplied with SUMO
(`sumolib` and TraCI). The scenario runner configures the SUMO tools path for
its child controller process. For a direct controller run, invoke it from
`centar/` with an environment where SUMO's Python modules can be imported.

## GUI does not open

Confirm SUMO-GUI is installed and the machine has a graphical desktop session.
Use a headless run if only output files are needed.

## Invalid ambulance start/destination

- Edge IDs must exist in the chosen network and allow emergency vehicles.
- Both edge options must be provided together.
- Both coordinate pairs must be provided together; input order is latitude
  then longitude.
- Edge IDs and coordinate inputs cannot be mixed.
- Coordinate searches only consider emergency-accessible roads within 250 m
  and require a connected route.
- These options are for `skopje` and `skopjelite`, not `centar`.
- Increase `--duration` if the ambulance is not completing before simulation
  end; it must exceed `--ambulance-depart`.

## Route generation fails or requested count differs

The generator validates passenger routes against the selected network and
checks that the generated vehicle count matches `--vehicles`. Confirm the
selected network file exists and SUMO can read it. Large scenarios and full
Skopje networks can take longer to generate.

## No ambulance route PDF

The route PDF is written only if at least one ambulance road segment was
recorded and drawable. A run that ends before the ambulance starts, or ends
before it reaches a road, will not produce one. An incomplete trip that did
travel is still plotted and marked incomplete in the report.

## Search-default JSON invalid

Check `centar/search_defaults.json` is a JSON object containing all four keys:
`search_algorithm`, `replan_interval`, `traffic_light_penalty`, and
`astar_heuristic_weight`. Use `dijkstra` or `astar`; interval must be finite
and positive; penalty may be `null` or finite/non-negative; heuristic weight
must be finite/non-negative. Startup reports invalid values rather than
silently replacing them.

## Training run does not update defaults

Defaults are not updated when no ambulance trip completes, or when
`--no-apply` is used. Increase `--duration`, choose a reachable route, or rerun
without `--no-apply`. The training report and JSON record whether defaults
were applied.

Training best checkpoints are scoped to a scenario signature. If the network,
algorithm, seed, route coordinates, or other signature inputs differ, that is
a separate profile and it will not reuse the previous profile's best.

## Test command

From the repository root:

```bash
python -m unittest discover -s tests -v
```
