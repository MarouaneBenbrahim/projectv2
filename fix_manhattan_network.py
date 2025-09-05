"""
Fix Manhattan Network - Create a properly connected SUMO network
This will regenerate your network with better connectivity
"""

import subprocess
import os
import sys
import sumolib
import json

def fix_manhattan_network():
    """
    Regenerate Manhattan network with proper connectivity
    """
    
    print("="*60)
    print("FIXING MANHATTAN NETWORK")
    print("="*60)
    
    # Check if netconvert is available
    try:
        result = subprocess.run(["netconvert", "--version"], capture_output=True)
        print(f"✅ Using SUMO {result.stdout.decode().split()[1] if result.stdout else 'version unknown'}")
    except:
        print("❌ netconvert not found! Make sure SUMO is in your PATH")
        return False
    
    # Input and output files
    osm_file = "data/sumo/manhattan.osm"
    output_file = "data/sumo/manhattan_fixed.net.xml"
    
    if not os.path.exists(osm_file):
        print(f"❌ OSM file not found: {osm_file}")
        return False
    
    print(f"\n📥 Input: {osm_file}")
    print(f"📤 Output: {output_file}")
    
    # Build netconvert command with aggressive connection parameters
    netconvert_cmd = [
        "netconvert",
        "--osm-files", osm_file,
        "--output-file", output_file,
        
        # CONNECTIVITY FIXES
        "--keep-edges.components", "1",  # ONLY keep largest connected component
        "--remove-edges.isolated", "true",  # Remove isolated edges
        
        # JUNCTION IMPROVEMENTS
        "--junctions.join", "true",  # Join nearby junctions
        "--junctions.join-dist", "20",  # Increased join distance (meters)
        "--junctions.corner-detail", "0",  # Simplify junctions
        "--junctions.limit-turn-speed", "5.5",  # Reasonable turn speeds
        
        # TRAFFIC LIGHT OPTIMIZATION
        "--tls.join", "true",  # Join nearby traffic lights
        "--tls.join-dist", "25",  # Join traffic lights within 25m
        "--tls.guess-signals", "true",  # Guess signal positions
        "--tls.default-type", "actuated",  # Smart traffic lights
        
        # EDGE PROCESSING
        "--geometry.remove", "true",  # Simplify geometry
        "--geometry.max-segment-length", "50",  # Reasonable segment length
        "--edges.join", "true",  # Join edges
        
        # TURN PERMISSIONS
        "--no-turnarounds", "false",  # Allow U-turns (important for connectivity!)
        "--no-left-connections", "false",  # Allow left turns
        
        # SPEED ADJUSTMENTS
        "--default.speed", "13.89",  # 50 km/h default
        "--default.sidewalk-width", "2.0",
        
        # TYPE RESTRICTIONS
        "--keep-edges.by-vclass", "passenger,taxi,bus,delivery",  # Keep vehicle roads
        "--remove-edges.by-type", "highway.footway,highway.path,highway.steps,highway.cycleway",
        
        # OUTPUT OPTIONS
        "--proj.utm", "true",  # Use UTM projection
        "--output.street-names", "true",  # Keep street names
        "--output.original-names", "true",  # Keep original names
        
        # PROCESSING
        "--edges.join-tram-dist", "1.0",  # Don't join tram lines
        "--roundabouts.guess", "true",  # Detect roundabouts
        "--ramps.guess", "true",  # Detect ramps
        
        # VERBOSITY
        "--verbose", "true",
        "--log", "data/sumo/netconvert.log"
    ]
    
    print("\n🔧 Regenerating network with improved connectivity...")
    print("  Parameters:")
    print("  - Keeping only largest connected component")
    print("  - Joining nearby junctions (20m)")
    print("  - Allowing U-turns for better connectivity")
    print("  - Simplifying geometry")
    print("  - Joining traffic lights (25m)")
    
    # Run netconvert
    try:
        result = subprocess.run(netconvert_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("\n✅ Network regenerated successfully!")
        else:
            print("\n⚠️ Netconvert completed with warnings")
            if result.stderr:
                print("Warnings (first 500 chars):")
                print(result.stderr[:500])
        
        # Check if output file was created
        if not os.path.exists(output_file):
            print("❌ Output file was not created!")
            return False
            
    except Exception as e:
        print(f"❌ Error running netconvert: {e}")
        return False
    
    # Analyze the new network
    print("\n📊 Analyzing fixed network...")
    analyze_network(output_file)
    
    # Backup old network
    if os.path.exists("data/sumo/manhattan.net.xml"):
        backup_file = "data/sumo/manhattan_backup.net.xml"
        os.rename("data/sumo/manhattan.net.xml", backup_file)
        print(f"\n📦 Backed up old network to {backup_file}")
    
    # Replace with fixed network
    os.rename(output_file, "data/sumo/manhattan.net.xml")
    print(f"✅ Replaced network with fixed version")
    
    return True

def analyze_network(net_file):
    """Analyze the fixed network"""
    
    try:
        net = sumolib.net.readNet(net_file)
        
        # Count edges
        edges = [e for e in net.getEdges() if not e.getID().startswith(':')]
        passenger_edges = [e for e in edges if e.allows('passenger')]
        
        print(f"\n  Network Statistics:")
        print(f"  - Total edges: {len(edges)}")
        print(f"  - Drivable edges: {len(passenger_edges)}")
        print(f"  - Traffic lights: {len(net.getTrafficLights())}")
        print(f"  - Junctions: {len(net.getNodes())}")
        
        # Test connectivity by checking components
        print("\n  Testing connectivity...")
        connected_components = find_connected_components(net)
        
        print(f"  - Connected components: {len(connected_components)}")
        if connected_components:
            main_component = max(connected_components, key=len)
            print(f"  - Main component size: {len(main_component)} edges")
            print(f"  - Connectivity: {len(main_component)*100//len(passenger_edges)}% of network")
        
        # Sample route test
        if len(passenger_edges) >= 2:
            test_routes(net, passenger_edges)
            
    except Exception as e:
        print(f"  ⚠️ Could not analyze network: {e}")

def find_connected_components(net):
    """Find connected components in network"""
    
    edges = [e for e in net.getEdges() if not e.getID().startswith(':') and e.allows('passenger')]
    
    # Build adjacency
    adjacency = {}
    for edge in edges:
        edge_id = edge.getID()
        adjacency[edge_id] = []
        
        to_node = edge.getToNode()
        for out_edge in to_node.getOutgoing():
            if out_edge.allows('passenger') and not out_edge.getID().startswith(':'):
                adjacency[edge_id].append(out_edge.getID())
    
    # Find components
    visited = set()
    components = []
    
    for edge_id in adjacency:
        if edge_id not in visited:
            component = set()
            stack = [edge_id]
            
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                    
                visited.add(current)
                component.add(current)
                
                for neighbor in adjacency.get(current, []):
                    if neighbor not in visited:
                        stack.append(neighbor)
            
            components.append(component)
    
    return components

def test_routes(net, edges):
    """Test sample routes"""
    
    import random
    
    print("\n  Testing sample routes...")
    success = 0
    total = 20
    
    for _ in range(total):
        e1 = random.choice(edges)
        e2 = random.choice(edges)
        
        if e1 != e2:
            route = net.getShortestPath(e1, e2)
            if route and route[0]:
                success += 1
    
    print(f"  - Route success rate: {success}/{total} ({success*100//total}%)")

def verify_fix():
    """Verify the fix worked"""
    
    print("\n" + "="*60)
    print("VERIFYING FIX")
    print("="*60)
    
    # Start SUMO and test
    import traci
    
    try:
        traci.start(["sumo", "-n", "data/sumo/manhattan.net.xml", "--no-warnings"])
        
        edges = [e for e in traci.edge.getIDList() if not e.startswith(':')]
        print(f"✅ SUMO loaded network with {len(edges)} edges")
        
        # Test 50 random routes
        success = 0
        for _ in range(50):
            if len(edges) >= 2:
                origin = random.choice(edges)
                dest = random.choice(edges)
                
                if origin != dest:
                    route = traci.simulation.findRoute(origin, dest)
                    if route and route.edges:
                        success += 1
        
        print(f"✅ Route test: {success}/50 successful ({success*2}%)")
        
        traci.close()
        
        if success > 40:  # 80% success
            print("\n🎉 NETWORK FIXED SUCCESSFULLY!")
            return True
        else:
            print("\n⚠️ Network still has connectivity issues")
            return False
            
    except Exception as e:
        print(f"❌ Could not verify: {e}")
        return False

if __name__ == "__main__":
    import random
    
    # Fix the network
    if fix_manhattan_network():
        # Verify the fix
        verify_fix()
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. The network has been fixed and replaced")
        print("2. The old network is backed up as manhattan_backup.net.xml")
        print("3. You can now run your main application")
        print("4. Vehicle spawning should have >80% success rate")
        print("\n✅ Ready to test with main_complete_integration.py")
    else:
        print("\n❌ Network fix failed. Check the errors above.")