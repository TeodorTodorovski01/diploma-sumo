import argparse
import copy
import time
import traci
import sumolib
import networkx as nx

# GUI runs use normal signal cycles by default; --preempt opts in to ambulance priority.
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

GUI = options.gui
PREEMPT = options.preempt or not options.no_preempt and not GUI
OWN_ROUTE = not options.sumo_route
# DIST [m] preemption, REPLAN [s] preracunuvanje
AMB, DIST, REPLAN = "amb0", 120, 30
# [s] kazna za semafor na kraj od ulica
TLS_PENALTY = 0 if PREEMPT else 15
GREEN_SECONDS = options.green_seconds
RED_SECONDS = options.red_seconds

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
EDGES = {e.getID(): e for e in net.getEdges() if e.allows("emergency")}


def weight(eid):
    """Estimate the cost of a road edge in seconds using its current travel time."""
    w = traci.edge.getTraveltime(eid)
    if EDGES[eid].getToNode().getType() == "traffic_light":
        w += TLS_PENALTY
    return w


def plan(src, dst):
    """Find the least-cost sequence of emergency-accessible road edges."""
    G = nx.DiGraph()
    for eid, e in EDGES.items():
        w = weight(eid)
        for o in e.getOutgoing():
            if o.getID() in EDGES:
                G.add_edge(eid, o.getID(), w=w)
    return nx.shortest_path(G, src, dst, weight="w")


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
    if not PREEMPT:
        set_normal_signal_cycles(GREEN_SECONDS, RED_SECONDS)
    t0 = dst = None
    last_plan, tracking = -1e9, False
    # Advance SUMO one step at a time so routes and signals can be adjusted live.
    while (traci.simulation.getMinExpectedNumber() > 0
           and (options.end_time is None
                or traci.simulation.getTime() < options.end_time)):
        traci.simulationStep()
        t = traci.simulation.getTime()
        if GUI and t >= 295:
            time.sleep(0.1)

        if AMB in traci.simulation.getArrivedIDList():
            print(f"{AMB}: duration = {t - t0:.0f} s  [{tag}]")
            if options.end_time is None:
                return
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
                    path = plan(cur, dst)
                    traci.vehicle.setRoute(AMB, path)
                    print(f"t={t:.0f}: tvoja ruta {len(path)} ulici")
                except (nx.NetworkXException, traci.TraCIException) as ex:
                    print("plan neuspesen:", ex)
                last_plan = t

        if PREEMPT:
            preempt(t)


while True:
    run_once()
    # Batch runs stop automatically; GUI runs can be restarted interactively.
    if not GUI or input("Enter = pak, q = izlez: ").strip().lower() == "q":
        break
    traci.load(args)
traci.close()
