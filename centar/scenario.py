"""Generate and run a configurable SUMO traffic scenario.

Example:
    python scenario.py --map skopje --vehicles 1200 --accident-probability 20 --gui
"""

import argparse
import importlib.util
import os
import random
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def find_sumo_tools() -> Path:
    candidates: list[Path] = []
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        home = Path(sumo_home).expanduser()
        candidates.extend((home / "tools", home))

    try:
        import sumolib
    except ImportError:
        pass
    else:
        candidates.append(Path(sumolib.__file__).resolve().parent.parent)

    sumo_spec = importlib.util.find_spec("sumo")
    if sumo_spec and sumo_spec.submodule_search_locations:
        for package_dir in sumo_spec.submodule_search_locations:
            candidates.append(Path(package_dir) / "tools")

    sumo_executable = shutil.which("sumo")
    if sumo_executable:
        install_root = Path(sumo_executable).resolve().parent.parent
        candidates.extend((
            install_root / "tools",
            install_root / "share" / "sumo" / "tools",
        ))

    candidates.extend((
        Path("/usr/share/sumo/tools"),
        Path("/usr/local/share/sumo/tools"),
        Path("/usr/lib/sumo/tools"),
        Path("/usr/lib64/sumo/tools"),
        Path("/opt/sumo/tools"),
    ))

    checked = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in checked:
            continue
        checked.add(candidate)
        if (candidate / "randomTrips.py").is_file():
            return candidate
    raise RuntimeError(
        "Cannot find SUMO's randomTrips.py tools. Install SUMO, or set SUMO_HOME "
        "to its installation directory (for example, /usr/share/sumo)."
    )


def add_random_blockage(
    route_file: Path,
    network_file: Path,
    ambulance_file: Path,
    seed: int,
    duration: float,
) -> str:
    import sumolib

    rng = random.Random(seed)
    net = sumolib.net.readNet(str(network_file))
    tree = ET.parse(route_file)
    root = tree.getroot()
    ambulance_root = ET.parse(ambulance_file).getroot()
    ambulance = next(
        (vehicle for vehicle in ambulance_root if vehicle.get("id") == "amb0"),
        None,
    )
    if ambulance is None:
        raise RuntimeError(f"Could not find ambulance 'amb0' in {ambulance_file}")
    ambulance_depart = float(ambulance.get("depart", "0"))
    candidates = []

    for vehicle in root.findall("vehicle"):
        if float(vehicle.get("depart", "0")) >= ambulance_depart:
            continue
        route = vehicle.find("route")
        if route is None:
            continue
        for edge_id in route.get("edges", "").split():
            try:
                edge = net.getEdge(edge_id)
            except KeyError:
                continue
            lanes = [
                lane for lane in edge.getLanes()
                if lane.allows("passenger") and lane.getLength() >= 20
            ]
            if lanes:
                candidates.append((
                    vehicle,
                    rng.choice(lanes),
                    float(vehicle.get("depart", "0")),
                ))
                break

    if not candidates:
        raise RuntimeError("Could not find a passenger vehicle route suitable for a blockage.")

    latest_depart = max(depart for _, _, depart in candidates)
    latest_vehicles = [
        candidate for candidate in candidates
        if abs(candidate[2] - latest_depart) < 1e-6
    ]
    vehicle, lane, _ = rng.choice(latest_vehicles)
    position = min(lane.getLength() - 5, max(5, lane.getLength() / 2))
    vehicle.set("color", "255,0,0")
    vehicle.append(ET.Element("stop", {
        "lane": lane.getID(),
        "endPos": f"{position:.2f}",
        "duration": str(duration),
    }))
    tree.write(route_file, encoding="UTF-8", xml_declaration=True)
    return vehicle.get("id", "unknown")


