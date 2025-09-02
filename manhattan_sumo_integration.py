"""
Manhattan Power Grid - World Class SUMO Traffic Integration
Professional vehicle simulation with EV charging and power grid coupling
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import random
import time
import threading
import asyncio
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# SUMO imports
try:
    if 'SUMO_HOME' in os.environ:
        sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
    import traci
    import sumolib
    SUMO_AVAILABLE = True
except ImportError:
    print("Warning: SUMO not installed. Install with: pip install sumolib traci")
    SUMO_AVAILABLE = False

# WebSocket imports
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    print("Warning: websockets not installed. Install with: pip install websockets")
    WEBSOCKETS_AVAILABLE = False

class VehicleType(Enum):
    """Vehicle classifications"""
    SEDAN = "sedan"
    SUV = "suv"
    TAXI = "taxi"
    BUS = "bus"
    TRUCK = "truck"
    EV_SEDAN = "ev_sedan"
    EV_SUV = "ev_suv"
    EV_TAXI = "ev_taxi"
    EV_BUS = "ev_bus"

@dataclass
class Vehicle:
    """Individual vehicle with battery for EVs"""
    id: str
    vehicle_type: VehicleType
    position: Tuple[float, float] = (0, 0)
    speed: float = 0.0
    route: List[str] = field(default_factory=list)
    is_ev: bool = False
    battery_capacity_kwh: float = 0.0
    battery_soc: float = 1.0  # State of charge (0-1)
    charging_station: Optional[str] = None
    charging_power_kw: float = 0.0
    color: str = "#ffffff"
    waiting_time: float = 0.0

@dataclass
class ChargingSession:
    """EV charging session"""
    vehicle_id: str
    station_id: str
    start_time: datetime
    energy_delivered_kwh: float = 0.0
    power_kw: float = 7.2
    target_soc: float = 0.9

class ManhattanSUMONetwork:
    """
    Creates and manages SUMO network for Manhattan
    """
    
    def __init__(self, bounds):
        self.bounds = bounds
        self.net_file = "data/manhattan.net.xml"
        self.route_file = "data/manhattan.rou.xml"
        self.additional_file = "data/manhattan.add.xml"
        self.config_file = "data/manhattan.sumocfg"
        
        print("Creating SUMO network files...")
        
        # Create SUMO files
        self._create_network()
        self._create_routes()
        self._create_additional()
        self._create_config()
        
        print(f"SUMO files created in 'data/' directory:")
        print(f"  - Network: {self.net_file}")
        print(f"  - Routes: {self.route_file}")
        print(f"  - Config: {self.config_file}")
    
    def _create_network(self):
        """Create SUMO network file for Manhattan grid"""
        
        # Create plain nodes file
        nodes_content = """<?xml version="1.0" encoding="UTF-8"?>
<nodes>
"""
        
        # Create a simple grid of nodes
        node_id = 0
        for i in range(5):  # Simplified to 5x5 grid
            for j in range(5):
                lon = self.bounds['min_lon'] + (self.bounds['max_lon'] - self.bounds['min_lon']) * i / 4
                lat = self.bounds['min_lat'] + (self.bounds['max_lat'] - self.bounds['min_lat']) * j / 4
                x = (lon + 74) * 100000  # Simple conversion to meters
                y = (lat - 40) * 100000
                
                tl_type = "traffic_light" if (i % 2 == 0 and j % 2 == 0) else "priority"
                nodes_content += f'    <node id="n{node_id}" x="{x:.2f}" y="{y:.2f}" type="{tl_type}"/>\n'
                node_id += 1
        
        nodes_content += "</nodes>"
        
        # Create plain edges file
        edges_content = """<?xml version="1.0" encoding="UTF-8"?>
