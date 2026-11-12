import random, sumolib
random.seed(1)
net = sumolib.net.readNet("net.net.xml")
edges = [e for e in net.getEdges() if e.allows("passenger") and e.getLength() > 50]
best = None
for _ in range(300):
    a, b = random.sample(edges, 2)
    path, cost = net.getShortestPath(a, b)
    if path and (best is None or cost > best[2]):
        best = (a, b, cost)
a, b, cost = best
print("amb:", a.getID(), "->", b.getID(), "~", round(cost), "s")
with open("amb.rou.xml", "w") as f:
    f.write(f'''<routes>
  <vType id="amb" vClass="emergency" guiShape="emergency" speedFactor="1.3" color="1,0,0">
    <param key="has.bluelight.device" value="true"/>
  </vType>
  <trip id="amb0" type="amb" depart="300" from="{a.getID()}" to="{b.getID()}"/>
</routes>''')
