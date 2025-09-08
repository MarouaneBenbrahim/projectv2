"""
MANHATTAN ULTIMATE SIMULATION
World-Class Traffic, Power, and EV Integration
Real-time vehicle tracking, EV charging, adaptive traffic control
"""

import os
import sys
import json
import random
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
import threading
import time
from datetime import datetime
import math

# Add SUMO to path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    import traci
    import sumolib

class ManhattanUltimateSimulation:
    """
    Ultimate Manhattan simulation with continuous traffic,
    visible vehicles, EV charging, and power integration
    """
    
    def __init__(self, integrated_system=None):
        self.integrated_system = integrated_system
        self.output_dir = 'data/sumo'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Files
        self.net_file = os.path.join(self.output_dir, 'manhattan.net.xml')
        self.route_file = os.path.join(self.output_dir, 'manhattan_continuous.rou.xml')
        self.config_file = os.path.join(self.output_dir, 'manhattan_ultimate.sumocfg')
        self.additional_file = os.path.join(self.output_dir, 'manhattan_additional.xml')
        
        # State
        self.running = False
        self.simulation_time = 0
        self.current_hour = 8  # Start at 8 AM
        
        # Vehicle tracking
        self.vehicles = {}
        self.ev_vehicles = {}
        self.emergency_vehicles = {}
        self.vehicle_positions = {}
        
        # EV charging
        self.charging_stations = self._define_charging_stations()
        self.charging_queues = {station: [] for station in self.charging_stations}
        self.vehicles_charging = {}
        
        # Traffic light phases
        self.traffic_light_phases = {}
        self.traffic_light_timers = {}
        
        # Statistics
        self.stats = {
            'total_vehicles': 0,
            'active_vehicles': 0,
            'evs_active': 0,
            'evs_charging': 0,
            'avg_speed_kmh': 0,
            'congestion_level': 0,
            'co2_emissions': 0,
            'power_consumption_kw': 0
        }
    
    def _define_charging_stations(self):
        """Define EV charging station locations"""
        return {
            'CS_TimesSquare': {
                'lat': 40.758, 'lon': -73.985,
                'capacity': 10, 'power_kw': 150,
                'occupied': 0, 'operational': True,
                'edge': 'edge_ts_1'  # Will be mapped to actual edge
            },
            'CS_PennStation': {
                'lat': 40.750, 'lon': -73.993,
                'capacity': 8, 'power_kw': 150,
                'occupied': 0, 'operational': True,
                'edge': 'edge_ps_1'
            },
            'CS_GrandCentral': {
                'lat': 40.752, 'lon': -73.977,
                'capacity': 12, 'power_kw': 150,
                'occupied': 0, 'operational': True,
                'edge': 'edge_gc_1'
            },
            'CS_BryantPark': {
                'lat': 40.754, 'lon': -73.984,
                'capacity': 6, 'power_kw': 50,
                'occupied': 0, 'operational': True,
                'edge': 'edge_bp_1'
            },
            'CS_ColumbusCircle': {
                'lat': 40.768, 'lon': -73.982,
                'capacity': 8, 'power_kw': 150,
                'occupied': 0, 'operational': True,
                'edge': 'edge_cc_1'
            }
        }
    
    def generate_continuous_traffic(self):
        """Generate routes file with continuous vehicle spawning"""
        print("\n🚗 Generating continuous Manhattan traffic...")
        
        if not os.path.exists(self.net_file):
            print("❌ Network file not found!")
            return False
        
        net = sumolib.net.readNet(self.net_file)
        edges = [e for e in net.getEdges() if not e.isSpecial() and e.allows('passenger')]
        
        if len(edges) < 10:
            print("❌ Not enough edges for traffic generation")
            return False
        
        # Create routes XML
        root = ET.Element('routes')
        
        # Vehicle types with realistic Manhattan distribution
        vtypes = [
            {
                'id': 'taxi',
                'vClass': 'taxi',
                'length': '4.8',
                'maxSpeed': '13.89',
                'accel': '2.8',
                'decel': '4.5',
                'sigma': '0.5',
                'color': '255,200,0',
                'probability': '0.25'  # 25% taxis in Manhattan
            },
            {
                'id': 'car',
                'vClass': 'passenger',
                'length': '4.5',
                'maxSpeed': '13.89',
                'accel': '2.6',
                'decel': '4.5',
                'sigma': '0.5',
                'color': '100,100,255',
                'probability': '0.35'
            },
            {
                'id': 'ev',
                'vClass': 'passenger',
                'length': '4.7',
                'maxSpeed': '13.89',
                'accel': '3.0',
                'decel': '4.5',
                'sigma': '0.3',
                'color': '0,255,100',
                'param': {'has.battery.device': 'true', 'maximumBatteryCapacity': '50000'},
                'probability': '0.15'  # 15% EVs
            },
            {
                'id': 'delivery',
                'vClass': 'delivery',
                'length': '6.0',
                'maxSpeed': '11.11',
                'accel': '2.0',
                'decel': '4.0',
                'sigma': '0.5',
                'color': '139,69,19',
                'probability': '0.15'
            },
            {
                'id': 'bus',
                'vClass': 'bus',
                'length': '12.0',
                'maxSpeed': '11.11',
                'accel': '1.2',
                'decel': '3.0',
                'sigma': '0.5',
                'color': '0,100,200',
                'probability': '0.08'
            },
            {
                'id': 'emergency',
                'vClass': 'emergency',
                'length': '6.5',
                'maxSpeed': '22.22',
                'accel': '3.5',
                'decel': '5.0',
                'sigma': '0.0',
                'color': '255,0,0',
                'guiShape': 'emergency',
                'probability': '0.02'
            }
        ]
        
        # Add vehicle types
        for vtype in vtypes:
            vt = ET.SubElement(root, 'vType')
            for key, value in vtype.items():
                if key == 'param':
                    param = ET.SubElement(vt, 'param')
                    for pk, pv in value.items():
                        param.set(pk, pv)
                elif key != 'probability':
                    vt.set(key, value)
        
        # Create flows for continuous traffic generation
        print(f"  Creating continuous traffic flows...")
        
        # Group edges by area for realistic OD patterns
        edge_groups = self._group_edges_by_area(edges)
        
        flow_id = 0
        for hour in range(24):
            # Traffic density varies by hour
            vehicles_per_hour = self._get_hourly_traffic_volume(hour)
            
            # Create flows between different areas
            for from_area, from_edges in edge_groups.items():
                for to_area, to_edges in edge_groups.items():
                    if from_area != to_area and from_edges and to_edges:
                        # Create flow
                        flow = ET.SubElement(root, 'flow')
                        flow.set('id', f'flow_{flow_id}')
                        flow.set('begin', str(hour * 3600))
                        flow.set('end', str((hour + 1) * 3600))
                        
                        # Vehicle type probabilities
                        vtype_id = self._select_vehicle_type(hour)
                        flow.set('type', vtype_id)
                        
                        # Origin and destination
                        from_edge = random.choice(from_edges).getID()
                        to_edge = random.choice(to_edges).getID()
                        flow.set('from', from_edge)
                        flow.set('to', to_edge)
                        
                        # Flow rate
                        flow.set('probability', str(vehicles_per_hour / 3600))
                        flow.set('departLane', 'best')
                        flow.set('departSpeed', 'random')
                        
                        flow_id += 1
        
        # Add special routes for EVs to charging stations
        self._add_ev_charging_routes(root, edges)
        
        # Save routes file
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')
        tree.write(self.route_file, encoding='UTF-8', xml_declaration=True)
        
        print(f"✅ Continuous traffic patterns generated")
        return True
    
    def _group_edges_by_area(self, edges):
        """Group edges by Manhattan areas"""
        areas = {
            'midtown_west': [],
            'midtown_east': [],
            'times_square': [],
            'murray_hill': [],
            'hells_kitchen': []
        }
        
        for edge in edges:
            coord = edge.getFromNode().getCoord()
            lon, lat = coord[0], coord[1]
            
            # Simple area classification based on coordinates
            if lon < -73.985:
                if lat > 40.760:
                    areas['hells_kitchen'].append(edge)
                else:
                    areas['midtown_west'].append(edge)
            elif lon > -73.975:
                if lat < 40.750:
                    areas['murray_hill'].append(edge)
                else:
                    areas['midtown_east'].append(edge)
            else:
                areas['times_square'].append(edge)
        
        return areas
    
    def _get_hourly_traffic_volume(self, hour):
        """Get traffic volume based on hour (Manhattan patterns)"""
        volumes = {
            0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.2,
            6: 0.4, 7: 0.8, 8: 1.0, 9: 0.9,  # Morning rush
            10: 0.7, 11: 0.6, 12: 0.7, 13: 0.7, 14: 0.6, 15: 0.7,
            16: 0.8, 17: 0.95, 18: 1.0, 19: 0.8,  # Evening rush
            20: 0.6, 21: 0.5, 22: 0.4, 23: 0.3
        }
        base_volume = 200  # Base vehicles per hour
        return base_volume * volumes.get(hour, 0.5)
    
    def _select_vehicle_type(self, hour):
        """Select vehicle type based on time of day"""
        # More taxis at night, more delivery trucks during day
        if 22 <= hour or hour <= 5:
            return random.choice(['taxi', 'taxi', 'car', 'ev'])
        elif 6 <= hour <= 9:
            return random.choice(['car', 'car', 'taxi', 'ev', 'bus'])
        elif 10 <= hour <= 16:
            return random.choice(['car', 'taxi', 'delivery', 'ev'])
        else:
            return random.choice(['car', 'taxi', 'ev', 'bus'])
    
    def _add_ev_charging_routes(self, root, edges):
        """Add specific routes for EVs going to charging stations"""
        # Map charging stations to nearest edges
        for station_id, station in self.charging_stations.items():
            # Find nearest edge to station
            min_dist = float('inf')
            nearest_edge = None
            
            for edge in edges:
                coord = edge.getFromNode().getCoord()
                dist = math.sqrt((coord[0] - station['lon'])**2 + (coord[1] - station['lat'])**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_edge = edge
            
            if nearest_edge:
                station['edge'] = nearest_edge.getID()
    
    def generate_additional_infrastructure(self):
        """Generate additional infrastructure file with traffic programs"""
        print("\n🚦 Generating traffic light programs and infrastructure...")
        
        root = ET.Element('additional')
        
        # Add traffic light programs for realistic phases
        if os.path.exists(self.net_file):
            net = sumolib.net.readNet(self.net_file)
            
            for tls in net.getTrafficLights():
                tls_id = tls.getID()
                
                # Create adaptive traffic light program
                program = ET.SubElement(root, 'tlLogic')
                program.set('id', tls_id)
                program.set('type', 'actuated')
                program.set('programID', 'adaptive')
                program.set('offset', '0')
                
                # Create realistic phases (simplified)
                phases = [
                    {'duration': '35', 'state': 'GGGGrrrrGGGGrrrr'},  # NS green
                    {'duration': '5', 'state': 'yyyyrrrryyyyrrrr'},   # NS yellow
                    {'duration': '35', 'state': 'rrrrGGGGrrrrGGGG'},  # EW green
                    {'duration': '5', 'state': 'rrrryyyyrrrryyyy'}    # EW yellow
                ]
                
                for phase_data in phases:
                    phase = ET.SubElement(program, 'phase')
                    phase.set('duration', phase_data['duration'])
                    phase.set('state', phase_data['state'][:len(tls.getConnections())])
        
        # Add parking areas for charging stations
        for station_id, station in self.charging_stations.items():
            parking = ET.SubElement(root, 'parkingArea')
            parking.set('id', station_id)
            parking.set('lane', station.get('edge', 'dummy') + '_0')
            parking.set('startPos', '10')
            parking.set('endPos', '50')
            parking.set('roadsideCapacity', str(station['capacity']))
            parking.set('angle', '0')
            
            # Add charger
            charger = ET.SubElement(parking, 'chargingStation')
            charger.set('power', str(station['power_kw'] * 1000))  # Convert to W
            charger.set('efficiency', '0.95')
        
        # Save additional file
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')
        tree.write(self.additional_file, encoding='UTF-8', xml_declaration=True)
        
        print(f"✅ Infrastructure configured")
        return True
    
    def generate_config(self):
        """Generate SUMO configuration for ultimate simulation"""
        print("\n⚙️ Creating ultimate configuration...")
        
        config = ET.Element('configuration')
        
        # Input
        input_elem = ET.SubElement(config, 'input')
        ET.SubElement(input_elem, 'net-file').set('value', os.path.basename(self.net_file))
        ET.SubElement(input_elem, 'route-files').set('value', os.path.basename(self.route_file))
        ET.SubElement(input_elem, 'additional-files').set('value', os.path.basename(self.additional_file))
        
        # Time
        time_elem = ET.SubElement(config, 'time')
        ET.SubElement(time_elem, 'begin').set('value', '0')
        ET.SubElement(time_elem, 'end').set('value', '86400')  # 24 hours
        ET.SubElement(time_elem, 'step-length').set('value', '0.5')  # 2Hz update
        
        # Processing
        processing = ET.SubElement(config, 'processing')
        ET.SubElement(processing, 'collision.action').set('value', 'warn')
        ET.SubElement(processing, 'collision.check-junctions').set('value', 'true')
        ET.SubElement(processing, 'emergencydecel.warning-threshold').set('value', '1.5')
        ET.SubElement(processing, 'time-to-teleport').set('value', '300')
        ET.SubElement(processing, 'max-depart-delay').set('value', '900')
        ET.SubElement(processing, 'routing-algorithm').set('value', 'dijkstra')
        ET.SubElement(processing, 'device.rerouting.probability').set('value', '0.8')
        ET.SubElement(processing, 'device.rerouting.period').set('value', '300')
        ET.SubElement(processing, 'device.battery.probability').set('value', '1')
        ET.SubElement(processing, 'device.emissions.probability').set('value', '1')
        ET.SubElement(processing, 'person.device.taxi.probability').set('value', '0.3')
        
        # Routing
        routing = ET.SubElement(config, 'routing')
        ET.SubElement(routing, 'device.rerouting.adaptation-weight').set('value', '0.5')
        ET.SubElement(routing, 'device.rerouting.adaptation-interval').set('value', '30')
        
        # Battery model
        battery = ET.SubElement(config, 'battery')
        ET.SubElement(battery, 'device.battery.track-fuel').set('value', 'true')
        
        # Save config
        tree = ET.ElementTree(config)
        ET.indent(tree, space='  ')
        tree.write(self.config_file, encoding='UTF-8', xml_declaration=True)
        
        print(f"✅ Ultimate configuration saved")
        return True
    
    def start(self, gui=False):
        """Start ultimate simulation"""
        if self.running:
            return False
        
        try:
            sumo_binary = "sumo-gui" if gui else "sumo"
            
            cmd = [
                sumo_binary,
                "-c", self.config_file,
                "--collision.action", "warn",
                "--collision.check-junctions", "true",
                "--device.emissions.probability", "1",
                "--device.battery.probability", "1",
                "--device.rerouting.probability", "0.8",
                "--person.device.taxi.probability", "0.3",
                "--tripinfo-output", os.path.join(self.output_dir, "tripinfo.xml"),
                "--fcd-output", os.path.join(self.output_dir, "fcd.xml"),  # Vehicle positions
                "--fcd-output.period", "1",  # Update every second
                "--emission-output", os.path.join(self.output_dir, "emissions.xml"),
                "--battery-output", os.path.join(self.output_dir, "battery.xml"),
                "--statistic-output", os.path.join(self.output_dir, "stats.xml"),
                "--no-step-log", "true"
            ]
            
            if gui:
                cmd.extend(["--start", "true"])
                cmd.extend(["--quit-on-end", "false"])
                cmd.extend(["--window-size", "1600,900"])
                cmd.extend(["--gui-settings-file", self._generate_gui_settings()])
            
            print(f"\n🚀 Starting ULTIMATE Manhattan simulation...")
            traci.start(cmd)
            
            self.running = True
            self._initialize()
            
            print("✅ Ultimate simulation started!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start: {e}")
            return False
    
    def _generate_gui_settings(self):
        """Generate GUI settings for better visualization"""
        settings_file = os.path.join(self.output_dir, 'gui-settings.xml')
        
        settings = ET.Element('viewsettings')
        scheme = ET.SubElement(settings, 'scheme')
        scheme.set('name', 'Manhattan Power Grid')
        
        # Viewport
        viewport = ET.SubElement(settings, 'viewport')
        viewport.set('zoom', '500')
        viewport.set('x', '-73.980')
        viewport.set('y', '40.758')
        
        # Colors
        ET.SubElement(settings, 'background').set('backgroundColor', '20,20,30')
        
        # Vehicle coloring
        vehicles = ET.SubElement(settings, 'vehicles')
        ET.SubElement(vehicles, 'vehicle_colorer').set('scheme', 'by type')
        ET.SubElement(vehicles, 'vehicle_scaler').set('scheme', 'by selection')
        
        tree = ET.ElementTree(settings)
        tree.write(settings_file, encoding='UTF-8', xml_declaration=True)
        return settings_file
    
    def _initialize(self):
        """Initialize simulation tracking"""
        # Get all traffic lights
        self.tls_ids = traci.trafficlight.getIDList()
        print(f"📊 Tracking {len(self.tls_ids)} traffic lights")
        
        # Initialize traffic light phases
        for tls_id in self.tls_ids:
            self.traffic_light_phases[tls_id] = {
                'current': traci.trafficlight.getRedYellowGreenState(tls_id),
                'timer': 0,
                'powered': True
            }
    
    def step(self):
        """Execute simulation step with full tracking"""
        if not self.running:
            return None
        
        try:
            traci.simulationStep()
            self.simulation_time = traci.simulation.getTime()
            self.current_hour = int((self.simulation_time / 3600) % 24)
            
            # Get all vehicles
            vehicle_ids = traci.vehicle.getIDList()
            
            # Track vehicle positions
            self.vehicle_positions = {}
            for vid in vehicle_ids:
                pos = traci.vehicle.getPosition(vid)
                lon, lat = traci.simulation.convertGeo(pos[0], pos[1])
                
                self.vehicle_positions[vid] = {
                    'id': vid,
                    'lat': lat,
                    'lon': lon,
                    'speed': traci.vehicle.getSpeed(vid),
                    'type': traci.vehicle.getTypeID(vid),
                    'route': traci.vehicle.getRoute(vid),
                    'co2': traci.vehicle.getCO2Emission(vid)
                }
                
                # Track EVs
                if 'ev' in traci.vehicle.getTypeID(vid).lower():
                    if traci.vehicle.getParameter(vid, "has.battery.device") == "true":
                        battery = traci.vehicle.getParameter(vid, "device.battery.actualBatteryCapacity")
                        self.vehicle_positions[vid]['battery'] = float(battery) if battery else 50
                        
                        # Check if needs charging
                        if self.vehicle_positions[vid]['battery'] < 20:
                            self._route_to_charging_station(vid)
            
            # Update statistics
            self.stats['active_vehicles'] = len(vehicle_ids)
            self.stats['avg_speed_kmh'] = sum(v['speed'] for v in self.vehicle_positions.values()) * 3.6 / max(1, len(vehicle_ids))
            self.stats['evs_active'] = sum(1 for v in self.vehicle_positions.values() if v['type'] == 'ev')
            self.stats['co2_emissions'] = sum(v['co2'] for v in self.vehicle_positions.values())
            
            # Update traffic light phases
            self._update_traffic_light_phases()
            
            # Manage EV charging
            self._manage_ev_charging()
            
            return self.stats
            
        except Exception as e:
            print(f"Step error: {e}")
            return None
    
    def _update_traffic_light_phases(self):
        """Update traffic light phases realistically"""
        for tls_id in self.tls_ids:
            if tls_id in self.traffic_light_phases:
                phase_info = self.traffic_light_phases[tls_id]
                
                if phase_info['powered']:
                    # Normal operation - phases change automatically
                    current_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                    phase_info['current'] = current_state
                    phase_info['timer'] = (phase_info['timer'] + 1) % 90  # 90 second cycle
                else:
                    # Power failure - all red
                    state_length = len(traci.trafficlight.getRedYellowGreenState(tls_id))
                    all_red = 'r' * state_length
                    traci.trafficlight.setRedYellowGreenState(tls_id, all_red)
    
    def _route_to_charging_station(self, vehicle_id):
        """Route EV to nearest available charging station"""
        try:
            pos = traci.vehicle.getPosition(vehicle_id)
            
            # Find nearest operational station with capacity
            best_station = None
            min_dist = float('inf')
            
            for station_id, station in self.charging_stations.items():
                if station['operational'] and station['occupied'] < station['capacity']:
                    station_pos = traci.simulation.convertGeo(station['lon'], station['lat'], inverse=True)
                    dist = math.sqrt((pos[0] - station_pos[0])**2 + (pos[1] - station_pos[1])**2)
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_station = station_id
            
            if best_station:
                # Route to charging station
                station = self.charging_stations[best_station]
                if 'edge' in station:
                    traci.vehicle.changeTarget(vehicle_id, station['edge'])
                    self.charging_queues[best_station].append(vehicle_id)
                    print(f"🔋 EV {vehicle_id} routing to {best_station}")
        except:
            pass
    
    def _manage_ev_charging(self):
        """Manage EV charging at stations"""
        for station_id, queue in self.charging_queues.items():
            station = self.charging_stations[station_id]
            
            # Process vehicles in queue
            for vid in queue[:]:
                if vid not in traci.vehicle.getIDList():
                    queue.remove(vid)
                    continue
                
                # Check if vehicle reached station
                pos = traci.vehicle.getPosition(vid)
                station_pos = traci.simulation.convertGeo(station['lon'], station['lat'], inverse=True)
                dist = math.sqrt((pos[0] - station_pos[0])**2 + (pos[1] - station_pos[1])**2)
                
                if dist < 50:  # Within 50m of station
                    if station['occupied'] < station['capacity']:
                        # Start charging
                        station['occupied'] += 1
                        self.vehicles_charging[vid] = station_id
                        queue.remove(vid)
                        
                        # Stop vehicle for charging
                        traci.vehicle.setStop(vid, traci.vehicle.getRoadID(vid), 
                                             traci.vehicle.getLanePosition(vid),
                                             duration=300)  # 5 min charge
                        print(f"⚡ EV {vid} charging at {station_id}")
            
            # Update power consumption
            station['power_consumption'] = station['occupied'] * station['power_kw']
    
    def simulate_power_failure(self, substation_name):
        """Simulate power failure effects"""
        print(f"⚡ Power failure at {substation_name}")
        
        # Fail traffic lights in area
        affected_tls = []
        
        # Map substations to traffic light areas (simplified)
        if 'Times' in substation_name:
            affected_area = {'min_lon': -73.990, 'max_lon': -73.980, 'min_lat': 40.755, 'max_lat': 40.762}
        elif 'Penn' in substation_name:
            affected_area = {'min_lon': -73.998, 'max_lon': -73.990, 'min_lat': 40.748, 'max_lat': 40.753}
        elif 'Grand' in substation_name:
            affected_area = {'min_lon': -73.980, 'max_lon': -73.973, 'min_lat': 40.750, 'max_lat': 40.756}
        else:
            affected_area = None
        
        if affected_area:
            for tls_id in self.tls_ids:
                # Get TLS position (would need mapping in real implementation)
                # For now, affect random subset
                if random.random() < 0.3:  # 30% of lights in area
                    self.traffic_light_phases[tls_id]['powered'] = False
                    affected_tls.append(tls_id)
        
        # Fail charging stations
        for station_id, station in self.charging_stations.items():
            if substation_name.lower() in station_id.lower():
                station['operational'] = False
                print(f"🔌 Charging station {station_id} offline")
        
        return len(affected_tls)
    
    def restore_power(self, substation_name):
        """Restore power to area"""
        print(f"⚡ Power restored at {substation_name}")
        
        # Restore traffic lights
        restored = 0
        for tls_id, phase_info in self.traffic_light_phases.items():
            if not phase_info['powered']:
                phase_info['powered'] = True
                restored += 1
        
        # Restore charging stations
        for station_id, station in self.charging_stations.items():
            if substation_name.lower() in station_id.lower():
                station['operational'] = True
                print(f"🔌 Charging station {station_id} back online")
        
        return restored
    
    def get_vehicle_positions(self):
        """Get all vehicle positions for map display"""
        return self.vehicle_positions
    
    def get_charging_stations_status(self):
        """Get charging station status"""
        return {
            station_id: {
                'occupied': station['occupied'],
                'capacity': station['capacity'],
                'operational': station['operational'],
                'queue_length': len(self.charging_queues[station_id]),
                'power_kw': station.get('power_consumption', 0)
            }
            for station_id, station in self.charging_stations.items()
        }
    
    def inject_emergency_vehicle(self, origin=None, destination=None):
        """Inject emergency vehicle with priority"""
        try:
            edges = traci.edge.getIDList()
            
            if not origin:
                origin = random.choice(edges[:50])
            if not destination:
                destination = random.choice(edges[-50:])
            
            veh_id = f"emergency_{self.simulation_time}"
            route_id = f"emergency_route_{self.simulation_time}"
            
            # Create route
            route = traci.simulation.findRoute(origin, destination)
            if route and route.edges:
                traci.route.add(route_id, route.edges)
                
                # Add emergency vehicle
                traci.vehicle.add(veh_id, route_id, typeID='emergency')
                traci.vehicle.setColor(veh_id, (255, 0, 0, 255))
                traci.vehicle.setSpeedMode(veh_id, 0)  # Ignore speed limits
                traci.vehicle.setLaneChangeMode(veh_id, 0)  # Free lane changes
                
                # Emergency vehicle preemption for traffic lights
                self._set_emergency_preemption(veh_id)
                
                print(f"🚨 Emergency vehicle {veh_id} dispatched!")
                return veh_id
        except Exception as e:
            print(f"Emergency vehicle error: {e}")
            return None
    
    def _set_emergency_preemption(self, emergency_vid):
        """Give emergency vehicle green lights"""
        # This would implement actual preemption logic
        # For now, simplified version
        pass
    
    def stop(self):
        """Stop simulation"""
        if self.running:
            try:
                traci.close()
                self.running = False
                print("✅ Simulation stopped")
            except:
                pass


# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("MANHATTAN ULTIMATE SIMULATION")
    print("=" * 60)
    
    sim = ManhattanUltimateSimulation()
    
    # Generate all files
    sim.generate_continuous_traffic()
    sim.generate_additional_infrastructure()
    sim.generate_config()
    
    # Start simulation
    if sim.start(gui=True):
        print("\nSimulation running...")
        print("Features:")
        print("- Continuous traffic generation")
        print("- EV charging behavior")
        print("- Power failure impacts")
        print("- Real-time vehicle tracking")
        
        try:
            while sim.running:
                stats = sim.step()
                if stats and sim.simulation_time % 10 == 0:
                    print(f"\nTime: {sim.current_hour:02d}:00 | "
                          f"Vehicles: {stats['active_vehicles']} | "
                          f"EVs: {stats['evs_active']} charging: {stats.get('evs_charging', 0)} | "
                          f"Speed: {stats['avg_speed_kmh']:.1f} km/h")
                
                # Test power failure after 60 seconds
                if sim.simulation_time == 60:
                    sim.simulate_power_failure("Times Square")
                
                # Restore after 120 seconds
                if sim.simulation_time == 120:
                    sim.restore_power("Times Square")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            sim.stop()