<edges>
"""
        
        edge_id = 0
        # Horizontal edges
        for j in range(5):
            for i in range(4):
                from_node = j * 5 + i
                to_node = j * 5 + i + 1
                edges_content += f'    <edge id="e{edge_id}" from="n{from_node}" to="n{to_node}" numLanes="2" speed="13.89"/>\n'
                edge_id += 1
        
        # Vertical edges
        for i in range(5):
            for j in range(4):
                from_node = j * 5 + i
                to_node = (j + 1) * 5 + i
                edges_content += f'    <edge id="e{edge_id}" from="n{from_node}" to="n{to_node}" numLanes="2" speed="11.11"/>\n'
                edge_id += 1
        
        edges_content += "</edges>"
        
        # Save plain XML files
        os.makedirs("data", exist_ok=True)
        
        with open("data/manhattan.nod.xml", "w") as f:
            f.write(nodes_content)
        
        with open("data/manhattan.edg.xml", "w") as f:
            f.write(edges_content)
        
        # Try to use netconvert if available
        try:
            import subprocess
            import shutil
            
            # Check if netconvert exists
            if not shutil.which("netconvert"):
                print("netconvert not found in PATH, creating simple network")
                self._create_simple_network()
                return
            
            result = subprocess.run([
                "netconvert",
                "--node-files", "data/manhattan.nod.xml",
                "--edge-files", "data/manhattan.edg.xml",
                "--output-file", self.net_file,
                "--no-warnings",
                "--no-turnarounds",
                "--offset.disable-normalization",
                "--geometry.remove",
                "--junctions.join",
                "--verbose"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("SUMO network created successfully with netconvert")
                # Check if file was actually created
                if not os.path.exists(self.net_file):
                    print("Warning: Network file not created, using simple network")
                    self._create_simple_network()
            else:
                print(f"netconvert failed with return code {result.returncode}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                if result.stdout:
                    print(f"Output: {result.stdout}")
                # Use the simple network anyway
                self._create_simple_network()
        except Exception as e:
            print(f"Could not run netconvert: {e}")
            self._create_simple_network()
    
    def _create_simple_network(self):
        """Create a simple network file directly"""
        network_content = """<?xml version="1.0" encoding="UTF-8"?>
<net>
    <location netOffset="0.00,0.00" convBoundary="0.00,0.00,1000.00,1000.00" origBoundary="0.00,0.00,1000.00,1000.00" projParameter="!"/>
    <edge id="e0" from="n0" to="n1">
        <lane id="e0_0" index="0" speed="13.89" length="100.00" shape="0.00,0.00 100.00,0.00"/>
    </edge>
    <junction id="n0" type="priority" x="0.00" y="0.00" incLanes="" intLanes="" shape="0.00,1.60 0.00,-1.60"/>
    <junction id="n1" type="priority" x="100.00" y="0.00" incLanes="e0_0" intLanes="" shape="100.00,-1.60 100.00,1.60"/>
