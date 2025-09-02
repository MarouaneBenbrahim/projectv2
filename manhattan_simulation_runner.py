"""
Manhattan Simulation Runner - World-Class SUMO Integration
Connects smart router with SUMO and provides real-time data for Mapbox
"""

import os
import sys
import traci
import time
import json
import random
import threading
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np

# Add SUMO tools
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)

from manhattan_vehicle_router import RouterService, SmartVehicleManager
from manhattan_vehicle_types import create_vehicle_types

class ManhattanSimulation:
    """World-class Manhattan traffic simulation"""
    
    def __init__(self, network_file="data/manhattan_real.net.xml"):
        # Initialize router
        self.router = RouterService(network_file)
        self.vehicle_manager = SmartVehicleManager(self.router)
        
        # Simulation state
        self.running = False
        self.simulation_time = 0
        self.vehicle_counter = 0
        
        # Configuration
        self.config = {
            'spawn_rate': 2.0,  # Vehicles per second
            'total_vehicles': 100,  # Total vehicles to spawn
            'ev_percentage': 70,  # 70% EVs
            'gui': True,  # Show SUMO GUI
            'step_length': 0.1,  # 100ms steps for smooth movement
            'update_interval': 1.0,  # Update telemetry every second
        }
        
        # Telemetry data for frontend
        self.telemetry = {
            'vehicles': [],
            'charging_stations': [],
            'statistics': {},
            'timestamp': None
        }
        
        # Load connected network data - CRITICAL FIX
        self.network_data = self._load_connected_network()
        
        # Use spawn edges as destinations if network data loaded
        if self.network_data:
            self.destinations = self.network_data.get('spawn_edges', [])[:50]
        else:
            self.destinations = self._load_destinations()
    
    def _load_connected_network(self):
        """Load pre-analyzed connected network"""
        import json
        
        try:
            with open("data/manhattan_connected_network.json", "r") as f:
                data = json.load(f)
                print(f"✅ Loaded connected network: {data['connected_edges_count']} edges")
                print(f"   Spawn points: {len(data['spawn_edges'])}")
                print(f"   Charging stations: {len(data['charging_stations'])}")
                
                # Update router's charging stations with verified locations
                for cs_name, edge_id in data['charging_stations'].items():
                    if cs_name in self.router.charging_stations:
                        self.router.charging_stations[cs_name]['edge_id'] = edge_id
                
                return data
        except Exception as e:
            print(f"⚠️ No connected network data: {e}")
            print("Run manhattan_network_analyzer.py first!")
            return None
    
    def _load_destinations(self) -> List[str]:
        """Load popular destination edges - fallback method"""
        all_edges = list(self.router.net.getEdges())
        
        destinations = []
        step = len(all_edges) // 50
        for i in range(0, len(all_edges), step):
            if all_edges[i].allows("passenger"):
                destinations.append(all_edges[i].getID())
        
        return destinations
    
    def generate_sumo_config(self):
        """Generate SUMO configuration for the simulation"""
        
        # First create vehicle types
        create_vehicle_types()
        
        config_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="manhattan_real.net.xml"/>
        <additional-files value="vehicle_types.add.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="{self.config['step_length']}"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="300"/>
        <max-depart-delay value="900"/>
        <pedestrian.model value="nonInteracting"/>
        <routing-algorithm value="astar"/>
    </processing>