def generate_ambulance_route(
    network_file: Path,
    route_file: Path,
    seed: int,
    depart: float = 300,
    source_id: str | None = None,
    destination_id: str | None = None,
    source_coordinates: tuple[float, float] | None = None,
    destination_coordinates: tuple[float, float] | None = None,
) -> tuple[str, str, int]:
    import sumolib

    net = sumolib.net.readNet(str(network_file))
    if source_id is not None and destination_id is not None:
        try:
            source = net.getEdge(source_id)
            destination = net.getEdge(destination_id)
        except KeyError as error:
            raise RuntimeError(
                f"Ambulance edge {error.args[0]!r} does not exist in {network_file}"
            ) from error
        for edge_id, edge in ((source_id, source), (destination_id, destination)):
            if not edge.allows("emergency"):
                raise RuntimeError(
                    f"Ambulance edge {edge_id!r} is not accessible to emergency vehicles"
                )
        path, _ = net.getShortestPath(source, destination, vClass="emergency")
        if not path:
            raise RuntimeError(
                f"No emergency-vehicle route connects {source_id!r} to "
                f"{destination_id!r} in {network_file}"
            )
    elif source_coordinates is not None and destination_coordinates is not None:
        def nearby_edges(coordinates: tuple[float, float]):
            latitude, longitude = coordinates
            x, y = net.convertLonLat2XY(longitude, latitude)
            return sorted(
                (
                    (distance, edge)
                    for edge, distance in net.getNeighboringEdges(x, y, 250)
                    if edge.allows("emergency")
                ),
                key=lambda item: item[0],
            )

        source_candidates = nearby_edges(source_coordinates)
        destination_candidates = nearby_edges(destination_coordinates)
        if not source_candidates or not destination_candidates:
            raise RuntimeError(
                "Could not find an emergency-accessible road within 250 meters "
                "of both ambulance coordinates"
            )

        candidate_pairs = [
            (source_distance + destination_distance, source_distance,
             destination_distance, source, destination)
            for source_distance, source in source_candidates
            for destination_distance, destination in destination_candidates
        ]
        candidate_pairs.sort(key=lambda candidate: candidate[0])
        selected_path = None
        for _, _, _, source, destination in candidate_pairs:
            path, _ = net.getShortestPath(
                source, destination, vClass="emergency"
            )
            if path:
                selected_path = source, destination, path
                break
        if selected_path is None:
            raise RuntimeError(
                "No emergency-vehicle route connects roads near the specified "
                "ambulance coordinates"
            )
        source, destination, path = selected_path
        source_id, destination_id = source.getID(), destination.getID()
    else:
        edges = [
            edge for edge in net.getEdges()
            if edge.allows("emergency") and edge.getLength() >= 100
        ]
        if len(edges) < 2:
            raise RuntimeError(
                f"Not enough emergency-accessible roads in {network_file}"
            )

        rng = random.Random(seed)
        selected_path = None
        for _ in range(500):
            source, destination = rng.sample(edges, 2)
            path, length = net.getShortestPath(
                source, destination, vClass="emergency"
            )
            if path and len(path) >= 30 and length >= 8_000:
                selected_path = source.getID(), destination.getID(), path
                break
        if selected_path is None:
            raise RuntimeError(
                f"Could not find a long, connected emergency-vehicle route in {network_file}"
            )

        source_id, destination_id, path = selected_path
    routes = ET.Element("routes")
    ET.SubElement(routes, "vType", {
        "id": "amb",
        "vClass": "emergency",
        "guiShape": "emergency",
        "speedFactor": "1.3",
        "color": "1,0,0",
    })
    vehicle = ET.SubElement(routes, "vehicle", {
        "id": "amb0",
        "type": "amb",
        "depart": str(depart),
    })
    ET.SubElement(vehicle, "param", {
        "key": "has.bluelight.device",
        "value": "true",
    })
    ET.SubElement(vehicle, "route", {
        "edges": " ".join(edge.getID() for edge in path),
    })
    ET.ElementTree(routes).write(route_file, encoding="UTF-8", xml_declaration=True)
    return source_id, destination_id, len(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate passenger traffic and run a configurable SUMO scenario."
    )
    parser.add_argument(
        "--map", choices=("centar", "skopje"), default="centar",
        help="road network to simulate (default: centar)",
    )
    parser.add_argument("--vehicles", type=int, default=1200,
                        help="number of passenger vehicles to generate (default: 1200)")
    parser.add_argument("--duration", type=float, default=1800,
                        help="traffic generation and maximum simulation time in seconds (default: 1800)")
    parser.add_argument(
        "--ambulance-from",
        help="Skopje network edge ID where the ambulance starts (default: random)",
    )
    parser.add_argument(
        "--ambulance-to",
        help="Skopje network edge ID where the ambulance ends (default: random)",
    )
    parser.add_argument(
        "--ambulance-from-coordinates",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        help="Skopje ambulance start coordinates in latitude, longitude order",
    )
    parser.add_argument(
        "--ambulance-to-coordinates",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        help="Skopje ambulance destination coordinates in latitude, longitude order",
    )
    parser.add_argument(
        "--ambulance-depart", type=float, default=300,
        help="ambulance departure time in seconds (default: 300)",
    )
    parser.add_argument("--accident-probability", type=float, default=20,
                        help="chance from 0 to 100%% of one stopped-vehicle blockage (default: 20)")
    parser.add_argument("--accident-duration", type=float, default=60,
                        help="blockage duration in seconds (default: 60)")
    parser.add_argument("--seed", type=int, default=1,
                        help="random seed for reproducible traffic and blockage (default: 1)")
    parser.add_argument(
        "--green-seconds", type=float, default=25,
        help="contribution to target full-cycle duration; combined with red seconds (default: 25)",
    )
    parser.add_argument(
        "--red-seconds", type=float, default=25,
        help="contribution to target full-cycle duration; yellow is preserved (default: 25)",
    )
    parser.add_argument("--output-dir", default="scenario-output",
                        help="directory for generated scenario files")
    parser.add_argument("--gui", action="store_true",
                        help="show the simulation in SUMO-GUI")
    signal_group = parser.add_mutually_exclusive_group()
    signal_group.add_argument("--preempt", action="store_true",
                              help="give the ambulance traffic-light priority")
    signal_group.add_argument("--no-preempt", action="store_true",
                              help="keep normal traffic-light cycles")
    options = parser.parse_args()

    if options.vehicles <= 0:
        parser.error("--vehicles must be greater than zero")
    if options.ambulance_depart < 0:
        parser.error("--ambulance-depart must be zero or greater")
    if options.duration <= options.ambulance_depart:
        parser.error("--duration must exceed --ambulance-depart")
    edge_options_set = (
        options.ambulance_from is not None or options.ambulance_to is not None
    )
    coordinate_options_set = (
        options.ambulance_from_coordinates is not None
        or options.ambulance_to_coordinates is not None
    )
    if (options.ambulance_from is None) != (options.ambulance_to is None):
        parser.error("--ambulance-from and --ambulance-to must be provided together")
    if (
        options.ambulance_from_coordinates is None
    ) != (
        options.ambulance_to_coordinates is None
    ):
        parser.error(
            "--ambulance-from-coordinates and --ambulance-to-coordinates "
            "must be provided together"
        )
    if edge_options_set and coordinate_options_set:
        parser.error(
            "Use either ambulance edge IDs or coordinate pairs, not both"
        )
    if options.map != "skopje" and (
        edge_options_set or coordinate_options_set or options.ambulance_depart != 300
    ):
        parser.error(
            "Ambulance start/destination options and --ambulance-depart "
            "are only supported with --map skopje"
        )
    if options.accident_duration <= 0:
        parser.error("--accident-duration must be greater than zero")
    if not 0 <= options.accident_probability <= 100:
        parser.error("--accident-probability must be between 0 and 100")
    if options.green_seconds <= 0 or options.red_seconds <= 0:
        parser.error("--green-seconds and --red-seconds must be greater than zero")
    return options