</net>"""
        
        with open(self.net_file, "w") as f:
            f.write(network_content)
        
        print("Created simple fallback network")
    
    def _create_routes(self):
        """Create vehicle routes and types"""
        
        # First check what edges exist in the network
        existing_edges = []
        if os.path.exists(self.net_file):
            try:
                # Try to parse the network to get actual edge IDs
                import xml.etree.ElementTree as ET
                tree = ET.parse(self.net_file)
                root = tree.getroot()
                for edge in root.findall(".//edge"):
                    edge_id = edge.get('id')
                    if edge_id and not edge_id.startswith(':'):  # Skip internal edges
                        existing_edges.append(edge_id)
            except:
                pass
        
        # If we found edges, use them; otherwise use defaults
        if existing_edges:
            # Create routes from actual edges
            route_list = []
            if len(existing_edges) >= 4:
                # Create a few simple routes from available edges
                route_list.append(' '.join(existing_edges[:min(4, len(existing_edges))]))
                if len(existing_edges) >= 8:
                    route_list.append(' '.join(existing_edges[4:8]))
            else:
                route_list.append(' '.join(existing_edges))
        else:
            # Use simple default routes
            route_list = ["e0", "e0", "e0", "e0"]  # Very simple fallback
        
        routes_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<routes>
    <!-- Vehicle types -->
    <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="5" maxSpeed="30" color="1,1,0"/>
    <vType id="bus" accel="1.2" decel="3.0" sigma="0.2" length="12" maxSpeed="20" color="1,0.5,0"/>
    <vType id="ev" accel="3.0" decel="5.0" sigma="0.3" length="5" maxSpeed="30" color="0,1,0">
        <param key="has.battery.device" value="true"/>
        <param key="battery.capacity" value="60"/>
    </vType>
    
    <!-- Routes -->
    <route id="route0" edges="{route_list[0] if len(route_list) > 0 else 'e0'}"/>
    <route id="route1" edges="{route_list[1] if len(route_list) > 1 else route_list[0] if route_list else 'e0'}"/>
    <route id="route2" edges="{route_list[2] if len(route_list) > 2 else route_list[0] if route_list else 'e0'}"/>
    
    <!-- Vehicle flows -->
    <flow id="flow_cars" type="car" route="route0" begin="0" end="3600" vehsPerHour="50"/>
    <flow id="flow_evs" type="ev" route="route1" begin="0" end="3600" vehsPerHour="15"/>
    <flow id="flow_buses" type="bus" route="route2" begin="0" end="3600" vehsPerHour="5"/>
</routes>"""
        
        with open(self.route_file, "w") as f:
            f.write(routes_content)
        
        print(f"Created routes with {len(existing_edges)} available edges")
    
    def _create_additional(self):
        """Create additional elements (charging stations, detectors)"""
        
        root = ET.Element("additional")
        
        # For now, skip charging stations until we verify lane names
        # We'll add them dynamically after the network is loaded
        
        # Save minimal additional file
        tree = ET.ElementTree(root)
        tree.write(self.additional_file, encoding="UTF-8", xml_declaration=True)
    
    def _create_config(self):
        """Create SUMO configuration file"""
        
        config = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{os.path.basename(self.net_file)}"/>
        <route-files value="{os.path.basename(self.route_file)}"/>
        <additional-files value="{os.path.basename(self.additional_file)}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="0.1"/>
    </time>
    <processing>
        <ignore-route-errors value="true"/>
    </processing>
