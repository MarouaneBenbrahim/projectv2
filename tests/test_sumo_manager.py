"""
Test SUMO Manager - Verify everything works before integration
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("MANHATTAN SUMO MANAGER - TEST SUITE")
print("=" * 60)

# Test 1: Import checks
print("\n[TEST 1] Checking imports...")
try:
    import traci
    print("  ✓ traci imported successfully")
except ImportError as e:
    print(f"  ✗ traci import failed: {e}")
    print("  → Install with: pip install traci sumolib")
    sys.exit(1)

try:
    import sumolib
    print("  ✓ sumolib imported successfully")
except ImportError as e:
    print(f"  ✗ sumolib import failed: {e}")
    sys.exit(1)

try:
    from core.sumo_manager import ManhattanSUMOManager, VehicleType, SimulationScenario
    print("  ✓ SUMO Manager imported successfully")
except ImportError as e:
    print(f"  ✗ SUMO Manager import failed: {e}")
    sys.exit(1)

# Test 2: Check SUMO files exist
print("\n[TEST 2] Checking SUMO network files...")
network_file = 'data/sumo/manhattan.net.xml'
if os.path.exists(network_file):
    print(f"  ✓ Network file found: {network_file}")
    file_size = os.path.getsize(network_file) / 1024
    print(f"    Size: {file_size:.1f} KB")
else:
    print(f"  ✗ Network file not found: {network_file}")
    print("  → Please ensure manhattan.net.xml is in data/sumo/")
    sys.exit(1)

# Check for optional files
route_file = network_file.replace('.net.xml', '.rou.xml')
if os.path.exists(route_file):
    print(f"  ✓ Route file found: {route_file}")
else:
    print(f"  ℹ Route file not found (optional): {route_file}")

add_file = network_file.replace('.net.xml', '.add.xml')
if os.path.exists(add_file):
    print(f"  ✓ Additional file found: {add_file}")
else:
    print(f"  ℹ Additional file not found (optional): {add_file}")

# Test 3: Create mock integrated system
print("\n[TEST 3] Creating mock integrated system...")

class MockIntegratedSystem:
    """Mock integrated system for testing"""
    def __init__(self):
        # Mock traffic lights
        self.traffic_lights = {
            'TL_1': {
                'id': 'TL_1',
                'lat': 40.758,
                'lon': -73.985,
                'powered': True,
                'phase': 'green',
                'color': '#00ff00'
            },
            'TL_2': {
                'id': 'TL_2',
                'lat': 40.750,
                'lon': -73.993,
                'powered': True,
                'phase': 'red',
                'color': '#ff0000'
            }
        }
        
        # Mock EV stations
        self.ev_stations = {
            'EV_0': {
                'id': 'EV_0',
                'name': 'Times Square Garage',
                'lat': 40.758,
                'lon': -73.985,
                'chargers': 50,
                'vehicles_charging': 0
            },
            'EV_1': {
                'id': 'EV_1',
                'name': 'Penn Station Hub',
                'lat': 40.750,
                'lon': -73.993,
                'chargers': 40,
                'vehicles_charging': 0
            }
        }

mock_system = MockIntegratedSystem()
print("  ✓ Mock integrated system created")

# Test 4: Initialize SUMO Manager
print("\n[TEST 4] Initializing SUMO Manager...")
try:
    sumo_manager = ManhattanSUMOManager(mock_system, network_file)
    print("  ✓ SUMO Manager initialized")
    print(f"    Network loaded: {sumo_manager.net is not None}")
    print(f"    Edges in network: {len(sumo_manager.net.getEdges())}")
    print(f"    Vehicle types defined: {len(sumo_manager.vehicle_types)}")
except Exception as e:
    print(f"  ✗ Failed to initialize SUMO Manager: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Start SUMO
print("\n[TEST 5] Starting SUMO simulation...")
print("  Note: SUMO-GUI should open. If it doesn't, check SUMO installation.")

# Clean up any existing connections first
try:
    import traci
    traci.close()
    print("  ✓ Cleaned up existing TRACI connection")
except:
    pass

try:
    # Try with GUI first
    success = sumo_manager.start_sumo(gui=True, seed=42)
    
    if not success:
        print("  ℹ GUI mode failed, trying headless mode...")
        success = sumo_manager.start_sumo(gui=False, seed=42)
    
    if success:
        print("  ✓ SUMO started successfully")
        print(f"    Traffic lights found: {len(traci.trafficlight.getIDList())}")
        print(f"    Mapped traffic lights: {len(sumo_manager.tls_mapping)}")
        print(f"    EV stations mapped: {len(sumo_manager.ev_stations_sumo)}")
    else:
        print("  ✗ Failed to start SUMO")
        sys.exit(1)
        
except Exception as e:
    print(f"  ✗ SUMO start failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Spawn vehicles
print("\n[TEST 6] Spawning test vehicles...")
try:
    num_vehicles = 10
    ev_percentage = 0.7
    
    print(f"  Attempting to spawn {num_vehicles} vehicles ({ev_percentage*100:.0f}% EVs)...")
    spawned = sumo_manager.spawn_vehicles(count=num_vehicles, ev_percentage=ev_percentage)
    
    if spawned > 0:
        print(f"  ✓ Successfully spawned {spawned} vehicles")
        print(f"    Total vehicles: {sumo_manager.stats['total_vehicles']}")
        print(f"    EV vehicles: {sumo_manager.stats['ev_vehicles']}")
    else:
        print("  ✗ Failed to spawn vehicles")
        
except Exception as e:
    print(f"  ✗ Vehicle spawning failed: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Run simulation steps
print("\n[TEST 7] Running simulation steps...")
try:
    print("  Running 100 simulation steps (10 seconds)...")
    
    for step in range(100):
        success = sumo_manager.step()
        
        if not success:
            print(f"  ✗ Simulation failed at step {step}")
            break
        
        # Print progress every 20 steps
        if step % 20 == 0:
            stats = sumo_manager.get_statistics()
            positions = sumo_manager.get_vehicle_positions()
            
            print(f"    Step {step}:")
            print(f"      Active vehicles: {len(positions)}")
            print(f"      Avg speed: {stats['avg_speed_mps']:.2f} m/s")
            print(f"      Vehicles charging: {stats['vehicles_charging']}")
            
            # Check EV battery levels
            ev_positions = [p for p in positions if p['is_ev']]
            if ev_positions:
                avg_soc = sum(p['soc'] for p in ev_positions) / len(ev_positions)
                print(f"      Avg EV battery: {avg_soc*100:.1f}%")
        
        # Small delay to see the simulation
        time.sleep(0.01)
    
    print("  ✓ Simulation steps completed")
    
except Exception as e:
    print(f"  ✗ Simulation step failed: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Traffic light synchronization
print("\n[TEST 8] Testing traffic light synchronization...")
try:
    # Change a traffic light state in mock system
    mock_system.traffic_lights['TL_1']['powered'] = False
    mock_system.traffic_lights['TL_1']['color'] = '#000000'
    
    # Update traffic lights
    sumo_manager.update_traffic_lights()
    
    print("  ✓ Traffic light sync executed")
    
except Exception as e:
    print(f"  ✗ Traffic light sync failed: {e}")

# Test 9: Get final statistics
print("\n[TEST 9] Final statistics...")
try:
    stats = sumo_manager.get_statistics()
    positions = sumo_manager.get_vehicle_positions()
    
    print(f"  Total vehicles spawned: {stats['total_vehicles']}")
    print(f"  EV vehicles: {stats['ev_vehicles']}")
    print(f"  Currently active: {len(positions)}")
    print(f"  Average speed: {stats['avg_speed_mps']:.2f} m/s ({stats['avg_speed_mps']*3.6:.1f} km/h)")
    print(f"  Total wait time: {stats['total_wait_time']:.1f} seconds")
    print(f"  Energy consumed: {stats['total_energy_consumed_kwh']:.2f} kWh")
    print(f"  Vehicles charging: {stats['vehicles_charging']}")
    
except Exception as e:
    print(f"  ✗ Failed to get statistics: {e}")

# Cleanup
print("\n[TEST 10] Cleanup...")
try:
    sumo_manager.stop()
    print("  ✓ SUMO stopped cleanly")
except Exception as e:
    print(f"  ✗ Cleanup failed: {e}")
# Final cleanup - make sure connection is closed
try:
    traci.close()
except:
    pass
print("\n" + "=" * 60)
print("TEST SUITE COMPLETED")
print("=" * 60)

# Summary
print("\nSUMMARY:")
print("  If all tests passed, the SUMO manager is ready for integration!")
print("  If any tests failed, please fix the issues before proceeding.")
print("\nNext steps:")
print("  1. Fix any errors shown above")
print("  2. Once all tests pass, we'll integrate into main_world_class.py")