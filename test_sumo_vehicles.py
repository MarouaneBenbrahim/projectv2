"""
test_sumo_vehicles.py - Test SUMO vehicle simulation
Run this to verify SUMO is working correctly
"""

import os
import sys
import time

try:
    import traci
    import sumolib
    print("✅ SUMO Python libraries loaded")
except ImportError:
    print("❌ SUMO Python libraries not found. Install with: pip install eclipse-sumo")
    sys.exit(1)

def test_basic_sumo():
    """Test basic SUMO functionality"""
    
    print("\n" + "="*60)
    print("TESTING SUMO VEHICLE SIMULATION")
    print("="*60)
    
    # Check network file
    net_file = "data/sumo/manhattan.net.xml"
    if not os.path.exists(net_file):
        print(f"❌ Network file not found: {net_file}")
        print("   Run: python get_manhattan_sumo_network.py")
        return False
    
    print(f"✅ Network file found: {net_file}")
    
    # Load network
    try:
        net = sumolib.net.readNet(net_file)
        edges = list(net.getEdges())
        print(f"✅ Network loaded: {len(edges)} edges")
        
        # Get some valid edge IDs for testing
        test_edges = []
        for edge in edges[:100]:
            if not edge.isSpecial() and edge.allows("passenger"):
                test_edges.append(edge.getID())
                if len(test_edges) >= 10:
                    break
        
        print(f"✅ Found {len(test_edges)} valid edges for vehicles")
        
    except Exception as e:
        print(f"❌ Failed to load network: {e}")
        return False
    
    # Start SUMO
    print("\n🚗 Starting SUMO (headless mode)...")
    
    # Build command with combined additional files
    cmd = [
        "sumo",  # Use sumo-gui if you want to see the simulation
        "-n", net_file,
        "--step-length", "0.1",
        "--no-warnings",
        "--no-step-log",
        "--duration-log.statistics",
        "--quit-on-end",
        "--end", "100"  # Run for 100 seconds then quit
    ]
    
    # Check for additional files and combine them
    additional_files = []
    if os.path.exists("data/sumo/traffic_lights.add.xml"):
        additional_files.append("data/sumo/traffic_lights.add.xml")
        print("   ✅ Traffic lights file found")
    if os.path.exists("data/sumo/types.add.xml"):
        additional_files.append("data/sumo/types.add.xml")
        print("   ✅ Vehicle types file found")
    
    if additional_files:
        cmd.extend(["-a", ",".join(additional_files)])
    
    try:
        traci.start(cmd)
        print("✅ SUMO started successfully!")
        
        # Test spawning vehicles
        print("\n🚗 Spawning test vehicles...")
        
        vehicles_spawned = 0
        for i in range(5):
            veh_id = f"test_vehicle_{i}"
            
            if len(test_edges) >= 2:
                origin = test_edges[i % len(test_edges)]
                dest = test_edges[(i + 5) % len(test_edges)]
                
                try:
                    # Create route
                    route_id = f"route_{veh_id}"
                    traci.route.add(route_id, [origin, dest])
                    
                    # Add vehicle
                    traci.vehicle.add(
                        veh_id,
                        route_id,
                        typeID="car",  # Use default car type
                        depart="now"
                    )
                    
                    vehicles_spawned += 1
                    print(f"   ✅ Spawned {veh_id} from {origin[:20]}... to {dest[:20]}...")
                    
                except Exception as e:
                    print(f"   ⚠️ Failed to spawn {veh_id}: {e}")
        
        print(f"\n✅ Successfully spawned {vehicles_spawned}/5 vehicles")
        
        # Run simulation for a few steps
        print("\n⏱️ Running simulation for 5 seconds...")
        
        for step in range(50):  # 5 seconds at 0.1s steps
            traci.simulationStep()
            
            if step % 10 == 0:  # Every second
                vehicles = traci.vehicle.getIDList()
                if vehicles:
                    avg_speed = sum(traci.vehicle.getSpeed(v) for v in vehicles) / len(vehicles)
                    print(f"   Step {step}: {len(vehicles)} vehicles, avg speed: {avg_speed*3.6:.1f} km/h")
        
        # Get final statistics
        vehicles = traci.vehicle.getIDList()
        if vehicles:
            print(f"\n📊 Final Statistics:")
            print(f"   Active vehicles: {len(vehicles)}")
            for veh_id in vehicles[:3]:  # Show first 3 vehicles
                speed = traci.vehicle.getSpeed(veh_id)
                dist = traci.vehicle.getDistance(veh_id)
                print(f"   - {veh_id}: Speed {speed*3.6:.1f} km/h, Distance {dist:.1f}m")
        
        # Close SUMO
        traci.close()
        print("\n✅ SUMO test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ SUMO test failed: {e}")
        try:
            traci.close()
        except:
            pass
        return False

def test_with_your_system():
    """Test with your integrated system"""
    
    print("\n" + "="*60)
    print("TESTING WITH YOUR INTEGRATED SYSTEM")
    print("="*60)
    
    try:
        # Import your systems
        from core.power_system import ManhattanPowerGrid
        from integrated_backend import ManhattanIntegratedSystem
        from core.sumo_manager import ManhattanSUMOManager
        
        print("✅ Imported your modules")
        
        # Initialize systems
        print("\n🔌 Initializing power grid...")
        power_grid = ManhattanPowerGrid()
        
        print("🏙️ Initializing integrated system...")
        integrated_system = ManhattanIntegratedSystem(power_grid)
        
        print("🚗 Initializing SUMO manager...")
        sumo_manager = ManhattanSUMOManager(integrated_system)
        
        # Start SUMO
        print("\n▶️ Starting SUMO through your system...")
        success = sumo_manager.start_sumo(gui=False, seed=42)
        
        if success:
            print("✅ SUMO started through your system!")
            
            # Spawn vehicles
            print("\n🚗 Spawning vehicles...")
            spawned = sumo_manager.spawn_vehicles(10, ev_percentage=0.5)
            print(f"✅ Spawned {spawned} vehicles (50% EVs)")
            
            # Run for a few steps
            print("\n⏱️ Running simulation...")
            for i in range(50):
                sumo_manager.step()
                
                if i % 10 == 0:
                    stats = sumo_manager.get_statistics()
                    print(f"   Step {i}: {len(sumo_manager.vehicles)} vehicles, "
                          f"EVs: {stats['ev_vehicles']}, "
                          f"Avg speed: {stats['avg_speed_mps']*3.6:.1f} km/h")
            
            # Stop SUMO
            sumo_manager.stop()
            print("\n✅ System test completed successfully!")
            return True
        else:
            print("❌ Failed to start SUMO through your system")
            return False
            
    except Exception as e:
        print(f"❌ System test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Test basic SUMO
    if test_basic_sumo():
        # Test with integrated system
        test_with_your_system()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)