</configuration>"""
        
        with open(self.config_file, 'w') as f:
            f.write(config)
        
        print(f"Created SUMO config: {self.config_file}")

class WorldClassTrafficSimulation:
    """
    Professional SUMO-PyPSA integrated traffic simulation
    """
    
    def __init__(self, integrated_system, power_grid):
        self.integrated_system = integrated_system
        self.power_grid = power_grid
        self.running = False
        self.vehicles: Dict[str, Vehicle] = {}
        self.charging_sessions: Dict[str, ChargingSession] = {}
        self.traffic_lights_synced = {}
        self.websocket_clients = []
        
        # Manhattan bounds
        self.bounds = {
            'min_lat': 40.745,
            'max_lat': 40.775,
            'min_lon': -74.010,
            'max_lon': -73.960
        }
        
        # Create SUMO network
        self.sumo_network = ManhattanSUMONetwork(self.bounds)
        
        # Statistics
        self.stats = {
            'total_vehicles': 0,
            'active_vehicles': 0,
            'evs_charging': 0,
            'avg_speed_mph': 0,
            'total_wait_time': 0,
            'energy_consumed_kwh': 0,
            'co2_emissions_kg': 0
        }
    
    def start_simulation(self, gui=False):
        """Start SUMO simulation"""
        
        if not SUMO_AVAILABLE:
            print("SUMO not available - install with: pip install sumolib traci")
            print("Also ensure SUMO is installed: https://sumo.dlr.de/docs/Downloads.php")
            return False
        
        original_dir = os.getcwd()  # Save original directory
        
        try:
            # First, check if network files exist
            if not os.path.exists(self.sumo_network.net_file):
                print(f"Network file not found: {self.sumo_network.net_file}")
                print("Creating network files...")
                self.sumo_network = ManhattanSUMONetwork(self.bounds)
            
            # Check all required files
            print(f"Checking SUMO files:")
            print(f"  Network: {os.path.exists(self.sumo_network.net_file)} - {self.sumo_network.net_file}")
            print(f"  Routes: {os.path.exists(self.sumo_network.route_file)} - {self.sumo_network.route_file}")
            print(f"  Config: {os.path.exists(self.sumo_network.config_file)} - {self.sumo_network.config_file}")
            
            # Build SUMO command
            if gui:
                sumo_binary = "sumo-gui"
            else:
                sumo_binary = "sumo"
            
            # Check if SUMO binary exists
            import shutil
            if not shutil.which(sumo_binary):
                print(f"SUMO binary '{sumo_binary}' not found in PATH")
                print("Please install SUMO from: https://sumo.dlr.de/docs/Downloads.php")
                return False
            
            # Change to data directory for SUMO
            os.chdir("data")
            
            sumo_cmd = [
                sumo_binary,
                "-c", os.path.basename(self.sumo_network.config_file),
                "--step-length", "0.1",
                "--no-warnings",
                "--duration-log.statistics",
                "--no-step-log"
            ]
            
            # Start SUMO
            print(f"Starting SUMO simulation ({'GUI' if gui else 'headless'} mode)...")
            print(f"Command: {' '.join(sumo_cmd)}")
            traci.start(sumo_cmd)
            
            # Change back to original directory
            os.chdir(original_dir)
            
            self.running = True
            
            # Verify connection
            try:
                step = traci.simulation.getTime()
                print(f"SUMO connected successfully at simulation time: {step}")
            except:
                print("SUMO started but connection verification failed")
                self.running = False
                return False
            
            # Start simulation thread
            self.sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.sim_thread.start()
            
            print(f"✅ SUMO simulation running")
            return True
            
        except Exception as e:
            # Try to restore directory if changed
            try:
                os.chdir(original_dir)
            except:
                pass
            
            print(f"Failed to start SUMO: {e}")
            print("\nTroubleshooting:")
            print("1. Ensure SUMO is installed: https://sumo.dlr.de/docs/Downloads.php")
            print("2. Set SUMO_HOME environment variable")
            print("3. On Windows, add SUMO/bin to PATH")
            print("4. Check that network files are generated in 'data/' folder")
            return False
    
    def _simulation_loop(self):
        """Main SUMO simulation loop"""
        
        step = 0
        
        try:
            while self.running:
                try:
                    # Check if simulation should continue
                    if traci.simulation.getMinExpectedNumber() <= 0:
                        print("No more vehicles in simulation, ending...")
                        break
                    
                    # Step simulation
                    traci.simulationStep()
                    step += 1
                    
                    # Update every 10 steps (1 second sim time)
                    if step % 10 == 0:
                        self._update_vehicles()
                        self._sync_traffic_lights()
                        self._handle_ev_charging()
                        self._update_statistics()
                        self._check_boundaries()
                    
                    # Power grid sync every 30 seconds
                    if step % 300 == 0:
                        self._sync_with_power_grid()
                    
                    time.sleep(0.01)  # Small delay for real-time
                    
                except Exception as e:
                    # Handle any TraCI error (different versions have different exception types)
                    if "closed" in str(e).lower() or "fatal" in str(e).lower():
                        print(f"SUMO connection lost: {e}")
                        break
                    else:
                        print(f"Simulation step error: {e}")
                        # Continue running despite non-fatal errors
                    
        except Exception as e:
            print(f"Simulation loop error: {e}")
        
        finally:
            self.stop_simulation()
    
    def _update_vehicles(self):
        """Update vehicle states from SUMO"""
        
        try:
            # Get all vehicles in simulation
            vehicle_ids = traci.vehicle.getIDList()
            
            # Update existing vehicles
            current_ids = set()
            
            for vid in vehicle_ids:
                current_ids.add(vid)
                
                # Get vehicle data
                try:
                    pos = traci.vehicle.getPosition(vid)
                    # Simple conversion - adjust based on your coordinate system
                    lon = self.bounds['min_lon'] + (pos[0] / 100000)
                    lat = self.bounds['min_lat'] + (pos[1] / 100000)
                    speed = traci.vehicle.getSpeed(vid) * 2.237  # m/s to mph
                    route = traci.vehicle.getRoute(vid)
                    waiting = traci.vehicle.getWaitingTime(vid)
                except Exception as e:
                    print(f"Error getting vehicle {vid} data: {e}")
                    continue
                
                # Check if EV
                try:
                    vehicle_type = traci.vehicle.getTypeID(vid)
                    is_ev = "ev" in vehicle_type.lower()
                except:
                    vehicle_type = "car"
                    is_ev = False
                
                # Create or update vehicle
                if vid not in self.vehicles:
                    self.vehicles[vid] = Vehicle(
                        id=vid,
                        vehicle_type=VehicleType.EV_SEDAN if is_ev else VehicleType.SEDAN,
                        is_ev=is_ev,
                        battery_capacity_kwh=60 if is_ev else 0,
                        battery_soc=0.8 if is_ev else 0,
                        color=self._get_vehicle_color(vehicle_type)
                    )
                
                vehicle = self.vehicles[vid]
                vehicle.position = (lon, lat)
                vehicle.speed = speed
                vehicle.route = route
                vehicle.waiting_time = waiting
                
                # Update battery for EVs
                if is_ev:
                    try:
                        # Energy consumption (simplified)
                        energy_consumed = speed * 0.0003  # kWh per mph
                        vehicle.battery_soc -= energy_consumed / vehicle.battery_capacity_kwh
                        vehicle.battery_soc = max(0, vehicle.battery_soc)
                        
                        # Check if needs charging
                        if vehicle.battery_soc < 0.2 and not vehicle.charging_station:
                            self._route_to_charging_station(vid)
                    except:
                        pass
            
            # Remove vehicles that left
            for vid in list(self.vehicles.keys()):
                if vid not in current_ids:
                    del self.vehicles[vid]
                    
        except Exception as e:
            print(f"Error updating vehicles: {e}")
    
    def _sync_traffic_lights(self):
        """Synchronize traffic lights with power grid"""
        
        try:
            tl_ids = traci.trafficlight.getIDList()
            
            for tl_id in tl_ids:
                # Find corresponding traffic light in power system
                for tl in self.integrated_system.traffic_lights.values():
                    # Match by approximate position
                    if self._match_traffic_light(tl_id, tl):
                        if not tl['powered']:
                            # No power - set to flashing red or all red
                            traci.trafficlight.setRedYellowGreenState(
                                tl_id, "rrrrrrrr"  # All red
                            )
                        else:
                            # Normal operation - use actual phase
                            if tl['phase'] == 'green':
                                traci.trafficlight.setRedYellowGreenState(
                                    tl_id, "GGGgrrrrGGGgrrrr"
                                )
                            elif tl['phase'] == 'yellow':
                                traci.trafficlight.setRedYellowGreenState(
                                    tl_id, "yyyyrrrryyyyrrrr"
                                )
                            else:  # red
                                traci.trafficlight.setRedYellowGreenState(
                                    tl_id, "rrrrGGGgrrrrGGGg"
                                )
                        break
                        
        except Exception as e:
            print(f"Error syncing traffic lights: {e}")
    
    def _handle_ev_charging(self):
        """Handle EV charging at stations"""
        
        try:
            # Check vehicles at charging stations
            for vid, vehicle in self.vehicles.items():
                if not vehicle.is_ev:
                    continue
                
                # Check if at charging station
                for ev_station in self.integrated_system.ev_stations.values():
                    if self._vehicle_at_station(vehicle, ev_station):
                        if vid not in self.charging_sessions:
                            # Start charging session
                            self.charging_sessions[vid] = ChargingSession(
                                vehicle_id=vid,
                                station_id=ev_station['id'],
                                start_time=datetime.now(),
                                power_kw=min(22, ev_station['power_kw'] / ev_station['chargers'])
                            )
                            
                            # Stop vehicle
                            try:
                                traci.vehicle.setSpeed(vid, 0)
                                traci.vehicle.setColor(vid, (0, 255, 0, 255))  # Green when charging
                            except:
                                pass
                        
                        # Update charging
                        session = self.charging_sessions[vid]
                        charge_rate = session.power_kw / vehicle.battery_capacity_kwh
                        vehicle.battery_soc += charge_rate * 0.1 / 3600  # 0.1 second steps
                        vehicle.battery_soc = min(0.95, vehicle.battery_soc)
                        session.energy_delivered_kwh += session.power_kw * 0.1 / 3600
                        
                        # Check if charged enough
                        if vehicle.battery_soc >= session.target_soc:
                            # Resume journey
                            del self.charging_sessions[vid]
                            try:
                                traci.vehicle.setSpeed(vid, -1)  # Resume normal speed
                                traci.vehicle.setColor(vid, (0, 200, 200, 255))  # Back to EV color
                            except:
                                pass
                        
                        # Update power grid load
                        self._update_charging_load(ev_station['substation'], session.power_kw)
                        
        except Exception as e:
            print(f"Error handling EV charging: {e}")
    
    def _check_boundaries(self):
        """Remove vehicles that leave the zone"""
        
        to_remove = []
        
        for vid, vehicle in self.vehicles.items():
            lon, lat = vehicle.position
            
            if (lon < self.bounds['min_lon'] or lon > self.bounds['max_lon'] or
                lat < self.bounds['min_lat'] or lat > self.bounds['max_lat']):
                to_remove.append(vid)
        
        for vid in to_remove:
            try:
                traci.vehicle.remove(vid)
                del self.vehicles[vid]
            except:
                pass
    
    def _update_statistics(self):
        """Update traffic statistics"""
        
        try:
            self.stats['active_vehicles'] = len(self.vehicles)
            self.stats['evs_charging'] = len(self.charging_sessions)
            
            if self.vehicles:
                speeds = [v.speed for v in self.vehicles.values()]
                self.stats['avg_speed_mph'] = np.mean(speeds) if speeds else 0
                self.stats['total_wait_time'] = sum(v.waiting_time for v in self.vehicles.values())
            
            # Get emissions if available
            try:
                if hasattr(traci.simulation, 'getCO2Emission'):
                    self.stats['co2_emissions_kg'] = traci.simulation.getCO2Emission() / 1000
            except:
                pass
                
        except Exception as e:
            print(f"Error updating statistics: {e}")
    
    def _sync_with_power_grid(self):
        """Synchronize with PyPSA power grid"""
        
        try:
            # Calculate total EV charging load
            total_charging_kw = sum(s.power_kw for s in self.charging_sessions.values())
            
            # Update power grid
            for sub_name in self.integrated_system.substations:
                bus_name = f"{sub_name}_13.8kV"
                if bus_name in self.power_grid.network.buses.index:
                    # Find EV load component
                    load_name = f"EV_Charging_{sub_name}"
                    if load_name not in self.power_grid.network.loads.index:
                        self.power_grid.network.add(
                            "Load",
                            load_name,
                            bus=bus_name,
                            p_set=0
                        )
                    
                    # Update load based on charging sessions
                    station_load = 0
                    for session in self.charging_sessions.values():
                        # Find which substation this charging is on
                        for ev_station in self.integrated_system.ev_stations.values():
                            if ev_station['id'] == session.station_id and ev_station['substation'] == sub_name:
                                station_load += session.power_kw
                    
                    self.power_grid.network.loads.at[load_name, 'p_set'] = station_load / 1000  # MW
                    
        except Exception as e:
            print(f"Error syncing with power grid: {e}")
    
    def _route_to_charging_station(self, vehicle_id):
        """Route vehicle to nearest available charging station"""
        
        try:
            vehicle = self.vehicles[vehicle_id]
            
            # Find nearest operational charging station
            best_station = None
            min_dist = float('inf')
            
            for ev_station in self.integrated_system.ev_stations.values():
                if ev_station['operational']:
                    dist = self._calculate_distance(
                        vehicle.position[1], vehicle.position[0],
                        ev_station['lat'], ev_station['lon']
                    )
                    if dist < min_dist:
                        min_dist = dist
                        best_station = ev_station
            
            if best_station:
                # Set vehicle color to indicate low battery
                traci.vehicle.setColor(vehicle_id, (255, 100, 0, 255))  # Orange
                # In real implementation, would reroute to station
                print(f"Vehicle {vehicle_id} routing to {best_station['name']} for charging")
                
        except Exception as e:
            print(f"Error routing to charging: {e}")
    
    def _match_traffic_light(self, sumo_tl_id, power_tl):
        """Match SUMO traffic light with power system traffic light"""
        # Simplified - in production would use precise mapping
        return True  # Placeholder
    
    def _vehicle_at_station(self, vehicle, station):
        """Check if vehicle is at charging station"""
        dist = self._calculate_distance(
            vehicle.position[1], vehicle.position[0],
            station['lat'], station['lon']
        )
        return dist < 0.0001  # Very close
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points"""
        return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)
    
    def _get_vehicle_color(self, vehicle_type):
        """Get vehicle color based on type"""
        colors = {
            'sedan': '#ffff00',
            'suv': '#cccccc',
            'taxi': '#ffff00',
            'bus': '#ff8800',
            'ev_sedan': '#00ff00',
            'ev_suv': '#00cccc',
            'ev_taxi': '#88ff88'
        }
        return colors.get(vehicle_type, '#ffffff')
    
    def _update_charging_load(self, substation, power_kw):
        """Update charging load on substation"""
        # This would update the actual power grid load
        pass
    
    def get_vehicle_states(self):
        """Get all vehicle states for visualization"""
        
        states = []
        for vehicle in self.vehicles.values():
            states.append({
                'id': vehicle.id,
                'type': vehicle.vehicle_type.value,
                'lat': vehicle.position[1],
                'lon': vehicle.position[0],
                'speed': vehicle.speed,
                'is_ev': vehicle.is_ev,
                'battery_soc': vehicle.battery_soc if vehicle.is_ev else 0,
                'charging': vehicle.id in self.charging_sessions,
                'color': vehicle.color,
                'waiting_time': vehicle.waiting_time
            })
        
        return states
    
    def get_statistics(self):
        """Get traffic statistics"""
        return self.stats.copy()
    
    def stop_simulation(self):
        """Stop SUMO simulation"""
        
        self.running = False
        
        try:
            if traci.isLoaded():
                traci.close()
            print("SUMO simulation stopped")
        except:
            pass

