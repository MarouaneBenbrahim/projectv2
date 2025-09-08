"""
Test Simulation - Working SUMO Integration
Simplified version that works with your Manhattan network
"""

import os
import json
import time
import random
import threading
from typing import Dict, List
import xml.etree.ElementTree as ET
import traci

# Your existing imports
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem

class SimpleVehicleSimulation:
    """Simplified working vehicle simulation"""
    
    def __init__(self):
        self.data_dir = 'data/sumo'
        self.network_file = os.path.join(self.data_dir, 'manhattan.net.xml')
        self.valid_edges = []
        self.vehicles = {}
        self.charging_stations = {}
        self.simulation_step = 0
        
        # Parse network
        self._parse_network()
        self._init_charging_stations()
    
    def _parse_network(self):
        """Parse network to get valid edges"""
        tree = ET.parse(self.network_file)
        root = tree.getroot()
        
        edges = root.findall('.//edge')
        for edge in edges:
            edge_id = edge.get('id', '')
            # Skip internal edges
            if not edge_id.startswith(':'):
                # Check for passenger lanes
                lanes = edge.findall('.//lane')
                for lane in lanes:
                    allow = lane.get('allow', '')
                    disallow = lane.get('disallow', '')
                    if 'passenger' not in disallow:
                        self.valid_edges.append(edge_id)
                        break
        
        print(f"Found {len(self.valid_edges)} valid edges")
    
    def _init_charging_stations(self):
        """Initialize charging stations"""
        station_names = [
            ('CS_TimesSquare', 'Times Square Garage'),
            ('CS_BryantPark', 'Bryant Park Station'),
            ('CS_PennStation', 'Penn Station Hub'),
            ('CS_GrandCentral', 'Grand Central Charging'),
            ('CS_ColumbusCircle', 'Columbus Circle EV'),
            ('CS_MurrayHill', 'Murray Hill Garage'),
        ]
        
        for i, (cs_id, name) in enumerate(station_names):
            if i < len(self.valid_edges):
                edge_id = self.valid_edges[i * (len(self.valid_edges) // 6)]
                self.charging_stations[cs_id] = {
                    'id': cs_id,
                    'name': name,
                    'edge_id': edge_id,
                    'vehicles_charging': [],
                    'operational': True
                }
    
    def generate_routes(self, num_vehicles=10):
        """Generate simple routes file"""
        routes_file = os.path.join(self.data_dir, 'test_routes.rou.xml')
        root = ET.Element('routes')
        
        # Define vehicle types
        car_type = ET.SubElement(root, 'vType')
        car_type.set('id', 'car')
        car_type.set('color', '0.8,0.8,0.8')
        car_type.set('length', '4.5')
        
        ev_type = ET.SubElement(root, 'vType')
        ev_type.set('id', 'ev')
        ev_type.set('color', '0,1,0')
        ev_type.set('length', '4.8')
        
        # Generate vehicles
        if len(self.valid_edges) < 2:
            print("ERROR: Not enough edges for routing!")
            return None
        
        for i in range(num_vehicles):
            # 40% EVs
            is_ev = random.random() < 0.4
            vtype = 'ev' if is_ev else 'car'
            
            # Pick random edges
            origin = random.choice(self.valid_edges)
            destination = random.choice(self.valid_edges)
            
            # Make sure they're different
            attempts = 0
            while destination == origin and attempts < 10:
                destination = random.choice(self.valid_edges)
                attempts += 1
            
            # Create trip
            trip = ET.SubElement(root, 'trip')
            trip.set('id', f'veh_{i}')
            trip.set('type', vtype)
            trip.set('from', origin)
            trip.set('to', destination)
            trip.set('depart', str(i * 3.0))
            
            # Store vehicle info
            self.vehicles[f'veh_{i}'] = {
                'id': f'veh_{i}',
                'type': vtype,
                'is_ev': is_ev,
                'battery': random.uniform(30, 90) if is_ev else 100,
                'origin': origin,
                'destination': destination
            }
        
        # Write file
        tree = ET.ElementTree(root)
        tree.write(routes_file, encoding='utf-8', xml_declaration=True)
        
        print(f"Generated {num_vehicles} vehicles ({sum(1 for v in self.vehicles.values() if v['is_ev'])} EVs)")
        return routes_file
    
    def run_simulation(self, num_vehicles=10, max_steps=600):
        """Run SUMO simulation"""
        print("\n" + "=" * 60)
        print("STARTING VEHICLE SIMULATION")
        print(f"Vehicles: {num_vehicles}")
        print(f"Max steps: {max_steps}")
        print("=" * 60)
        
        # Generate routes
        routes_file = self.generate_routes(num_vehicles)
        if not routes_file:
            print("ERROR: Could not generate routes!")
            return
        
        # Build SUMO command - SIMPLE VERSION
        sumo_cmd = [
            'sumo',  # Headless
            '-n', self.network_file,
            '-r', routes_file,
            '--step-length', '1.0',
            '--no-step-log',
            '--no-warnings',
            '--duration-log.disable',
            '--time-to-teleport', '300'
        ]
        
        # Add additional files ONLY if they exist and aren't duplicated
        additional_files = []
        
        traffic_lights_file = os.path.join(self.data_dir, 'traffic_lights.add.xml')
        if os.path.exists(traffic_lights_file):
            additional_files.append(traffic_lights_file)
        
        types_file = os.path.join(self.data_dir, 'types.add.xml')
        if os.path.exists(types_file) and types_file not in additional_files:
            additional_files.append(types_file)
        
        # Add all additional files at once with comma separation
        if additional_files:
            sumo_cmd.extend(['--additional-files', ','.join(additional_files)])
        
        try:
            print("Starting SUMO...")
            print(f"Command: {' '.join(sumo_cmd)}")
            
            # Start SUMO
            traci.start(sumo_cmd)
            print("✓ SUMO started successfully")
            
            # Run simulation loop
            print("\nSimulation running...")
            print("-" * 40)
            
            while self.simulation_step < max_steps:
                # Check if vehicles remain
                if traci.simulation.getMinExpectedNumber() <= 0:
                    print("All vehicles completed routes")
                    break
                
                # Step
                traci.simulationStep()
                self.simulation_step += 1
                
                # Update every 30 steps
                if self.simulation_step % 30 == 0:
                    self._print_status()
                
                # Simple EV charging logic
                if self.simulation_step % 10 == 0:
                    self._handle_ev_charging()
            
            print("-" * 40)
            print(f"Simulation complete after {self.simulation_step} steps")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                traci.close()
                print("✓ SUMO closed")
            except:
                pass
    
    def _print_status(self):
        """Print simulation status"""
        try:
            num_vehicles = traci.simulation.getVehicleNumber()
            
            if num_vehicles > 0:
                vehicle_ids = traci.vehicle.getIDList()
                
                # Count stopped vehicles
                stopped = sum(1 for v in vehicle_ids if traci.vehicle.getSpeed(v) < 0.1)
                
                # Count EVs
                evs = sum(1 for v in vehicle_ids if v in self.vehicles and self.vehicles[v]['is_ev'])
                
                # Average speed
                avg_speed = sum(traci.vehicle.getSpeed(v) for v in vehicle_ids) / num_vehicles
                
                print(f"Step {self.simulation_step}: "
                      f"{num_vehicles} vehicles | "
                      f"{evs} EVs | "
                      f"Stopped: {stopped} | "
                      f"Avg speed: {avg_speed*3.6:.1f} km/h")
        except:
            pass
    
    def _handle_ev_charging(self):
        """Simple EV charging logic"""
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            for veh_id in vehicle_ids:
                if veh_id in self.vehicles and self.vehicles[veh_id]['is_ev']:
                    vehicle = self.vehicles[veh_id]
                    
                    # Check battery
                    if vehicle['battery'] < 20:
                        # Find a charging station
                        for station in self.charging_stations.values():
                            if station['operational'] and len(station['vehicles_charging']) < 5:
                                try:
                                    # Route to charging station
                                    traci.vehicle.changeTarget(veh_id, station['edge_id'])
                                    station['vehicles_charging'].append(veh_id)
                                    print(f"  EV {veh_id} routing to {station['name']} (battery: {vehicle['battery']:.1f}%)")
                                    break
                                except:
                                    pass
                    
                    # Simulate battery drain
                    vehicle['battery'] = max(0, vehicle['battery'] - 0.1)
        except:
            pass

class IntegratedTest:
    """Test integrated system with vehicles"""
    
    def __init__(self):
        # Initialize power grid
        print("\nInitializing power grid...")
        self.power_grid = ManhattanPowerGrid()
        
        # Initialize integrated backend
        print("Initializing integrated backend...")
        self.integrated_backend = ManhattanIntegratedSystem(self.power_grid)
        
        # Initialize vehicle simulation
        print("Initializing vehicle simulation...")
        self.vehicle_sim = SimpleVehicleSimulation()
        
        self.failed_substations = set()
    
    def run_test(self):
        """Run integrated test"""
        print("\n" + "=" * 60)
        print("INTEGRATED SYSTEM TEST")
        print("=" * 60)
        
        # Start vehicle simulation in thread
        def run_vehicles():
            self.vehicle_sim.run_simulation(num_vehicles=10, max_steps=300)
        
        vehicle_thread = threading.Thread(target=run_vehicles)
        vehicle_thread.start()
        
        # Wait for simulation to start
        time.sleep(5)
        
        # Test substation failure after 30 seconds
        print("\n" + "!" * 60)
        print("TEST: Waiting 30 seconds before failure test...")
        print("!" * 60)
        time.sleep(30)
        
        # Trigger failure
        self.trigger_failure('Times Square')
        
        # Wait 30 seconds
        time.sleep(30)
        
        # Restore
        self.restore_substation('Times Square')
        
        # Wait for vehicle simulation to complete
        vehicle_thread.join()
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
    
    def trigger_failure(self, substation_name):
        """Trigger substation failure"""
        print(f"\n⚡ TRIGGERING FAILURE: {substation_name}")
        print("-" * 40)
        
        # Fail in power grid
        self.power_grid.trigger_failure('substation', substation_name)
        
        # Fail in integrated backend
        impact = self.integrated_backend.simulate_substation_failure(substation_name)
        
        print(f"  Traffic lights affected: {impact['traffic_lights_affected']}")
        print(f"  EV stations affected: {impact['ev_stations_affected']}")
        print(f"  Load lost: {impact['load_lost_mw']:.2f} MW")
        
        # Affect charging stations
        for station in self.vehicle_sim.charging_stations.values():
            # Simple logic: Times Square affects first 2 stations
            if substation_name == 'Times Square' and station['id'] in ['CS_TimesSquare', 'CS_BryantPark']:
                station['operational'] = False
                print(f"  ✗ {station['name']} offline")
        
        self.failed_substations.add(substation_name)
        print("-" * 40)
    
    def restore_substation(self, substation_name):
        """Restore substation"""
        print(f"\n✓ RESTORING: {substation_name}")
        
        # Restore in power grid
        self.power_grid.restore_component('substation', substation_name)
        
        # Restore in integrated backend
        self.integrated_backend.restore_substation(substation_name)
        
        # Restore charging stations
        for station in self.vehicle_sim.charging_stations.values():
            if substation_name == 'Times Square' and station['id'] in ['CS_TimesSquare', 'CS_BryantPark']:
                station['operational'] = True
                print(f"  ✓ {station['name']} back online")
        
        if substation_name in self.failed_substations:
            self.failed_substations.remove(substation_name)
        
        print(f"✓ {substation_name} restored")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MANHATTAN INTEGRATED SYSTEM TEST")
    print("Power Grid + Traffic + Vehicles")
    print("=" * 60)
    
    # Run integrated test
    test = IntegratedTest()
    test.run_test()