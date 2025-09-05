"""
setup_sumo_manhattan.py - Complete SUMO Network Setup for Manhattan
Run this to ensure your SUMO network is properly configured
"""

import os
import json
import subprocess
import sys

def check_sumo_installation():
    """Check if SUMO is installed"""
    
    print("🔍 Checking SUMO installation...")
    
    try:
        result = subprocess.run(['sumo', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ SUMO is installed")
            print(f"   Version: {result.stdout.split()[1] if result.stdout else 'Unknown'}")
            return True
    except FileNotFoundError:
        print("❌ SUMO not found in PATH")
        print("\n📦 To install SUMO:")
        print("   Ubuntu/Debian: sudo apt-get install sumo sumo-tools")
        print("   MacOS: brew install sumo")
        print("   Windows: Download from https://sumo.dlr.de/docs/Downloads.php")
        print("   Python package: pip install eclipse-sumo")
        return False
    
    return False

def setup_directories():
    """Create necessary directories"""
    
    print("\n📁 Setting up directories...")
    
    directories = [
        'data',
        'data/sumo',
        'data/cache',
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   ✅ {directory}/")

def check_network_files():
    """Check if network files exist"""
    
    print("\n📄 Checking network files...")
    
    files_status = {
        'data/sumo/manhattan.net.xml': False,
        'data/manhattan_traffic_lights.json': False,
        'data/manhattan_connected_network.json': False,
        'data/sumo/traffic_lights.add.xml': False,
        'data/sumo/types.add.xml': False
    }
    
    for filepath in files_status.keys():
        if os.path.exists(filepath):
            files_status[filepath] = True
            size = os.path.getsize(filepath) / 1024
            print(f"   ✅ {filepath} ({size:.1f} KB)")
        else:
            print(f"   ❌ {filepath} - MISSING")
    
    return files_status

def generate_vehicle_types():
    """Generate vehicle type definitions for SUMO"""
    
    print("\n🚗 Generating vehicle types...")
    
    vehicle_types = {
        'car': {
            'accel': '2.6',
            'decel': '4.5',
            'length': '4.5',
            'minGap': '2.5',
            'maxSpeed': '13.89',
            'vClass': 'passenger',
            'color': '0.8,0.8,0.8'
        },
        'taxi': {
            'accel': '2.8',
            'decel': '5.0',
            'length': '4.5',
            'minGap': '2.0',
            'maxSpeed': '16.67',
            'vClass': 'taxi',
            'color': '1,1,0'
        },
        'bus': {
            'accel': '1.5',
            'decel': '4.0',
            'length': '12',
            'minGap': '3.0',
            'maxSpeed': '11.11',
            'vClass': 'bus',
            'color': '0,0,1'
        },
        'ev_sedan': {
            'accel': '3.5',
            'decel': '5.5',
            'length': '4.8',
            'minGap': '2.5',
            'maxSpeed': '16.67',
            'vClass': 'passenger',
            'color': '0,1,0',
            'emissionClass': 'Zero'
        },
        'ev_suv': {
            'accel': '3.0',
            'decel': '5.0',
            'length': '5.2',
            'minGap': '3.0',
            'maxSpeed': '16.67',
            'vClass': 'passenger',
            'color': '0,0.8,0.2',
            'emissionClass': 'Zero'
        },
        'delivery': {
            'accel': '2.0',
            'decel': '4.0',
            'length': '6.0',
            'minGap': '3.0',
            'maxSpeed': '13.89',
            'vClass': 'delivery',
            'color': '0.6,0.4,0.2'
        },
        'uber': {
            'accel': '2.7',
            'decel': '4.8',
            'length': '4.5',
            'minGap': '2.2',
            'maxSpeed': '15.56',
            'vClass': 'passenger',
            'color': '0.1,0.1,0.1'
        }
    }
    
    # Create XML content
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<additional>\n'
    
    for vtype_id, params in vehicle_types.items():
        xml_content += f'    <vType id="{vtype_id}"'
        for key, value in params.items():
            xml_content += f' {key}="{value}"'
        xml_content += '/>\n'
    
    xml_content += '</additional>\n'
    
    # Write file
    types_file = 'data/sumo/types.add.xml'
    with open(types_file, 'w') as f:
        f.write(xml_content)
    
    print(f"   ✅ Generated {len(vehicle_types)} vehicle types")
    return True

def create_simple_network():
    """Create a simple Manhattan grid network if main network is missing"""
    
    print("\n🏗️ Creating simple Manhattan grid network...")
    
    # Create nodes file
    nodes_content = """<?xml version="1.0" encoding="UTF-8"?>
<nodes>
"""
    
    # Create a grid of nodes (simplified Manhattan)
    node_id = 0
    nodes = []
    
    # Create grid from 34th to 59th Street, West to East
    for x in range(0, 2000, 200):  # East-West (roughly 10 avenues)
        for y in range(0, 3600, 150):  # North-South (roughly 24 blocks)
            nodes.append((node_id, x, y))
            nodes_content += f'    <node id="{node_id}" x="{x}" y="{y}"/>\n'
            node_id += 1
    
    nodes_content += '</nodes>\n'
    
    # Write nodes file
    with open('data/sumo/manhattan_simple.nod.xml', 'w') as f:
        f.write(nodes_content)
    
    # Create edges file
    edges_content = """<?xml version="1.0" encoding="UTF-8"?>
<edges>
"""
    
    edge_id = 0
    # Create horizontal edges (streets)
    for row in range(24):
        for col in range(9):
            from_node = row * 10 + col
            to_node = row * 10 + col + 1
            edges_content += f'    <edge id="e{edge_id}" from="{from_node}" to="{to_node}" numLanes="2"/>\n'
            edge_id += 1
            edges_content += f'    <edge id="e{edge_id}" from="{to_node}" to="{from_node}" numLanes="2"/>\n'
            edge_id += 1
    
    # Create vertical edges (avenues)
    for col in range(10):
        for row in range(23):
            from_node = row * 10 + col
            to_node = (row + 1) * 10 + col
            edges_content += f'    <edge id="e{edge_id}" from="{from_node}" to="{to_node}" numLanes="3"/>\n'
            edge_id += 1
            edges_content += f'    <edge id="e{edge_id}" from="{to_node}" to="{from_node}" numLanes="3"/>\n'
            edge_id += 1
    
    edges_content += '</edges>\n'
    
    # Write edges file
    with open('data/sumo/manhattan_simple.edg.xml', 'w') as f:
        f.write(edges_content)
    
    # Use netconvert to create network
    try:
        cmd = [
            'netconvert',
            '--node-files', 'data/sumo/manhattan_simple.nod.xml',
            '--edge-files', 'data/sumo/manhattan_simple.edg.xml',
            '--output-file', 'data/sumo/manhattan.net.xml',
            '--no-turnarounds',
            '--tls.guess', 'true',
            '--tls.default-type', 'actuated',
            '--junctions.corner-detail', '5',
            '--rectangular-lane-cut', 'true'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Network created successfully")
            return True
        else:
            print(f"   ❌ Failed to create network: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error creating network: {e}")
        return False

def create_traffic_light_programs():
    """Create realistic traffic light programs"""
    
    print("\n🚦 Creating traffic light programs...")
    
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<additional>
    <!-- Default NYC traffic light timing -->
    <tlLogic id="default" type="actuated" programID="0" offset="0">
        <!-- Phase 1: North-South Green (35s) -->
        <phase duration="35" state="GGGgrrrrGGGgrrrr" minDur="10" maxDur="50"/>
        <!-- Phase 2: North-South Yellow (3s) -->
        <phase duration="3" state="yyygrrrryyygrrrr"/>
        <!-- Phase 3: All Red (2s) -->
        <phase duration="2" state="rrrrrrrrrrrrrrrr"/>
        <!-- Phase 4: East-West Green (35s) -->
        <phase duration="35" state="rrrGGGGgrrrGGGGg" minDur="10" maxDur="50"/>
        <!-- Phase 5: East-West Yellow (3s) -->
        <phase duration="3" state="rrryyyygrrryyyyg"/>
        <!-- Phase 6: All Red (2s) -->
        <phase duration="2" state="rrrrrrrrrrrrrrrr"/>
    </tlLogic>
</additional>
"""
    
    with open('data/sumo/traffic_lights.add.xml', 'w') as f:
        f.write(xml_content)
    
    print("   ✅ Traffic light programs created")
    return True

def run_build_scripts():
    """Run the network building scripts if they exist"""
    
    print("\n🔨 Building complete network...")
    
    scripts = [
        ('get_real_traffic_lights.py', "Getting real traffic light data"),
        ('get_manhattan_sumo_network.py', "Building SUMO network"),
        ('manhattan_network_analyzer.py', "Analyzing network connectivity")
    ]
    
    for script, description in scripts:
        if os.path.exists(script):
            print(f"\n   Running: {description}...")
            try:
                result = subprocess.run([sys.executable, script], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"   ✅ {description} - Complete")
                else:
                    print(f"   ⚠️ {description} - Had issues")
                    print(f"      {result.stderr[:200]}")
            except Exception as e:
                print(f"   ❌ Failed to run {script}: {e}")
        else:
            print(f"   ⚠️ {script} not found")

def main():
    """Main setup process"""
    
    print("=" * 60)
    print("MANHATTAN SUMO NETWORK SETUP")
    print("Complete Configuration for World-Class Traffic Simulation")
    print("=" * 60)
    
    # Check SUMO installation
    sumo_ok = check_sumo_installation()
    
    # Setup directories
    setup_directories()
    
    # Check existing files
    files_status = check_network_files()
    
    # Generate vehicle types if needed
    if not files_status['data/sumo/types.add.xml']:
        generate_vehicle_types()
    
    # Create traffic light programs if needed
    if not files_status['data/sumo/traffic_lights.add.xml']:
        create_traffic_light_programs()
    
    # If network is missing, try to build it
    if not files_status['data/sumo/manhattan.net.xml']:
        print("\n⚠️ Main network file missing!")
        
        # Try running build scripts
        run_build_scripts()
        
        # Re-check
        if not os.path.exists('data/sumo/manhattan.net.xml'):
            print("\n🏗️ Creating fallback network...")
            if sumo_ok:
                create_simple_network()
    
    # Final status
    print("\n" + "=" * 60)
    print("SETUP COMPLETE - STATUS REPORT")
    print("=" * 60)
    
    # Re-check all files
    final_status = check_network_files()
    
    all_good = all(final_status.values())
    
    if all_good:
        print("\n✅ ALL SYSTEMS GO!")
        print("Your Manhattan SUMO network is ready for simulation")
        print("\n📋 Next steps:")
        print("1. Run: python main_complete_integration.py")
        print("2. Open: http://localhost:5000")
        print("3. Click 'Start Vehicles' to begin simulation")
    else:
        print("\n⚠️ Some files are still missing")
        print("The system will work with limitations")
        
        if not sumo_ok:
            print("\n🔴 CRITICAL: SUMO is not installed!")
            print("Install SUMO first, then run this setup again")
    
    print("=" * 60)

if __name__ == "__main__":
    main()