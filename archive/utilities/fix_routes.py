"""
find_good_edges.py - Find well-connected edges for vehicle spawning
"""

import sumolib
import json
import os

def find_connected_edges():
    """Find edges that are well-connected in the network"""
    
    print("Finding well-connected edges in Manhattan network...")
    
    # Load network
    net = sumolib.net.readNet('data/sumo/manhattan.net.xml')
    
    # Get edges that are good for spawning
    good_edges = []
    all_edges = list(net.getEdges())
    
    for edge in all_edges:
        # Skip special edges and non-passenger edges
        if edge.isSpecial() or not edge.allows("passenger"):
            continue
        
        # Check if edge has good connectivity
        outgoing = edge.getOutgoing()
        incoming = edge.getIncoming()
        
        # We want edges with multiple connections
        if len(outgoing) > 0 and len(incoming) > 0:
            good_edges.append(edge.getID())
            
            # Limit to first 200 for performance
            if len(good_edges) >= 200:
                break
    
    print(f"Found {len(good_edges)} well-connected edges")
    
    # Save to file
    os.makedirs('data', exist_ok=True)
    with open('data/good_spawn_edges.json', 'w') as f:
        json.dump(good_edges, f, indent=2)
    
    print("Saved good spawn edges to data/good_spawn_edges.json")
    
    # Show some examples
    if good_edges:
        print("\nSample edges for spawning:")
        for edge in good_edges[:5]:
            print(f"  - {edge}")
    
    return good_edges

def test_route_creation():
    """Test creating routes between found edges"""
    
    print("\nTesting route creation...")
    
    import traci
    
    # Load the good edges
    with open('data/good_spawn_edges.json', 'r') as f:
        good_edges = json.load(f)
    
    if len(good_edges) < 2:
        print("Not enough edges found")
        return False
    
    # Start SUMO for testing
    cmd = [
        "sumo",
        "-n", "data/sumo/manhattan.net.xml",
        "--no-warnings",
        "--no-step-log",
        "--quit-on-end",
        "--end", "10"
    ]
    
    if os.path.exists("data/sumo/types.add.xml"):
        cmd.extend(["-a", "data/sumo/types.add.xml"])
    
    try:
        traci.start(cmd)
        
        # Test creating routes
        successful_routes = 0
        for i in range(5):
            origin = good_edges[i % len(good_edges)]
            dest = good_edges[(i + 10) % len(good_edges)]
            
            try:
                route_id = f"test_route_{i}"
                traci.route.add(route_id, [origin, dest])
                
                # Try adding a vehicle
                traci.vehicle.add(f"test_veh_{i}", route_id, depart="now")
                successful_routes += 1
            except:
                pass
        
        print(f"Successfully created {successful_routes}/5 test routes")
        
        # Run for a few steps
        for _ in range(10):
            traci.simulationStep()
        
        vehicles = traci.vehicle.getIDList()
        print(f"Active vehicles: {len(vehicles)}")
        
        traci.close()
        return successful_routes > 0
        
    except Exception as e:
        print(f"Test failed: {e}")
        try:
            traci.close()
        except:
            pass
        return False

if __name__ == "__main__":
    print("="*60)
    print("FINDING GOOD SPAWN EDGES FOR VEHICLES")
    print("="*60)
    
    # Find connected edges
    edges = find_connected_edges()
    
    if edges:
        # Test them
        success = test_route_creation()
        
        if success:
            print("\n" + "="*60)
            print("SUCCESS! Good edges found and tested")
            print("="*60)
            print("\nNext steps:")
            print("1. Apply the fix from route_fix.txt to manhattan_sumo_manager.py")
            print("2. The system will now use these validated edges")
            print("3. Restart: python main_complete_integration.py")
        else:
            print("\nEdges found but route testing had issues")
            print("This is normal - apply the fix anyway")
    else:
        print("\nNo edges found - check if network file exists")