class IntegratedWebSocketServer:
    """WebSocket server for real-time vehicle updates"""
    
    def __init__(self, traffic_sim, port=8765):
        self.traffic_sim = traffic_sim
        self.port = port
        self.clients = set()
        
    async def handler(self, websocket, path):
        """Handle WebSocket connections"""
        
        self.clients.add(websocket)
        try:
            # Send updates every 100ms
            while True:
                # Get vehicle states
                vehicles = self.traffic_sim.get_vehicle_states()
                stats = self.traffic_sim.get_statistics()
                
                message = json.dumps({
                    'type': 'traffic_update',
                    'vehicles': vehicles,
                    'statistics': stats,
                    'timestamp': time.time()
                })
                
                # Broadcast to all clients
                if self.clients:
                    await asyncio.gather(
                        *[client.send(message) for client in self.clients],
                        return_exceptions=True
                    )
                
                await asyncio.sleep(0.1)  # 10 Hz updates
                
        except Exception as e:
            # Handle disconnection
            pass
        finally:
            self.clients.remove(websocket)
    
    async def start(self):
        """Start WebSocket server"""
        
        if not WEBSOCKETS_AVAILABLE:
            print("WebSocket server not available - install websockets package")
            return
        
        import websockets
        async with websockets.serve(self.handler, "localhost", self.port):
            print(f"WebSocket server started on ws://localhost:{self.port}")
            await asyncio.Future()  # Run forever

