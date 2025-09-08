"""
Manhattan Power Grid - SUMO Traffic Integration (FIXED)
World-Class Implementation with Real NYC Traffic
"""

import os
import sys
import json
import random
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
import threading
import time
import numpy as np

# Add SUMO to path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    print(f"✅ SUMO loaded from: {os.environ['SUMO_HOME']}")
else:
    print("❌ SUMO_HOME not set!")
    sys.exit(1)

import traci
import sumolib

class ManhattanTrafficSimulation:
    """
    Professional SUMO integration for Manhattan Power Grid
    Simulates real NYC traffic with power dependencies
    """
    
    def __init__(self, integrated_system=None):
        self.integrated_system = integrated_system
        self.output_dir = 'data/sumo'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Files
        self.net_file = os.path.join(self.output_dir, 'manhattan.net.xml')
        self.route_file = os.path.join(self.output_dir, 'manhattan.rou.xml')
        self.config_file = os.path.join(self.output_dir, 'manhattan.sumocfg')
        
        # State
        self.running = False
        self.gui_running = False
        self.step_counter = 0
        self.traffic_lights_map = {}
        
        # Manhattan bounds (Midtown - smaller area for better performance)
        self.bounds = {
            'north': 40.765, 'south': 40.750,  # Reduced area
            'east': -73.970, 'west': -73.990    # Times Square to Grand Central area
        }
        
        # Traffic metrics
        self.metrics = {
            'vehicles': 0,
            'avg_speed': 0,
            'waiting_time': 0,
            'co2_emissions': 0
        }
    
    def download_manhattan_network(self):
        """Download Manhattan street network from OSM"""
        osm_file = os.path.join(self.output_dir, 'manhattan.osm')
        
        if os.path.exists(osm_file):
            print(f"✅ Using existing OSM file: {osm_file}")
            return osm_file
        
        print("📥 Downloading Manhattan street network from OpenStreetMap...")
        
        import requests
        
        # Smaller area for better performance
        query = f"""
        [bbox:{self.bounds['south']},{self.bounds['west']},{self.bounds['north']},{self.bounds['east']}]
        [out:xml][timeout:90];
        (
          way["highway"~"primary|secondary|tertiary|residential"];
          node(w);
        );
        out;
        """
        
        url = "https://overpass-api.de/api/interpreter"
        
        try:
            response = requests.post(url, data={'data': query}, timeout=120)
            if response.status_code == 200:
                with open(osm_file, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Downloaded Manhattan street data ({len(response.content)/1024:.1f} KB)")
                return osm_file
            else:
                print(f"❌ Download failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Download error: {e}")
            return None
    
    def generate_network(self):
        """Generate SUMO network from OSM data"""
        print("\n🗺️ Generating SUMO network for Manhattan...")
        
        # Download OSM if needed
        osm_file = self.download_manhattan_network()
        if not osm_file:
            print("❌ Failed to get OSM data")
            return False
        
        # Convert to SUMO network with simplified settings
        print("🔨 Converting OSM to SUMO network...")
        
        netconvert_cmd = [
            "netconvert",
            "--osm-files", osm_file,
            "--output-file", self.net_file,
            # Simplified settings for stability
            "--geometry.remove",
            "--remove-edges.isolated",
            "--keep-edges.by-vclass", "passenger",
            "--junctions.join",
            "--tls.guess-signals", "true",
            "--tls.discard-simple",
            "--tls.join",
            "--no-turnarounds",
            "--offset.disable-normalization",
            "--lefthand", "false",
            "--default.speed", "13.89",  # 50 km/h default
            "--edges.join"
        ]
        
        try:
            result = subprocess.run(netconvert_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Network generated successfully!")
                self._analyze_network()
                return True
            else:
                print(f"⚠️ Netconvert warnings (this is normal):\n{result.stderr[:500]}")
                # Check if file was created despite warnings
                if os.path.exists(self.net_file):
                    print(f"✅ Network file created despite warnings")
                    self._analyze_network()
                    return True
                return False
        except Exception as e:
            print(f"❌ Error running netconvert: {e}")
            return False
    
    def _analyze_network(self):
        """Analyze generated network"""
        if not os.path.exists(self.net_file):
            return
        
        try:
            net = sumolib.net.readNet(self.net_file)
            
            edges = net.getEdges()
            tls = net.getTrafficLights()
            
            print(f"\n📊 Network Statistics:")
            print(f"  • Edges (streets): {len(edges)}")
            print(f"  • Traffic lights: {len(tls)}")
            print(f"  • Junctions: {len(net.getNodes())}")
        except Exception as e:
            print(f"⚠️ Could not analyze network: {e}")
    
    def generate_traffic(self, num_vehicles=500):
        """Generate realistic Manhattan traffic with VALID routes"""
        print(f"\n🚗 Generating {num_vehicles} vehicles with valid routes...")
        
        if not os.path.exists(self.net_file):
            print("❌ Network file not found!")
            return False
        
        try:
            net = sumolib.net.readNet(self.net_file)
        except Exception as e:
            print(f"❌ Could not read network: {e}")
            return False
        
        # Create routes XML
        root = ET.Element('routes')
        
        # Vehicle types (simplified)
        vtypes = [
            {'id': 'car', 'length': '4.5', 'maxSpeed': '13.89', 'accel': '2.6', 'decel': '4.5', 
             'sigma': '0.5', 'color': '1,1,0'},
            {'id': 'taxi', 'length': '4.8', 'maxSpeed': '13.89', 'accel': '2.6', 'decel': '4.5',
             'sigma': '0.5', 'color': '1,0.8,0'},
            {'id': 'bus', 'length': '12.0', 'maxSpeed': '11.11', 'accel': '1.2', 'decel': '3.0',
             'sigma': '0.5', 'color': '0,0.4,0.8'},
            {'id': 'delivery', 'length': '6.0', 'maxSpeed': '11.11', 'accel': '2.0', 'decel': '4.0',
             'sigma': '0.5', 'color': '0.5,0.3,0'}
        ]
        
        for vtype in vtypes:
            vt = ET.SubElement(root, 'vType')
            for key, value in vtype.items():
                vt.set(key, value)
        
        # Get valid edges for routing
        edges = [e for e in net.getEdges() if not e.isSpecial() and e.allows('passenger')]
        
        if len(edges) < 2:
            print("❌ Not enough valid edges for routing")
            return False
        
        print(f"  Found {len(edges)} valid edges for routing")
        
        # Generate vehicles with random routes
        successful_vehicles = 0
        depart_time = 0.0
        
        for i in range(num_vehicles):
            # Random vehicle type
            vtype_id = random.choice(['car', 'car', 'taxi', 'bus', 'delivery'])  # More cars
            
            # Try to find a valid route
            attempts = 0
            route_found = False
            
            while attempts < 10 and not route_found:
                # Random origin and destination edges
                from_edge = random.choice(edges)
                to_edge = random.choice(edges)
                
                if from_edge != to_edge:
                    # Try to compute route
                    route = net.getShortestPath(from_edge, to_edge)
                    
                    if route and route[0]:  # Valid route found
                        # Create vehicle with explicit route
                        vehicle = ET.SubElement(root, 'vehicle')
                        vehicle.set('id', f'veh_{i}')
                        vehicle.set('type', vtype_id)
                        vehicle.set('depart', str(depart_time))
                        vehicle.set('departLane', 'best')
                        vehicle.set('departSpeed', 'random')
                        
                        # Add route as edge list
                        route_elem = ET.SubElement(vehicle, 'route')
                        edge_list = ' '.join([e.getID() for e in route[0]])
                        route_elem.set('edges', edge_list)
                        
                        successful_vehicles += 1
                        route_found = True
                        
                        # Stagger departures
                        depart_time += random.uniform(0.5, 3.0)
                
                attempts += 1
        
        print(f"  Generated {successful_vehicles} vehicles with valid routes")
        
        # Save routes file
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')
        tree.write(self.route_file, encoding='UTF-8', xml_declaration=True)
        
        print(f"✅ Routes file saved: {self.route_file}")
        return True
    
    def generate_config(self):
        """Generate SUMO configuration"""
        print("\n⚙️ Creating SUMO configuration...")
        
        config = ET.Element('configuration')
        
        # Input
        input_elem = ET.SubElement(config, 'input')
        ET.SubElement(input_elem, 'net-file').set('value', os.path.basename(self.net_file))
        ET.SubElement(input_elem, 'route-files').set('value', os.path.basename(self.route_file))
        
        # Time
        time_elem = ET.SubElement(config, 'time')
        ET.SubElement(time_elem, 'begin').set('value', '0')
        ET.SubElement(time_elem, 'end').set('value', '3600')
        ET.SubElement(time_elem, 'step-length').set('value', '1')
        
        # Processing
        processing = ET.SubElement(config, 'processing')
        ET.SubElement(processing, 'collision.action').set('value', 'warn')
        ET.SubElement(processing, 'collision.check-junctions').set('value', 'true')
        ET.SubElement(processing, 'time-to-teleport').set('value', '300')
        ET.SubElement(processing, 'max-depart-delay').set('value', '900')
        ET.SubElement(processing, 'routing-algorithm').set('value', 'dijkstra')
        ET.SubElement(processing, 'device.rerouting.probability').set('value', '0.3')
        
        # Report
        report = ET.SubElement(config, 'report')
        ET.SubElement(report, 'verbose').set('value', 'true')
        ET.SubElement(report, 'no-step-log').set('value', 'true')
        
        # Save config
        tree = ET.ElementTree(config)
        ET.indent(tree, space='  ')
        tree.write(self.config_file, encoding='UTF-8', xml_declaration=True)
        
        print(f"✅ Configuration saved: {self.config_file}")
        return True
    
    def start(self, gui=True):
        """Start SUMO simulation"""
        if self.running:
            print("⚠️ Simulation already running")
            return False
        
        # Check files
        required_files = [self.net_file, self.route_file, self.config_file]
        for f in required_files:
            if not os.path.exists(f):
                print(f"❌ Missing file: {f}")
                return False
        
        try:
            # Prepare SUMO command
            sumo_binary = "sumo-gui" if gui else "sumo"
            
            cmd = [
                sumo_binary,
                "-c", self.config_file,
                "--collision.action", "warn",
                "--collision.check-junctions", "true",
                "--no-step-log", "true",
                "--no-warnings", "true",
                "--error-log", os.path.join(self.output_dir, "error.log")
            ]
            
            if gui:
                cmd.extend(["--start", "true"])
                cmd.extend(["--quit-on-end", "false"])
                cmd.extend(["--window-size", "1200,800"])
            
            print(f"\n🚀 Starting SUMO {'GUI' if gui else 'headless'} simulation...")
            print(f"   Command: {' '.join(cmd[:3])}...")
            
            traci.start(cmd)
            
            self.running = True
            self.gui_running = gui
            
            print("✅ SUMO simulation started successfully!")
            
            # Get initial info
            try:
                print(f"   Simulation time: 0 - {traci.simulation.getEndTime()}s")
                print(f"   Traffic lights: {len(traci.trafficlight.getIDList())}")
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start SUMO: {e}")
            self.running = False
            return False
    
    def step(self):
        """Execute simulation steps"""
        if not self.running:
            return None
        
        try:
            # Run for 100 steps then check
            for _ in range(100):
                traci.simulationStep()
                self.step_counter += 1
                
                if self.step_counter % 10 == 0:
                    # Get metrics
                    vehicle_ids = traci.vehicle.getIDList()
                    self.metrics['vehicles'] = len(vehicle_ids)
                    
                    if vehicle_ids:
                        speeds = [traci.vehicle.getSpeed(v) for v in vehicle_ids]
                        self.metrics['avg_speed'] = sum(speeds) / len(speeds)
                    
                    print(f"Step {self.step_counter}: {self.metrics['vehicles']} vehicles, "
                          f"Avg speed: {self.metrics['avg_speed']*3.6:.1f} km/h")
            
            return self.metrics
            
        except traci.exceptions.FatalTraCIError:
            print("Simulation ended")
            self.running = False
            return None
        except Exception as e:
            print(f"Step error: {e}")
            return None
    
    def stop(self):
        """Stop simulation"""
        if self.running:
            try:
                traci.close()
                self.running = False
                print("✅ SUMO simulation stopped")
            except:
                pass
    
    def setup_complete(self):
        """Complete setup with one command"""
        print("\n" + "="*60)
        print("MANHATTAN SUMO SETUP")
        print("="*60)
        
        success = True
        
        # 1. Generate network if needed
        if not os.path.exists(self.net_file):
            print("\n[1/3] Generating street network...")
            success = success and self.generate_network()
        else:
            print("\n[1/3] ✅ Using existing network")
        
        # 2. Generate traffic (fewer vehicles for testing)
        print("\n[2/3] Generating traffic patterns...")
        success = success and self.generate_traffic(num_vehicles=200)  # Start small
        
        # 3. Generate config
        print("\n[3/3] Creating configuration...")
        success = success and self.generate_config()
        
        if success:
            print("\n" + "="*60)
            print("✅ SETUP COMPLETE - Ready to simulate!")
            print("="*60)
        else:
            print("\n❌ Setup had issues - check messages above")
        
        return success


def test_manhattan_sumo():
    """Test SUMO with Manhattan data"""
    print("\n🧪 Testing Manhattan SUMO Integration...")
    
    sim = ManhattanTrafficSimulation()
    
    # Setup
    if not sim.setup_complete():
        print("Setup incomplete, but trying to continue...")
    
    # Ask to start
    print("\nStart simulation? (y/n): ", end='')
    response = input().strip().lower()
    
    if response == 'y':
        if sim.start(gui=True):
            print("\n📊 Simulation running...")
            print("Close SUMO window or press Ctrl+C to stop\n")
            
            try:
                while sim.running:
                    sim.step()
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                print("\n\nStopping simulation...")
            finally:
                sim.stop()
        else:
            print("Failed to start simulation")
            print("\nTrying headless mode...")
            if sim.start(gui=False):
                print("Running headless for 10 seconds...")
                for _ in range(10):
                    sim.step()
                    time.sleep(1)
                sim.stop()
    
    return sim


if __name__ == "__main__":
    test_manhattan_sumo()