def main() -> None:
    options = parse_args()
    base_dir = Path(__file__).resolve().parent
    map_dir = base_dir if options.map == "centar" else base_dir.parent / "skopje"
    output_dir = Path(options.output_dir)
    if not output_dir.is_absolute():
        output_dir = map_dir / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    tools_dir = find_sumo_tools()
    sys.path.insert(0, str(tools_dir))
    child_env = os.environ.copy()
    existing_pythonpath = child_env.get("PYTHONPATH")
    child_env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(tools_dir), existing_pythonpath) if part
    )
    child_env["SUMO_HOME"] = str(tools_dir.parent)
    packaged_sumo_bin = tools_dir.parent / "bin"
    if packaged_sumo_bin.is_dir():
        child_env["PATH"] = os.pathsep.join((
            str(packaged_sumo_bin),
            child_env.get("PATH", ""),
        ))

    trips_file = output_dir / "passenger.trips.xml"
    routes_file = output_dir / "passenger.rou.xml"
    ambulance_file = (
        base_dir / "amb.rou.xml"
        if options.map == "centar"
        else output_dir / "ambulance.rou.xml"
    )
    tripinfo_file = output_dir / "tripinfo.xml"
    network_file = map_dir / (
        "net.net.xml" if options.map == "centar" else "net.net.xml.gz"
    )
    config_file = map_dir / (
        "run.sumocfg" if options.map == "centar" else "skopje.sumocfg"
    )
    random_trips = tools_dir / "randomTrips.py"
    period = options.duration / options.vehicles

    subprocess.run([
        sys.executable, str(random_trips),
        "-n", str(network_file),
        "-o", str(trips_file),
        "-r", str(routes_file),
        "-s", str(options.seed),
        "-b", "0",
        "-e", str(options.duration),
        "-p", str(period),
        "--vehicle-class", "passenger",
        "--validate",
    ], cwd=map_dir, env=child_env, check=True)

    route_root = ET.parse(routes_file).getroot()
    generated_count = sum(vehicle.tag == "vehicle" for vehicle in route_root)
    if generated_count != options.vehicles:
        raise RuntimeError(
            f"SUMO generated {generated_count} vehicles; requested {options.vehicles}."
        )

    if options.map == "skopje":
        source_id, destination_id, route_length = generate_ambulance_route(
            network_file,
            ambulance_file,
            options.seed + 2,
            depart=options.ambulance_depart,
            source_id=options.ambulance_from,
            destination_id=options.ambulance_to,
            source_coordinates=(
                tuple(options.ambulance_from_coordinates)
                if options.ambulance_from_coordinates is not None else None
            ),
            destination_coordinates=(
                tuple(options.ambulance_to_coordinates)
                if options.ambulance_to_coordinates is not None else None
            ),
        )
        print(
            f"Skopje ambulance route: {source_id} -> {destination_id} "
            f"({route_length} roads)."
        )

    accident_id = None
    if random.Random(options.seed + 1).random() < options.accident_probability / 100:
        accident_id = add_random_blockage(
            routes_file, network_file, ambulance_file,
            options.seed + 1, options.accident_duration
        )
        print(
            f"Scenario blockage: vehicle {accident_id} stops for "
            f"{options.accident_duration:g} seconds."
        )
    else:
        print("Scenario blockage: none.")

    command = [
        sys.executable, str(base_dir / "control.py"),
        "--config-file", str(config_file),
        "--network-file", str(network_file),
        "--ambulance-route", str(ambulance_file),
        "--passenger-routes", str(routes_file),
        "--tripinfo-output", str(tripinfo_file),
        "--end-time", str(options.duration),
        "--green-seconds", str(options.green_seconds),
        "--red-seconds", str(options.red_seconds),
    ]
    if options.gui:
        command.append("--gui")
    if options.preempt:
        command.append("--preempt")
    elif options.no_preempt:
        command.append("--no-preempt")

    print(f"Generated {generated_count} passenger vehicles (seed {options.seed}).")
    print(f"Scenario files: {output_dir}")
    subprocess.run(command, cwd=map_dir, env=child_env, check=True)


if __name__ == "__main__":
    main()