</configuration>"""
        
        with open("data/manhattan_sim.sumocfg", "w") as f:
            f.write(config_content)
        
        print("✅ Generated SUMO configuration")
    
    def start_simulation(self, gui=True):
        """Start SUMO simulation"""
        
        if not self.network_data:
            print("❌ Cannot start simulation without network data!")
            print("Please run: python manhattan_network_analyzer.py")
            return False
        
        self.generate_sumo_config()
        
        # SUMO command
        sumo_binary = "sumo-gui" if gui else "sumo"
        sumo_cmd = [
            sumo_binary,
            "-c", "data/manhattan_sim.sumocfg",
            "--delay", "50" if gui else "0",
            "--window-size", "1920,1080",
            "--window-pos", "50,50",
            "--scale", "3.0",
            "--gui-settings-file", "data/gui_settings.xml"
        ]
        
        try:
            traci.start(sumo_cmd)
            self.running = True
            print("✅ SUMO simulation started!")
            
            # Start vehicle spawning thread
            self.spawn_thread = threading.Thread(target=self._spawn_vehicles_thread)
            self.spawn_thread.daemon = True
            self.spawn_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start SUMO: {e}")
            return False
    
    def _spawn_vehicles_thread(self):
        """Background thread to spawn vehicles"""
        
        last_spawn_time = 0
        
        while self.running and self.vehicle_counter < self.config['total_vehicles']:
            current_time = traci.simulation.getTime()
            
            if current_time - last_spawn_time >= 1.0 / self.config['spawn_rate']:
                self._spawn_random_vehicle()
                last_spawn_time = current_time
                
            time.sleep(0.1)
    
    def _spawn_random_vehicle(self):
        """Spawn vehicle with intelligent routing - FINAL FIXED VERSION"""
        
        if not self.network_data:
            print("No network data available")
            return
        
        # Generate unique vehicle ID
        vehicle_id = f"veh_{self.vehicle_counter:04d}"
        self.vehicle_counter += 1
        
        # Use verified spawn edges from network analysis
        spawn_edges = self.network_data.get('spawn_edges', [])
        if len(spawn_edges) < 2:
            print("Not enough spawn edges")
            return
        
        # Choose random start and end from connected edges
        start_edge = random.choice(spawn_edges)
        end_edge = random.choice(spawn_edges)
        
        # Ensure they're different
        attempts = 0
        while start_edge == end_edge and attempts < 10:
            end_edge = random.choice(spawn_edges)
            attempts += 1
        
        if start_edge == end_edge:
            return  # Skip if couldn't find different edges
        
        try:
            # Create smart vehicle
            vehicle_data = self.router.create_smart_vehicle(vehicle_id, start_edge, end_edge)
            
            # Get the route
            path = vehicle_data.get('route', [])
            
            if path and len(path) > 1:
                # Create route in SUMO
                route_id = f"route_{vehicle_id}"
                traci.route.add(route_id, path)
                
                # Add vehicle to SUMO
                traci.vehicle.add(
                    vehicle_id,
                    routeID=route_id,
                    typeID=vehicle_data['type']
                )
                
                self.vehicle_manager.active_vehicles[vehicle_id] = vehicle_data
                
                if vehicle_data.get('is_ev'):
                    battery_percent = vehicle_data.get('battery_percent', 0)
                    print(f"🔋 EV {vehicle_id}: {vehicle_data['type']} ({battery_percent:.0f}% battery)")
                    if battery_percent < 30:
                        print(f"   ⚡ Low battery! Will route to charging station")
                else:
                    print(f"⛽ Gas {vehicle_id}: {vehicle_data['type']}")
                    
        except Exception as e:
            # Silently skip failed spawns to avoid spam
            pass
    
    def simulation_step(self):
        """Execute one simulation step"""
        
        if not self.running:
            return
        
        try:
            # Advance SUMO
            traci.simulationStep()
            self.simulation_time = traci.simulation.getTime()
            
            # Update all vehicles
            self.vehicle_manager.update_all_vehicles()
            
            # Update charging states
            for vehicle_id, vehicle in self.router.vehicles.items():
                if vehicle['state'] == 'charging':
                    self.router.update_charging(vehicle_id, self.config['step_length'])
            
            # Update telemetry periodically
            if int(self.simulation_time) % int(self.config['update_interval']) == 0:
                self._update_telemetry()
                
        except traci.exceptions.FatalTraCIError:
            print("Simulation ended")
            self.running = False
    
    def _update_telemetry(self):
        """Update telemetry data for frontend"""
        
        # Get vehicle positions
        vehicle_telemetry = self.vehicle_manager.get_all_telemetry()
        
        # Update charging station status
        charging_status = []
        for station_id, station in self.router.charging_stations.items():
            charging_status.append({
                'id': station_id,
                'name': station['name'],
                'lat': station['lat'],
                'lon': station['lon'],
                'capacity': station['capacity'],
                'available': station['available'],
                'occupied': station['capacity'] - station['available'],
                'power_kw': station['power_kw']
            })
        
        # Calculate statistics
        total_vehicles = len(vehicle_telemetry)
        evs = [v for v in vehicle_telemetry if v['is_ev']]
        charging = [v for v in evs if v['state'] == 'charging']
        seeking_charge = [v for v in evs if v['needs_charging']]
        
        avg_battery = np.mean([v['battery_percent'] for v in evs]) if evs else 0
        avg_speed = np.mean([v['speed_kmh'] for v in vehicle_telemetry]) if vehicle_telemetry else 0
        
        self.telemetry = {
            'vehicles': vehicle_telemetry,
            'charging_stations': charging_status,
            'statistics': {
                'total_vehicles': total_vehicles,
                'total_evs': len(evs),
                'charging_now': len(charging),
                'seeking_charge': len(seeking_charge),
                'gas_vehicles': total_vehicles - len(evs),
                'avg_battery_percent': round(avg_battery, 1),
                'avg_speed_kmh': round(avg_speed, 1),
                'simulation_time': round(self.simulation_time, 1)
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def get_telemetry(self) -> Dict:
        """Get current telemetry for API"""
        return self.telemetry
    
    def run(self):
        """Main simulation loop"""
        
        print("\n🚗 MANHATTAN SMART TRAFFIC SIMULATION 🚗")
        print(f"   EVs: {self.config['ev_percentage']}%")
        print(f"   Spawn rate: {self.config['spawn_rate']} vehicles/second")
        print(f"   Total vehicles: {self.config['total_vehicles']}")
        print("\n" + "="*50 + "\n")
        
        while self.running:
            self.simulation_step()
            
            # Print statistics every 10 seconds
            if int(self.simulation_time) % 10 == 0 and self.simulation_time > 0:
                stats = self.telemetry.get('statistics', {})
                print(f"\n⏱️  Time: {stats.get('simulation_time', 0):.0f}s")
                print(f"🚗 Vehicles: {stats.get('total_vehicles', 0)} "
                      f"({stats.get('total_evs', 0)} EVs, {stats.get('gas_vehicles', 0)} gas)")
                print(f"🔋 Battery avg: {stats.get('avg_battery_percent', 0):.1f}%")
                print(f"⚡ Charging: {stats.get('charging_now', 0)} now, "
                      f"{stats.get('seeking_charge', 0)} seeking")
                print(f"💨 Avg speed: {stats.get('avg_speed_kmh', 0):.1f} km/h")
            
            time.sleep(self.config['step_length'])
    
    def stop(self):
        """Stop simulation"""
        self.running = False
        try:
            traci.close()
        except:
            pass
        print("\n✅ Simulation stopped")
    
    def export_telemetry_json(self):
        """Export telemetry to JSON file for frontend"""
        with open("data/telemetry.json", "w") as f:
            json.dump(self.telemetry, f, indent=2)

# GUI settings for better visualization
def create_gui_settings():
    """Create SUMO GUI settings"""
    
    settings = """<?xml version="1.0" encoding="UTF-8"?>