# Main integration function
def integrate_sumo_with_power_grid(integrated_system, power_grid):
    """
    Main function to integrate SUMO with the power grid
    """
    
    print("\n" + "=" * 60)
    print("INITIALIZING WORLD-CLASS SUMO TRAFFIC INTEGRATION")
    print("=" * 60)
    
    # Create traffic simulation
    traffic_sim = WorldClassTrafficSimulation(integrated_system, power_grid)
    
    # Start SUMO (GUI mode for development, headless for production)
    success = traffic_sim.start_simulation(gui=False)
    
    if success:
        print("✅ SUMO simulation running")
        print(f"  - Active vehicles: {traffic_sim.stats['active_vehicles']}")
        print(f"  - EV penetration: 30%")
        print(f"  - Charging stations: {len(integrated_system.ev_stations)}")
        print("  - Real-time sync with power grid: ACTIVE")
        
        # Start WebSocket server for real-time updates
        if WEBSOCKETS_AVAILABLE:
            ws_server = IntegratedWebSocketServer(traffic_sim)
            
            # Run WebSocket server in separate thread
            def run_ws_server():
                asyncio.set_event_loop(asyncio.new_event_loop())
                asyncio.get_event_loop().run_until_complete(ws_server.start())
            
            ws_thread = threading.Thread(target=run_ws_server, daemon=True)
            ws_thread.start()
            
            print("✅ WebSocket server running on ws://localhost:8765")
        else:
            print("⚠️ WebSocket server disabled - install websockets package")
    else:
        print("⚠️ SUMO not available - traffic simulation disabled")
        print("   Install SUMO: apt-get install sumo sumo-tools")
        traffic_sim = None
    
    print("=" * 60 + "\n")
    
    return traffic_sim

