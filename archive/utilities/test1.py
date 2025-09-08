# Run this in Python (you can create a test file or run in Jupyter)
import os
import sys

# First check if SUMO tools are accessible
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    print(f"✓ SUMO_HOME found: {os.environ['SUMO_HOME']}")
else:
    print("✗ SUMO_HOME not set!")

# Check for network file
if os.path.exists('data/manhattan.net.xml'):
    size = os.path.getsize('data/manhattan.net.xml') / 1024 / 1024
    print(f"✓ Network file exists: {size:.2f} MB")
    
    # Try to read it with sumolib
    try:
        import sumolib
        net = sumolib.net.readNet('data/manhattan.net.xml')
        print(f"✓ Network loaded successfully")
        print(f"  - Edges: {len(net.getEdges())}")
        print(f"  - Nodes: {len(net.getNodes())}")
        print(f"  - Sample edge IDs: {[e.getID() for e in list(net.getEdges())[:5]]}")
    except Exception as e:
        print(f"✗ Error reading network: {e}")
else:
    print("✗ Network file not found!")

# Check for OSM file
if os.path.exists('data/manhattan.osm'):
    size = os.path.getsize('data/manhattan.osm') / 1024 / 1024
    print(f"✓ OSM file exists: {size:.2f} MB")
else:
    print("✗ OSM file not found!")