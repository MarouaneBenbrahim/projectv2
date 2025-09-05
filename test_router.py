# test_router.py
from manhattan_vehicle_router import RouterService

# Initialize router
router = RouterService("data/manhattan_real.net.xml")

# Test pathfinding
test_edges = list(router.net.getEdges())[:10]
start = test_edges[0].getID()
end = test_edges[9].getID()

path, distance = router.find_shortest_path(start, end)
print(f"✅ Path found: {len(path)} edges, {distance:.1f}m total")

# Test vehicle creation
vehicle = router.create_smart_vehicle("test_ev_001", start, end)
print(f"✅ Created {vehicle['type']}: {vehicle['battery_percent']:.1f}% battery")
if vehicle['needs_charging']:
    print(f"   ⚡ Needs charging at {vehicle['charging_station']}")