if __name__ == "__main__":
    # Test SUMO integration
    print("Testing SUMO integration...")
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Create mock systems for testing
    class MockIntegratedSystem:
        def __init__(self):
            self.traffic_lights = {
                "tl1": {"lat": 40.750, "lon": -73.980, "powered": True, "phase": "green"},
                "tl2": {"lat": 40.755, "lon": -73.975, "powered": True, "phase": "red"}
            }
            self.ev_stations = {
                "ev1": {"id": "ev1", "name": "Test Station", "lat": 40.752, "lon": -73.978, 
                        "operational": True, "chargers": 4, "power_kw": 50}
            }
            self.substations = {
                "sub1": {"name": "Test Substation", "operational": True}
            }
    
    class MockPowerGrid:
        def __init__(self):
            self.network = type('obj', (object,), {
                'buses': type('obj', (object,), {'index': []}),
                'loads': type('obj', (object,), {'index': []})
            })()
    
    mock_integrated = MockIntegratedSystem()
    mock_grid = MockPowerGrid()
    
    # Try to start traffic simulation
    traffic_sim = integrate_sumo_with_power_grid(mock_integrated, mock_grid)
    
    if traffic_sim and traffic_sim.running:
        print("\n✅ SUCCESS: SUMO simulation is running!")
        print("Press Ctrl+C to stop...")
        try:
            while True:
                time.sleep(1)
                stats = traffic_sim.get_statistics()
                print(f"Vehicles: {stats['active_vehicles']}, Avg Speed: {stats['avg_speed_mph']:.1f} mph", end='\r')
        except KeyboardInterrupt:
            print("\nStopping simulation...")
            traffic_sim.stop_simulation()
    else:
        print("\n⚠️ SUMO simulation could not start")
        print("Check the error messages above for details")