<viewsettings>
    <viewport y="40.758" x="-73.980" zoom="500"/>
    <delay value="50"/>
    <scheme name="real-world">
        <background backgroundColor="20,20,20" showGrid="false" gridXSize="100.00" gridYSize="100.00"/>
        <edge laneWidthExaggeration="1" scaleWidth="true" showLinkDecals="true" showRails="true"/>
        <vehicle vehicleQuality="2" showBlinker="true" showBrakeLights="true" showRoute="false" 
                 vehicleSize="2" vehicleShape="passenger/van">
            <colorScheme name="by_speed" interpolated="true">
                <entry color="red" threshold="0"/>
                <entry color="yellow" threshold="8.33"/>
                <entry color="green" threshold="15.28"/>
                <entry color="cyan" threshold="22.22"/>
            </colorScheme>
        </vehicle>
        <person personQuality="2" showPedestrians="true"/>
        <junction showShape="true" drawLinkTLIndex="false" drawLinkJunctionIndex="false"/>
        <additionals busStopColorSign="1" chargingStationColor="green" chargingStationColorSign="1"/>
    </scheme>
</viewsettings>"""
    
    with open("data/gui_settings.xml", "w") as f:
        f.write(settings)
    print("✅ Created GUI settings")

if __name__ == "__main__":
    # Create GUI settings
    create_gui_settings()
    
    # Initialize simulation
    sim = ManhattanSimulation()
    
    # Check if network data is available
    if not sim.network_data:
        print("\n❌ ERROR: Network data not found!")
        print("Please run these commands first:")
        print("1. python manhattan_network_analyzer.py")
        print("2. python fix_charging_stations.py")
        sys.exit(1)
    
    # Configure
    sim.config['ev_percentage'] = 70  # 70% EVs
    sim.config['spawn_rate'] = 2.0  # 2 vehicles per second
    sim.config['total_vehicles'] = 50  # Start with 50 for testing
    
    # Start simulation
    if sim.start_simulation(gui=True):
        try:
            sim.run()
        except KeyboardInterrupt:
            print("\n⚠️ Stopping simulation...")
        finally:
            sim.stop()
            sim.export_telemetry_json()
            print("✅ Telemetry exported to data/telemetry.json")
    else:
        print("Failed to start simulation")