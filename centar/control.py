import sys, time, traci, sumolib, networkx as nx

PREEMPT   = "--no-preempt" not in sys.argv   # semafori na ruta -> zeleno
OWN_ROUTE = "--sumo-route" not in sys.argv   # tvoja ruta namesto SUMO-va
GUI       = "--gui" in sys.argv
AMB, DIST, REPLAN = "amb0", 120, 30          # DIST [m] preemption, REPLAN [s] preracunuvanje
TLS_PENALTY = 0 if PREEMPT else 15           # [s] kazna za semafor na kraj od ulica

tag = ("own" if OWN_ROUTE else "sumo") + ("_preempt" if PREEMPT else "_nopreempt")
args = ["-c", "run.sumocfg", "--no-step-log", "--tripinfo-output", f"tripinfo_{tag}.xml"]
if GUI:
    args += ["--start", "--delay", "0"]
traci.start(["sumo-gui" if GUI else "sumo"] + args)

# ---------- graf (cvor = ulica/edge, luk = dozvolen prevoj) ----------
net = sumolib.net.readNet("net.net.xml")
EDGES = {e.getID(): e for e in net.getEdges() if e.allows("emergency")}

def weight(eid):
    """TEZINA NA ULICA [s]: ovde dodavas guzva, vreme od denot, stepen na itnost..."""
    w = traci.edge.getTraveltime(eid)             # momentalno vreme na patuvanje
    if EDGES[eid].getToNode().getType() == "traffic_light":
        w += TLS_PENALTY
    return w

def plan(src, dst):
    G = nx.DiGraph()
    for eid, e in EDGES.items():
        w = weight(eid)
        for o in e.getOutgoing():
            if o.getID() in EDGES:
                G.add_edge(eid, o.getID(), w=w)
    return nx.shortest_path(G, src, dst, weight="w")

# ---------- preemption ----------
cache = {}
def green_phase(tls, link):
    if (tls, link) not in cache:
        logic = traci.trafficlight.getAllProgramLogics(tls)[0]
        cache[(tls, link)] = next(
            (i for i, p in enumerate(logic.phases) if p.state[link] in "Gg"), None)
    return cache[(tls, link)]

def preempt(t):
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
    t0 = dst = None
    last_plan, tracking = -1e9, False
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        t = traci.simulation.getTime()
        if GUI and t >= 295:
            time.sleep(0.1)

        if AMB in traci.simulation.getArrivedIDList():
            print(f"{AMB}: duration = {t - t0:.0f} s  [{tag}]")
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

        if t0 is None:                            # prv cekor na ambulantata
            t0 = t
            sumo_route = traci.vehicle.getRoute(AMB)
            dst = sumo_route[-1]
            print(f"SUMO ruta: {len(sumo_route)} ulici")
        if GUI and not tracking:
            traci.gui.trackVehicle("View #0", AMB)
            traci.gui.setZoom("View #0", 1500)
            tracking = True

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
    if not GUI or input("Enter = pak, q = izlez: ").strip().lower() == "q":
        break
    traci.load(args)
traci.close()
