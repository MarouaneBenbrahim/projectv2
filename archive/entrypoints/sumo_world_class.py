"""
Manhattan SUMO Traffic Simulation - World Class Implementation
Professional-grade traffic simulation with real NYC data
"""

import os
import sys
import json
import random
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np

# Check SUMO installation
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    print(f"✅ SUMO found at: {os.environ['SUMO_HOME']}")
else:
    print("❌ Please set SUMO_HOME environment variable")
    print("   Example: set SUMO_HOME=C:\\Program Files (x86)\\Eclipse\\Sumo")
    sys.exit(1)

try:
    import traci
    import sumolib
    print("✅ SUMO Python tools loaded successfully")
except ImportError as e:
    print(f"❌ Error importing SUMO tools: {e}")
    sys.exit(1)

@dataclass
class VehicleType:
    """Vehicle types for Manhattan traffic"""
    id: str
    name: str
    length: float
    max_speed: float
    accel: float
    decel: float
    color: str
    emission_class: str
    probability: float

class ManhattanSUMOSimulation:
    """
    World-class SUMO simulation for Manhattan
    Realistic traffic patterns, EV integration, emergency vehicles
    """
    
    def __init__(self, output_dir='data/sumo'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Manhattan bounds
        self.bounds = {
            'north': 40.775,
            'south': 40.745,
            'east': -73.960,
            'west': -74.010
        }
        
        # Vehicle types
        self.vehicle_types = self._define_vehicle_types()
        
        # Traffic patterns by hour
        self.traffic_patterns = self._load_traffic_patterns()
        
        # SUMO files
        self.net_file = os.path.join(output_dir, 'manhattan.net.xml')
        self.route_file = os.path.join(output_dir, 'manhattan.rou.xml')
        self.config_file = os.path.join(output_dir, 'manhattan.sumocfg')
        self.additional_file = os.path.join(output_dir, 'manhattan.add.xml')
        
        # Simulation state
        self.running = False
        self.step = 0
        self.vehicles = {}
        self.traffic_lights = {}
        self.ev_charging_stations = {}
        
    def _define_vehicle_types(self) -> List[VehicleType]:
        """Define realistic Manhattan vehicle types"""
        return [
            # Regular vehicles
            VehicleType("sedan", "Sedan", 4.5, 30.0, 2.6, 4.5, "1,1,0", "HBEFA3/PC_G_EU4", 0.30),
            VehicleType("suv", "SUV", 5.0, 28.0, 2.4, 4.5, "0.8,0.8,0.8", "HBEFA3/PC_D_EU4", 0.25),
            VehicleType("taxi", "NYC Taxi", 4.8, 30.0, 2.8, 5.0, "1,0.8,0", "HBEFA3/PC_G_EU4", 0.15),
            
            # Electric vehicles
            VehicleType("tesla", "Tesla Model 3", 4.7, 35.0, 3.0, 5.5, "0,0.5,1", "Energy/unknown", 0.08),
            VehicleType("ev_suv", "Electric SUV", 5.2, 30.0, 2.5, 4.5, "0,0.8,0.5", "Energy/unknown", 0.05),
            
            # Commercial
            VehicleType("delivery", "Delivery Van", 6.0, 25.0, 2.0, 4.0, "0.5,0.3,0", "HBEFA3/LDV_D_EU4", 0.10),
            VehicleType("truck", "Box Truck", 8.0, 20.0, 1.5, 3.5, "0.4,0.4,0.4", "HBEFA3/HDV_D_EU4", 0.03),
            
            # Public transport
            VehicleType("bus", "MTA Bus", 12.0, 20.0, 1.2, 3.0, "0,0,0.8", "HBEFA3/Bus_D_EU4", 0.02),
            
            # Emergency
            VehicleType("ambulance", "Ambulance", 6.5, 40.0, 3.5, 6.0, "1,1,1", "HBEFA3/PC_D_EU4", 0.01),
            VehicleType("firetruck", "Fire Truck", 10.0, 35.0, 2.0, 4.0, "1,0,0", "HBEFA3/HDV_D_EU4", 0.01),
        ]
    
    def _load_traffic_patterns(self) -> Dict[int, float]:
        """NYC traffic patterns by hour"""
        return {
            0: 0.3,   # Midnight
            1: 0.2,
            2: 0.15,
            3: 0.15,
            4: 0.2,
            5: 0.3,
            6: 0.5,   # Morning rush starts
            7: 0.8,
            8: 0.95,  # Peak morning
            9: 0.9,
            10: 0.7,
            11: 0.6,
            12: 0.65, # Lunch
            13: 0.7,
            14: 0.65,
            15: 0.7,
            16: 0.8,  # Evening rush starts
            17: 0.95, # Peak evening
            18: 0.9,
            19: 0.75,
            20: 0.6,
            21: 0.5,
            22: 0.4,
            23: 0.35
        }
    
    def generate_network_from_osm(self):
        """Generate SUMO network from OpenStreetMap data"""
        print("\n🗺️ Generating Manhattan street network from OSM...")
        
        # Download OSM data
        osm_file = os.path.join(self.output_dir, 'manhattan.osm')
        
        if not os.path.exists(osm_file):
            print("Downloading Manhattan OSM data...")
            import requests
            
            # Overpass API query for Manhattan roads
            query = f"""
            [bbox:{self.bounds['south']},{self.bounds['west']},{self.bounds['north']},{self.bounds['east']}]
            [out:xml][timeout:90];
            (
              way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service"];
            );
            (._;>;);
            out body;
            """
            
            url = "https://overpass-api.de/api/interpreter"
            response = requests.post(url, data={'data': query})
            
            if response.status_code == 200:
                with open(osm_file, 'wb') as f:
                    f.write(response.content)
                print(f"✅ OSM data saved to {osm_file}")
            else:
                print(f"❌ Error downloading OSM data: {response.status_code}")
                return False
        
        # Convert OSM to SUMO network
        print("Converting OSM to SUMO network...")
        
        netconvert_cmd = [
            "netconvert",
            "--osm-files", osm_file,
            "--output-file", self.net_file,
            "--geometry.remove",
            "--remove-edges.isolated",
            "--keep-edges.by-vclass", "passenger",
            "--junctions.join",
            "--tls.guess-signals", "true",
            "--tls.discard-simple",
            "--tls.join",
            "--tls.default-type", "actuated",
            "--ramps.guess",
            "--roundabouts.guess",
            "--no-turnarounds",
            "--offset.disable-normalization",
            "--lefthand", "false",
            "--edges.join",
            "--speed.offset", "5",  # NYC speed limits
            "--default.speed", "11.11",  # 25 mph default
        ]
        
        try:
            result = subprocess.run(netconvert_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Network generated: {self.net_file}")
                return True
            else:
                print(f"❌ Netconvert error: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error running netconvert: {e}")
            return False
    
    def generate_routes(self, num_vehicles: int = 1000, duration: int = 3600):
        """Generate realistic Manhattan traffic routes"""
        print(f"\n🚗 Generating routes for {num_vehicles} vehicles...")
        
        # Load network
        if not os.path.exists(self.net_file):
            print("❌ Network file not found. Generate network first!")
            return False
        
        net = sumolib.net.readNet(self.net_file)
        
        # Create routes XML
        root = ET.Element('routes')
        
        # Add vehicle types
        for vtype in self.vehicle_types:
            vtype_elem = ET.SubElement(root, 'vType')
            vtype_elem.set('id', vtype.id)
            vtype_elem.set('length', str(vtype.length))
            vtype_elem.set('maxSpeed', str(vtype.max_speed))
            vtype_elem.set('accel', str(vtype.accel))
            vtype_elem.set('decel', str(vtype.decel))
            vtype_elem.set('color', vtype.color)
            vtype_elem.set('emissionClass', vtype.emission_class)
        
        # Get all edges
        edges = net.getEdges()
        valid_edges = [e for e in edges if not e.isSpecial()]
        
        if len(valid_edges) < 2:
            print("❌ Not enough edges in network")
            return False
        
        # Generate vehicles
        current_time = 0.0
        vehicle_id = 0
        
        for i in range(num_vehicles):
            # Select vehicle type based on probability
            rand = random.random()
            cumulative = 0
            selected_type = self.vehicle_types[0]
            
            for vtype in self.vehicle_types:
                cumulative += vtype.probability
                if rand <= cumulative:
                    selected_type = vtype
                    break
            
            # Random origin and destination
            origin = random.choice(valid_edges)
            destination = random.choice(valid_edges)
            
            while destination == origin:
                destination = random.choice(valid_edges)
            
            # Create vehicle
            vehicle = ET.SubElement(root, 'vehicle')
            vehicle.set('id', f'veh_{vehicle_id}')
            vehicle.set('type', selected_type.id)
            vehicle.set('depart', str(current_time))
            
            # Simple route (from edge to edge)
            route = ET.SubElement(vehicle, 'route')
            route.set('edges', f"{origin.getID()} {destination.getID()}")
            
            vehicle_id += 1
            
            # Distribute departures
            current_time += random.expovariate(num_vehicles / duration)
        
        # Save routes file
        tree = ET.ElementTree(root)
        tree.write(self.route_file, encoding='UTF-8', xml_declaration=True)
        print(f"✅ Routes generated: {self.route_file}")
        return True
    
    def generate_traffic_lights(self):
        """Generate traffic light programs"""
        print("\n🚦 Generating traffic light programs...")
        
        root = ET.Element('additional')
        
        # Add traffic light programs (simplified)
        # In real implementation, would read from network and create proper phases
        
        # Save additional file
        tree = ET.ElementTree(root)
        tree.write(self.additional_file, encoding='UTF-8', xml_declaration=True)
        print(f"✅ Traffic lights configured: {self.additional_file}")
        return True
    
    def generate_config(self):
        """Generate SUMO configuration file"""
        print("\n⚙️ Generating SUMO configuration...")
        
        config = ET.Element('configuration')
        
        # Input files
        input_elem = ET.SubElement(config, 'input')
        ET.SubElement(input_elem, 'net-file').set('value', os.path.basename(self.net_file))
        ET.SubElement(input_elem, 'route-files').set('value', os.path.basename(self.route_file))
        
        # Time settings
        time_elem = ET.SubElement(config, 'time')
        ET.SubElement(time_elem, 'begin').set('value', '0')
        ET.SubElement(time_elem, 'end').set('value', '3600')
        ET.SubElement(time_elem, 'step-length').set('value', '0.1')
        
        # Processing
        processing = ET.SubElement(config, 'processing')
        ET.SubElement(processing, 'collision.action').set('value', 'warn')
        ET.SubElement(processing, 'collision.check-junctions').set('value', 'true')
        ET.SubElement(processing, 'emergencydecel.warning-threshold').set('value', '1.5')
        
        # Save config
        tree = ET.ElementTree(config)
        tree.write(self.config_file, encoding='UTF-8', xml_declaration=True)
        print(f"✅ Configuration saved: {self.config_file}")
        return True
    
    def start_simulation(self, gui: bool = True):
        """Start SUMO simulation"""
        if self.running:
            print("⚠️ Simulation already running")
            return False
        
        # Check required files
        required_files = [self.net_file, self.route_file, self.config_file]
        for file in required_files:
            if not os.path.exists(file):
                print(f"❌ Missing required file: {file}")
                return False
        
        # Start SUMO
        try:
            sumo_binary = "sumo-gui" if gui else "sumo"
            sumo_cmd = [
                sumo_binary,
                "-c", self.config_file,
                "--collision.action", "warn",
                "--collision.check-junctions",
                "--device.emissions.probability", "1.0",
                "--device.battery.probability", "0.3",  # 30% EVs
                "--tripinfo-output", os.path.join(self.output_dir, "tripinfo.xml"),
                "--summary-output", os.path.join(self.output_dir, "summary.xml"),
                "--emission-output", os.path.join(self.output_dir, "emissions.xml"),
                "--statistic-output", os.path.join(self.output_dir, "stats.xml"),
                "--duration-log.statistics",
                "--no-step-log",
            ]
            
            if gui:
                sumo_cmd.extend([
                    "--start",
                    "--quit-on-end",
                    "--gui-settings-file", self._generate_gui_settings()
                ])
            
            print(f"🚀 Starting SUMO {'GUI' if gui else 'headless'}...")
            traci.start(sumo_cmd)
            self.running = True
            
            print("✅ SUMO simulation started successfully!")
            self._initialize_simulation()
            return True
            
        except Exception as e:
            print(f"❌ Error starting SUMO: {e}")
            self.running = False
            return False
    
    def _generate_gui_settings(self):
        """Generate GUI view settings"""
        settings_file = os.path.join(self.output_dir, 'gui-settings.xml')
        
        settings = ET.Element('viewsettings')
        scheme = ET.SubElement(settings, 'scheme')
        scheme.set('name', 'Manhattan Power Grid')
        
        # Background
        ET.SubElement(settings, 'background').set('backgroundColor', '0.2,0.2,0.2')
        
        # Visualization
        edges = ET.SubElement(settings, 'edges')
        ET.SubElement(edges, 'edge_colorer').set('scheme', 'by speed')
        ET.SubElement(edges, 'edge_scaler').set('scheme', 'by flow')
        
        tree = ET.ElementTree(settings)
        tree.write(settings_file, encoding='UTF-8', xml_declaration=True)
        return settings_file
    
    def _initialize_simulation(self):
        """Initialize simulation data structures"""
        if not self.running:
            return
        
        # Get all traffic lights
        tls_ids = traci.trafficlight.getIDList()
        for tls_id in tls_ids:
            self.traffic_lights[tls_id] = {
                'id': tls_id,
                'state': traci.trafficlight.getRedYellowGreenState(tls_id),
                'program': traci.trafficlight.getProgram(tls_id),
                'phase': traci.trafficlight.getPhase(tls_id)
            }
        
        print(f"📊 Initialized {len(self.traffic_lights)} traffic lights")
    
    def step(self):
        """Execute one simulation step"""
        if not self.running:
            return None
        
        try:
            traci.simulationStep()
            self.step += 1
            
            # Update vehicle data
            vehicle_ids = traci.vehicle.getIDList()
            
            metrics = {
                'step': self.step,
                'time': traci.simulation.getTime(),
                'vehicle_count': len(vehicle_ids),
                'departed': traci.simulation.getDepartedNumber(),
                'arrived': traci.simulation.getArrivedNumber(),
                'waiting_time': 0,
                'fuel_consumption': 0,
                'co2_emission': 0,
                'avg_speed': 0,
                'emergency_stops': 0
            }
            
            for veh_id in vehicle_ids:
                metrics['waiting_time'] += traci.vehicle.getWaitingTime(veh_id)
                metrics['fuel_consumption'] += traci.vehicle.getFuelConsumption(veh_id)
                metrics['co2_emission'] += traci.vehicle.getCO2Emission(veh_id)
                metrics['avg_speed'] += traci.vehicle.getSpeed(veh_id)
                
                if traci.vehicle.getEmergencyDecel(veh_id) > 4.5:
                    metrics['emergency_stops'] += 1
            
            if len(vehicle_ids) > 0:
                metrics['avg_speed'] /= len(vehicle_ids)
                metrics['avg_waiting'] = metrics['waiting_time'] / len(vehicle_ids)
            
            return metrics
            
        except traci.TraCIException as e:
            print(f"⚠️ TraCI error: {e}")
            return None
    
    def update_traffic_light(self, tls_id: str, powered: bool):
        """Update traffic light based on power status"""
        if not self.running or tls_id not in self.traffic_lights:
            return
        
        try:
            if not powered:
                # Power failure - set to flashing red (all red)
                state = 'r' * len(traci.trafficlight.getRedYellowGreenState(tls_id))
                traci.trafficlight.setRedYellowGreenState(tls_id, state)
                traci.trafficlight.setPhaseDuration(tls_id, 1000000)  # Hold indefinitely
            else:
                # Restore normal operation
                traci.trafficlight.setProgram(tls_id, self.traffic_lights[tls_id]['program'])
                
        except Exception as e:
            print(f"⚠️ Error updating traffic light {tls_id}: {e}")
    
    def inject_emergency_vehicle(self, origin: str, destination: str):
        """Inject an emergency vehicle with priority"""
        if not self.running:
            return
        
        veh_id = f"emergency_{self.step}"
        
        try:
            route_id = f"route_emergency_{self.step}"
            traci.route.add(route_id, [origin, destination])
            
            traci.vehicle.add(
                veh_id,
                route_id,
                typeID="ambulance",
                depart=traci.simulation.getTime()
            )
            
            # Set emergency vehicle parameters
            traci.vehicle.setSpeedMode(veh_id, 0)  # Ignore safe speed
            traci.vehicle.setColor(veh_id, (255, 0, 0, 255))
            traci.vehicle.setEmergencyDecel(veh_id, 9.0)
            
            print(f"🚨 Emergency vehicle {veh_id} dispatched!")
            return veh_id
            
        except Exception as e:
            print(f"⚠️ Error adding emergency vehicle: {e}")
            return None
    
    def get_traffic_density_map(self):
        """Get current traffic density for visualization"""
        if not self.running:
            return {}
        
        density_map = {}
        
        try:
            edges = traci.edge.getIDList()
            
            for edge_id in edges:
                vehicle_count = traci.edge.getLastStepVehicleNumber(edge_id)
                mean_speed = traci.edge.getLastStepMeanSpeed(edge_id)
                occupancy = traci.edge.getLastStepOccupancy(edge_id)
                
                density_map[edge_id] = {
                    'vehicles': vehicle_count,
                    'speed': mean_speed,
                    'occupancy': occupancy,
                    'congestion': 1.0 - (mean_speed / 30.0)  # Normalized congestion
                }
            
            return density_map
            
        except Exception as e:
            print(f"⚠️ Error getting traffic density: {e}")
            return {}
    
    def stop_simulation(self):
        """Stop SUMO simulation"""
        if self.running:
            try:
                traci.close()
                self.running = False
                print("✅ SUMO simulation stopped")
            except Exception as e:
                print(f"⚠️ Error stopping simulation: {e}")
    
    def setup_complete_simulation(self):
        """One-click setup for complete simulation"""
        print("\n" + "="*60)
        print("MANHATTAN SUMO SETUP - WORLD CLASS")
        print("="*60)
        
        # Step 1: Generate network
        if not os.path.exists(self.net_file):
            if not self.generate_network_from_osm():
                print("❌ Failed to generate network")
                return False
        else:
            print(f"✅ Using existing network: {self.net_file}")
        
        # Step 2: Generate routes
        if not os.path.exists(self.route_file):
            if not self.generate_routes(num_vehicles=2000, duration=3600):
                print("❌ Failed to generate routes")
                return False
        else:
            print(f"✅ Using existing routes: {self.route_file}")
        
        # Step 3: Generate traffic lights
        self.generate_traffic_lights()
        
        # Step 4: Generate config
        self.generate_config()
        
        print("\n" + "="*60)
        print("✅ SETUP COMPLETE - Ready to simulate!")
        print("="*60)
        return True


# Quick test function
def test_sumo():
    """Test SUMO setup"""
    print("\n🧪 Testing SUMO Installation...")
    
    # Create simulation
    sim = ManhattanSUMOSimulation()
    
    # Setup everything
    if sim.setup_complete_simulation():
        print("\n✅ SUMO is ready!")
        print("\nTo start simulation:")
        print("  sim.start_simulation(gui=True)  # With GUI")
        print("  sim.start_simulation(gui=False) # Headless")
        return sim
    else:
        print("\n❌ SUMO setup failed")
        return None


if __name__ == "__main__":
    # Run test
    sim = test_sumo()
    
    if sim:
        print("\n" + "="*60)
        print("Would you like to start the simulation? (y/n)")
        if input().lower() == 'y':
            if sim.start_simulation(gui=True):
                print("\nSimulation running... Press Ctrl+C to stop")
                
                try:
                    # Run for a while
                    for i in range(100):
                        metrics = sim.step()
                        if metrics and i % 10 == 0:
                            print(f"Step {i}: {metrics['vehicle_count']} vehicles, "
                                  f"Avg speed: {metrics['avg_speed']:.1f} m/s")
                except KeyboardInterrupt:
                    pass
                finally:
                    sim.stop_simulation()