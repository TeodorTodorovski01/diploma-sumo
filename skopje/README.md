# Skopje SUMO map

This folder contains a SUMO road network for the wider urban area of Skopje,
generated from the [Geofabrik North Macedonia OpenStreetMap extract](https://download.geofabrik.de/europe/macedonia.html).
The SUMO network is clipped to this bounding box:

- West: 21.3000
- South: 41.9000
- East: 21.5500
- North: 42.1000

## Files

- `map.osm` - OpenStreetMap road ways and their nodes.
- `net.net.xml.gz` - Compressed SUMO network converted from the OSM data.
- `skopje.sumocfg` - SUMO configuration for opening the map.

Road segments are clipped at the selected area boundary. The network retains
vehicle-accessible roads and omits roads that are for pedestrians only.

Open the network in SUMO-GUI from this directory:

```bash
sumo-gui -c skopje.sumocfg
```

The network contains roads and traffic lights. Generate passenger traffic and
a long emergency-vehicle route, then run them together in SUMO-GUI from the
`centar` directory:

```bash
python scenario.py --map skopje --gui
```

The generated scenario files are saved in `skopje/scenario-output/`. For
example, choose the number of passenger vehicles and disable simulated
blockages:

```bash
python scenario.py --map skopje --gui --vehicles 1200 --accident-probability 0
```

To start the ambulance at specific map coordinates, enter each location as
latitude followed by longitude. From the repository root, run:

```bash
source venv/bin/activate
export SUMO_HOME="$PWD/venv/lib64/python3.15/site-packages/sumo"
python centar/scenario.py --map skopje --gui \
  --ambulance-from-coordinates 41.976343 21.549497 \
  --ambulance-to-coordinates 42.006512 21.402385 \
  --ambulance-depart 0 \
  --duration 1800 \
  --accident-probability 0
```

The generator picks nearby emergency-accessible roads that have a connecting
route; coordinate searches include roads up to 250 meters away. Alternatively,
use `--ambulance-from EDGE_ID` and `--ambulance-to EDGE_ID` to enter edge IDs
directly. If you omit both start and destination options, it chooses a long
random route. The generated route is saved in
`skopje/scenario-output/ambulance.rou.xml`.

## Data attribution

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).

## Rebuild the SUMO network

With SUMO and `netconvert` installed:

```bash
netconvert --osm-files map.osm --output-file net.net.xml \
  --tls.guess-signals --junctions.join --geometry.remove \
  --keep-edges.by-vclass=passenger,emergency \
  --keep-edges.in-geo-boundary=21.30,41.90,21.55,42.10 \
  --keep-edges.postload
gzip -9 net.net.xml
```
