import argparse
import copy
import json
import math
from pathlib import Path
import time
import traci
import sumolib
import networkx as nx
from route_pdf import write_route_pdf
from search_defaults import load_search_defaults
from smart_city import EdgeTrafficMetric, collect_smart_city_metrics

# GUI runs use normal signal cycles by default; --preempt opts in to ambulance priority.
search_defaults = load_search_defaults()
parser = argparse.ArgumentParser(
    description="Run the ambulance SUMO simulation."
)
parser.add_argument("--gui", action="store_true")
signal_group = parser.add_mutually_exclusive_group()
signal_group.add_argument("--preempt", action="store_true")
signal_group.add_argument("--no-preempt", action="store_true")
parser.add_argument("--sumo-route", action="store_true")
parser.add_argument("--passenger-routes")
parser.add_argument("--ambulance-route", default="amb.rou.xml")
parser.add_argument("--config-file", default="run.sumocfg")
parser.add_argument("--network-file", default="net.net.xml")
parser.add_argument("--tripinfo-output")
parser.add_argument("--route-pdf", default="ambulance-route.pdf")
parser.add_argument("--map-name")
parser.add_argument(
    "--search-algorithm",
    choices=("dijkstra", "astar"),
    default=search_defaults.search_algorithm,
)
parser.add_argument(
    "--replan-interval", type=float, default=search_defaults.replan_interval)
parser.add_argument(
    "--traffic-light-penalty", type=float,
    default=search_defaults.traffic_light_penalty,
)
parser.add_argument(
    "--astar-heuristic-weight", type=float,
    default=search_defaults.astar_heuristic_weight,
)
parser.add_argument("--scenario-parameters", type=json.loads, default={})
parser.add_argument("--end-time", type=float)
parser.add_argument(
    "--green-seconds", type=float, default=25,
    help="green/red cycle setting; combined with --red-seconds (default: 25)",
)
parser.add_argument(
    "--red-seconds", type=float, default=25,
    help="red/green cycle setting; combined with --green-seconds (default: 25)",
)
options = parser.parse_args()

if not math.isfinite(options.replan_interval) or options.replan_interval <= 0:
    parser.error("--replan-interval must be a finite value greater than zero")
if (options.traffic_light_penalty is not None
        and (not math.isfinite(options.traffic_light_penalty)
             or options.traffic_light_penalty < 0)):
    parser.error("--traffic-light-penalty must be finite and non-negative")
if (not math.isfinite(options.astar_heuristic_weight)
        or options.astar_heuristic_weight < 0):
    parser.error("--astar-heuristic-weight must be finite and non-negative")
if not isinstance(options.scenario_parameters, dict):
    parser.error("--scenario-parameters must be a JSON object")

GUI = options.gui
PREEMPT = options.preempt or not options.no_preempt and not GUI
OWN_ROUTE = not options.sumo_route
# DIST [m] preemption, REPLAN [s] preracunuvanje
AMB, DIST = "amb0", 120
REPLAN = options.replan_interval
# [s] kazna za semafor na kraj od ulica
TLS_PENALTY = (
    options.traffic_light_penalty
    if options.traffic_light_penalty is not None
    else 0 if PREEMPT else 15
)
GREEN_SECONDS = options.green_seconds
RED_SECONDS = options.red_seconds
SEARCH_ALGORITHM = options.search_algorithm
ASTAR_HEURISTIC_WEIGHT = options.astar_heuristic_weight
AMBULANCE_SPEED_FACTOR = 1.3
SMART_CITY_SAMPLE_INTERVAL = 30.0

tag = ("own" if OWN_ROUTE else "sumo") + \
    ("_preempt" if PREEMPT else "_nopreempt")
args = ["-c", options.config_file, "--no-step-log",
        "--tripinfo-output", options.tripinfo_output or f"tripinfo_{tag}.xml"]
if options.passenger_routes:
    args += [
        "--route-files",
        f"{options.passenger_routes},{options.ambulance_route}",
    ]
if options.end_time is not None:
    args += ["--end", str(options.end_time)]
if GUI:
    args += ["--start", "--delay", "0"]
traci.start(["sumo-gui" if GUI else "sumo"] + args)

# The routing graph uses road edges as nodes. A graph link means SUMO allows
# the ambulance to drive directly from one road edge to the next.
net = sumolib.net.readNet(options.network_file)
ALL_EDGES = {e.getID(): e for e in net.getEdges()}
EDGES = {eid: edge for eid, edge in ALL_EDGES.items()
         if edge.allows("emergency")}
MAP_NAME = options.map_name or Path.cwd().name.title() or "City network"
MAX_AMBULANCE_SPEED = max(
    (
        lane.getSpeed() * AMBULANCE_SPEED_FACTOR
        for edge in EDGES.values()
        for lane in edge.getLanes()
    ),
    default=0.0,
)


def weight(eid):
    """Estimate the cost of a road edge in seconds using its current travel time."""
    w = traci.edge.getTraveltime(eid)
    if EDGES[eid].getToNode().getType() == "traffic_light":
        w += TLS_PENALTY
    return w


