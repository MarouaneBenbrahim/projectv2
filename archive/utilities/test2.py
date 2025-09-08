# test3.py - Verify the real Manhattan network
import sumolib

net = sumolib.net.readNet('data/manhattan_real.net.xml')
print(f"✅ Real Manhattan Network Loaded!")
print(f"   - Edges: {len(net.getEdges())}")
print(f"   - Nodes: {len(net.getNodes())}")
print(f"   - Traffic Lights: {len(net.getTrafficLights())}")

# Check sample edges
edges = list(net.getEdges())[:10]
print("\n📍 Sample Street Segments:")
for e in edges:
    edge_id = e.getID()
    lanes = e.getLaneNumber()
    length = e.getLength()
    speed = e.getSpeed()
    print(f"   {edge_id}: {lanes} lanes, {length:.1f}m, {speed:.1f}m/s")

# Find some major streets (if they exist in the data)
print("\n🏙️ Looking for major Manhattan streets...")
for e in net.getEdges():
    edge_name = e.getID()
    if any(street in edge_name for street in ['Broadway', '42nd', '5th', 'Park', 'Times']):
        print(f"   Found: {edge_name}")
        if len([e for e in net.getEdges() if street in e.getID()]) >= 3:
            break  # Just show a few examples