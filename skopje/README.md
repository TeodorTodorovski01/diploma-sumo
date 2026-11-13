# Skopje SUMO networks

This directory contains a wider Skopje road network derived from
[OpenStreetMap](https://www.openstreetmap.org/) data and a smaller editable
network used for routing-parameter training.

## Network files

| File | Purpose |
|---|---|
| `map.osm` | OpenStreetMap source extract. |
| `net.net.xml.gz` | Full Skopje SUMO road network. |
| `skopje.sumocfg` | SUMO configuration for the full network. |
| `skopjelite.net.xml` | Smaller editable Skopje network. |
| `skopjelite.sumocfg` | SUMO configuration for the Lite network. |

The full network is clipped to this bounding box:

- West: longitude `21.3000`
- South: latitude `41.9000`
- East: longitude `21.5500`
- North: latitude `42.1000`

Road segments are clipped at the selected boundary. The network retains
vehicle-accessible roads and omits roads for pedestrians only.

## Open a network

From this directory, open either network directly in SUMO-GUI:

```bash
sumo-gui -c skopje.sumocfg
sumo-gui -c skopjelite.sumocfg
```

To generate passenger traffic, create an ambulance route, and run a scenario,
use the repository-root entry point:

```bash
python centar/scenario.py --map skopje --gui
python centar/scenario.py --map skopjelite --gui
```

For example, set a route using latitude then longitude and disable the
simulated blockage:

```bash
python centar/scenario.py --map skopje --gui \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 0 --duration 1800 --accident-probability 0
```

The coordinate-based route search selects connected, emergency-accessible
roads within 250 meters. Edge IDs may be used instead with
`--ambulance-from EDGE_ID --ambulance-to EDGE_ID`. Omitting both start and
destination options generates a seeded long route. Outputs default to
`scenario-output/` under this directory.

See the [project wiki](../wiki/Home.md) for all commands, options, routing
behavior, function descriptions, and output formats.

## Rebuild the full network

With SUMO and `netconvert` installed, run from this directory:

```bash
netconvert --osm-files map.osm --output-file net.net.xml \
  --tls.guess-signals --junctions.join --geometry.remove \
  --keep-edges.by-vclass=passenger,emergency \
  --keep-edges.in-geo-boundary=21.30,41.90,21.55,42.10 \
  --keep-edges.postload
gzip -9 net.net.xml
```

This rebuilds the full network from `map.osm`. It does not rebuild the
separately prepared `skopjelite.net.xml`.

## Attribution

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