def build_routing_graph():
    G = nx.DiGraph()
    for eid, e in EDGES.items():
        w = weight(eid)
        G.add_node(eid, cost=w)
        for o in e.getOutgoing():
            if o.getID() in EDGES:
                G.add_edge(eid, o.getID(), w=w)
    return G


def plan(G, src, dst, algorithm):
    """Find the least-cost sequence of emergency-accessible road edges."""
    if algorithm == "dijkstra":
        return nx.shortest_path(
            G, src, dst, weight="w", method="dijkstra"
        )
    if MAX_AMBULANCE_SPEED <= 0:
        raise RuntimeError("A* requires a positive emergency-road speed limit.")

    def heuristic(edge_id, destination_id):
        source = EDGES[edge_id].getToNode().getCoord()
        destination = EDGES[destination_id].getFromNode().getCoord()
        distance = math.hypot(
            source[0] - destination[0],
            source[1] - destination[1],
        )
        return (
            distance / MAX_AMBULANCE_SPEED * ASTAR_HEURISTIC_WEIGHT
        )

    return nx.astar_path(
        G, src, dst, heuristic=heuristic, weight="w"
    )


def set_normal_signal_cycles(green_seconds, red_seconds):
    """Fit the requested green/red cycle while preserving yellow clearances."""
    cycle_seconds = green_seconds + red_seconds
    for tls in traci.trafficlight.getIDList():
        program = traci.trafficlight.getProgram(tls)
        logic = next(
            (item for item in traci.trafficlight.getAllProgramLogics(tls)
             if item.programID == program),
            None,
        )
        if logic is None:
            raise RuntimeError(f"No active signal program found for {tls}")

        green_phase_indices = [
            index for index, phase in enumerate(logic.phases)
            if any(state in "Gg" for state in phase.state)
            and not any(state in "yY" for state in phase.state)
        ]
        green_duration = sum(
            logic.phases[index].duration for index in green_phase_indices)
        fixed_duration = sum(
            phase.duration for index, phase in enumerate(logic.phases)
            if index not in green_phase_indices
        )
        target_green_duration = cycle_seconds - fixed_duration
        if (green_seconds <= 0 or red_seconds <= 0 or not green_phase_indices
                or green_duration <= 0 or target_green_duration <= 0):
            raise RuntimeError(
                f"Cannot fit the requested cycle into the signal program for {tls}")

        updated_logic = copy.deepcopy(logic)
        scale = target_green_duration / green_duration
        for index in green_phase_indices:
            updated_logic.phases[index].duration *= scale
        traci.trafficlight.setProgramLogic(tls, updated_logic)


# ---------- preemption ----------
cache = {}


def green_phase(tls, link):
    """Find and cache the signal program phase that gives this link a green."""
    if (tls, link) not in cache:
        logic = traci.trafficlight.getAllProgramLogics(tls)[0]
        cache[(tls, link)] = next(
            (i for i, p in enumerate(logic.phases) if p.state[link] in "Gg"), None)
    return cache[(tls, link)]


def preempt(t):
    """When the ambulance is close to a signal, request a short green phase."""
    for tls, link, dist, state in traci.vehicle.getNextTLS(AMB):
        if dist > DIST:
            continue
        if state in "Gg":
            if traci.trafficlight.getNextSwitch(tls) - t < 5:
                traci.trafficlight.setPhaseDuration(tls, 5)
        else:
            ph = green_phase(tls, link)
            if ph is not None:
                traci.trafficlight.setPhase(tls, ph)
                traci.trafficlight.setPhaseDuration(tls, 5)

# ---------- eden tek na simulacija ----------


def run_once():
    run_started_at = time.perf_counter()
    if not PREEMPT:
        set_normal_signal_cycles(GREEN_SECONDS, RED_SECONDS)
    t0 = dst = None
    ambulance_trip_seconds = None
    optimal_estimated_seconds = None
    last_plan, tracking = -1e9, False
    traversed_edges = []
    traffic_metrics: dict[str, EdgeTrafficMetric] = {}
    traffic_sample_count = 0
    last_traffic_sample = -SMART_CITY_SAMPLE_INTERVAL
    # Advance SUMO one step at a time so routes and signals can be adjusted live.
    while (traci.simulation.getMinExpectedNumber() > 0
           and (options.end_time is None
                or traci.simulation.getTime() < options.end_time)):
        traci.simulationStep()
        t = traci.simulation.getTime()
        if t - last_traffic_sample >= max(SMART_CITY_SAMPLE_INTERVAL, REPLAN):
            active_edge_ids = set()
            for vehicle_id in traci.vehicle.getIDList():
                edge_id = traci.vehicle.getRoadID(vehicle_id)
                if edge_id in EDGES:
                    active_edge_ids.add(edge_id)
            traffic_metrics = collect_smart_city_metrics(
                active_edge_ids,
                traffic_metrics,
                traci.edge.getLastStepOccupancy,
                traci.edge.getWaitingTime,
            )
            traffic_sample_count += 1
            last_traffic_sample = t
        if AMB in traci.vehicle.getIDList():
            road_id = traci.vehicle.getRoadID(AMB)
            if road_id in EDGES and (
                not traversed_edges or traversed_edges[-1] != road_id
            ):
                traversed_edges.append(road_id)
        if GUI and t >= 295:
            time.sleep(0.1)

        if AMB in traci.simulation.getArrivedIDList():
            if t0 is not None:
                ambulance_trip_seconds = t - t0
                print(f"{AMB}: duration = {ambulance_trip_seconds:.0f} s  [{tag}]")
            if options.end_time is None:
                break
        if AMB not in traci.vehicle.getIDList():
            continue
        if traci.vehicle.getSpeed(AMB) < 0.5 and int(t) % 10 == 0:
            head, n = AMB, 0
            while n < 50:
                ld = traci.vehicle.getLeader(head, 100)
                if not ld:
                    break
                head, n = ld[0], n + 1
            print(f"t={t:.0f} kolona={n} glava={head} lane={traci.vehicle.getLaneID(head)} "
                  f"v={traci.vehicle.getSpeed(head):.1f} wait={traci.vehicle.getWaitingTime(head):.0f} "
                  f"nextTLS={traci.vehicle.getNextTLS(head)[:1]}")

        if t0 is None:                            # First step where the ambulance is present.
            t0 = t
            sumo_route = traci.vehicle.getRoute(AMB)
            # Keep the original route's destination even when using our own route.
            dst = sumo_route[-1]
            print(f"SUMO ruta: {len(sumo_route)} ulici")
        if GUI and not tracking:
            traci.gui.trackVehicle("View #0", AMB)
            traci.gui.setZoom("View #0", 1500)
            tracking = True

        # Recompute periodically using current edge travel times, not just at departure.
        if OWN_ROUTE and t - last_plan >= REPLAN:
            cur = traci.vehicle.getRoadID(AMB)
            if cur in EDGES and cur != dst:
                try:
                    graph = build_routing_graph()
                    dijkstra_path = None
                    if optimal_estimated_seconds is None:
                        dijkstra_path = plan(
                            graph, cur, dst, "dijkstra"
                        )
                        optimal_estimated_seconds = sum(
                            graph.nodes[edge_id]["cost"]
                            for edge_id in dijkstra_path
                        )
                    path = (
                        dijkstra_path
                        if SEARCH_ALGORITHM == "dijkstra" and dijkstra_path
                        else plan(graph, cur, dst, SEARCH_ALGORITHM)
                    )
                    traci.vehicle.setRoute(AMB, path)
                    print(f"t={t:.0f}: tvoja ruta {len(path)} ulici")
                except (nx.NetworkXException, traci.TraCIException) as ex:
                    print("plan neuspesen:", ex)
                last_plan = t

        if PREEMPT:
            preempt(t)

    if traversed_edges:
        if ambulance_trip_seconds is not None:
            measured_trip = f"{ambulance_trip_seconds:.1f} simulation s"
        elif t0 is not None:
            elapsed = max(0, traci.simulation.getTime() - t0)
            measured_trip = f"incomplete; {elapsed:.1f} simulation s elapsed"
        else:
            measured_trip = "not started"
        pdf_parameters = {
            "Search algorithm": SEARCH_ALGORITHM.upper(),
            "Route objective": "Estimated travel time",
            "Replan interval": f"{REPLAN:g} s",
            "Traffic-light penalty": f"{TLS_PENALTY:g} s",
            "A* heuristic weight": f"{ASTAR_HEURISTIC_WEIGHT:g}",
            "Recorded road segments": str(len(traversed_edges)),
            "SmartCity traffic samples": str(traffic_sample_count),
            "Peak road occupancy": (
                f"{max((value[0] for value in traffic_metrics.values()), default=0.0):.1f}%"
            ),
            "Peak summed edge waiting": (
                f"{max((value[1] for value in traffic_metrics.values()), default=0.0):.1f} s"
            ),
            "Simulation wall time": f"{time.perf_counter() - run_started_at:.2f} s",
            "Measured ambulance trip": measured_trip,
            "Initial Dijkstra-optimal ETA": (
                f"{optimal_estimated_seconds:.1f} simulation s"
                if optimal_estimated_seconds is not None else "unavailable"
            ),
            **options.scenario_parameters,
        }
        pdf_path = write_route_pdf(
            net,
            traversed_edges,
            Path(options.route_pdf),
            MAP_NAME,
            pdf_parameters,
            traffic_metrics=traffic_metrics,
        )
        print(f"Ambulance route PDF: {pdf_path.resolve()}")
    else:
        print("No ambulance road segments were recorded; route PDF not created.")


while True:
    run_once()
    # Batch runs stop automatically; GUI runs can be restarted interactively.
    if not GUI or input("Enter = pak, q = izlez: ").strip().lower() == "q":
        break
    traci.load(args)
traci.close()
