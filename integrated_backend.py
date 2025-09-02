"""
Manhattan Power Grid - Complete Integrated Backend
Includes: Power Distribution + Realistic Traffic Control + Vehicle Simulation
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import os
from dataclasses import dataclass, field
from enum import Enum
import math
import random
from datetime import datetime, timedelta
import threading
import time

# Import the realistic traffic controller
try:
    from manhattan_traffic_control import (
        ManhattanTrafficController, 
        TrafficLight,
        TrafficPhase,
        TimeOfDay
    )
    TRAFFIC_CONTROL_AVAILABLE = True
except ImportError:
    print("⚠️ manhattan_traffic_control.py not found - using basic traffic lights")
    TRAFFIC_CONTROL_AVAILABLE = False

# Import SUMO runner if available
try:
    from manhattan_sumo_runner import ManhattanSUMORunner
    SUMO_AVAILABLE = True
except ImportError:
    print("⚠️ SUMO integration not available - continuing without vehicles")
    SUMO_AVAILABLE = False

class PowerComponent(Enum):
    """Power system hierarchy"""
    TRANSMISSION_SUBSTATION = "transmission_substation"
    DISTRIBUTION_SUBSTATION = "distribution_substation"
    DISTRIBUTION_TRANSFORMER = "distribution_transformer"
    TRAFFIC_LIGHT = "traffic_light"
    EV_STATION = "ev_station"

@dataclass
class DistributionTransformer:
    """Distribution transformer (13.8kV to 480V)"""
    id: str
    name: str
    lat: float
    lon: float
    substation: str
    capacity_kva: float = 500
    load_kw: float = 0
    traffic_lights: List[str] = field(default_factory=list)
    operational: bool = True

class ManhattanIntegratedSystemV2:
    """
    World-class integrated power and traffic system
    Version 2: Realistic traffic control + Vehicle simulation support
    """
    
    def __init__(self, power_grid):
        self.power_grid = power_grid
        
        # Initialize traffic controller if available
        if TRAFFIC_CONTROL_AVAILABLE:
            self.traffic_controller = ManhattanTrafficController()
        else:
            self.traffic_controller = None
        
        # Initialize SUMO if available
        self.sumo_runner = None
        self.sumo_thread = None
        self.vehicles_enabled = False
        
        # Electrical hierarchy
        self.substations = {}
        self.distribution_transformers = {}
        self.ev_stations = {}
        
        # Cable routing - KEEP ALL YOUR CABLES
        self.primary_cables = []
        self.secondary_cables = []
        
        # System time
        self.system_time = datetime.now()
        self.simulation_speed = 1.0
        
        # Manhattan boundaries
        self.manhattan_bounds = {
            'min_lat': 40.745,
            'max_lat': 40.775,
            'min_lon': -74.010,
            'max_lon': -73.960
        }
        
        # Build the system
        self._initialize_system()
        
        # Start simulation threads
        self.simulation_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        
        # Start vehicle simulation if available
        if SUMO_AVAILABLE:
            self._start_vehicle_simulation()
    
    def _initialize_system(self):
        """Initialize complete system"""
        
        print("Initializing Manhattan Integrated System V2...")
        
        # Load or generate traffic lights
        lights_data = self._load_traffic_lights()
        
        # Initialize traffic controller with lights if available
        if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
            self.traffic_controller.initialize_traffic_lights(lights_data)
            print(f"✅ Realistic traffic control initialized with {len(self.traffic_controller.traffic_lights)} lights")
        else:
            # Fallback to simple traffic lights
            self.traffic_lights = {}
            for light in lights_data:
                self.traffic_lights[str(light['id'])] = {
                    'id': str(light['id']),
                    'lat': light['lat'],
                    'lon': light['lon'],
                    'powered': True,
                    'color': '#ff0000',
                    'phase': 'normal',
                    'substation': None,
                    'transformer': None
                }
        
        # Build power distribution network
        self._build_distribution_network()
        
        # Connect traffic lights to power network
        self._connect_lights_to_power()
        
        # Create cable routes - YOUR FULL CABLE NETWORK
        self._create_all_cable_routes()
        
        # Add EV stations
        self._add_ev_stations()
        
        # Integrate with PyPSA
        self._integrate_with_pypsa()
        
        if TRAFFIC_CONTROL_AVAILABLE:
            print(f"System initialized with {len(self.traffic_controller.traffic_lights)} traffic lights")
            print(f"Traffic control zones: {len(self.traffic_controller.coordination_zones)}")
        else:
            print(f"System initialized with {len(self.traffic_lights)} traffic lights (basic mode)")
    
    def _simulation_loop(self):
        """Background simulation loop for traffic light updates"""
        
        last_update = time.time()
        
        while self.simulation_running:
            try:
                current_time = time.time()
                delta = current_time - last_update
                
                # Advance system time based on simulation speed
                time_advance = timedelta(seconds=delta * self.simulation_speed)
                self.system_time += time_advance
                
                # Update traffic controller if available
                if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
                    if delta >= (1.0 / self.simulation_speed):
                        self.traffic_controller.update(self.system_time)
                        last_update = current_time
                else:
                    # Simple traffic light update
                    if delta >= 2.0:  # Update every 2 seconds
                        self._update_simple_traffic_lights()
                        last_update = current_time
                
                time.sleep(0.1)  # 10 Hz update rate
                
            except Exception as e:
                print(f"Simulation error: {e}")
                time.sleep(1)
    
    def _update_simple_traffic_lights(self):
        """Simple traffic light phase changes when not using realistic controller"""
        
        for tl_id, tl in self.traffic_lights.items():
            if tl['powered']:
                # Simple random phase changes
                rand = random.random()
                if rand < 0.60:
                    tl['color'] = '#ff0000'  # Red
                    tl['phase'] = 'red'
                elif rand < 0.95:
                    tl['color'] = '#00ff00'  # Green
                    tl['phase'] = 'green'
                else:
                    tl['color'] = '#ffff00'  # Yellow
                    tl['phase'] = 'yellow'
            else:
                tl['color'] = '#000000'  # Black when no power
                tl['phase'] = 'off'
    
    def _start_vehicle_simulation(self):
        """Start SUMO vehicle simulation if available"""
        
        if not SUMO_AVAILABLE:
            return
        
        try:
            self.sumo_runner = ManhattanSUMORunner(power_system=self)
            
            # Start SUMO without GUI (headless)
            if self.sumo_runner.start_sumo(gui=False):
                self.vehicles_enabled = True
                
                # Run in background thread
                self.sumo_thread = threading.Thread(
                    target=self.sumo_runner.run_continuous,
                    daemon=True
                )
                self.sumo_thread.start()
                
                print("✅ Vehicle simulation started!")
            else:
                print("⚠️ SUMO not available, continuing without vehicles")
                
        except Exception as e:
            print(f"Vehicle simulation not available: {e}")
            self.vehicles_enabled = False
    
    def _load_traffic_lights(self) -> List[Dict]:
        """Load or generate Manhattan traffic light data"""
        
        filepath = 'data/manhattan_traffic_lights.json'
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        else:
            return self._generate_manhattan_traffic_lights()
    
    def _generate_manhattan_traffic_lights(self) -> List[Dict]:
        """Generate realistic Manhattan traffic light grid"""
        
        lights = []
        light_id = 1
        
        # Major Avenues (North-South) - ACCURATE positions
        avenues = [
            ('12th Ave', -74.008),
            ('11th Ave', -74.004),
            ('10th Ave', -74.000),
            ('9th Ave', -73.996),
            ('8th Ave', -73.992),
            ('7th Ave', -73.989),
            ('Broadway', -73.987),
            ('6th Ave', -73.985),
            ('5th Ave', -73.982),
            ('Madison Ave', -73.979),
            ('Park Ave', -73.976),
            ('Lexington Ave', -73.973),
            ('3rd Ave', -73.970),
            ('2nd Ave', -73.967),
            ('1st Ave', -73.964)
        ]
        
        # Cross streets (34th to 59th)
        base_lat = 40.7486
        
        for st_num in range(34, 60):
            lat = base_lat + (st_num - 34) * 0.00072
            
            for ave_name, lon in avenues:
                if (self.manhattan_bounds['min_lat'] <= lat <= self.manhattan_bounds['max_lat'] and
                    self.manhattan_bounds['min_lon'] <= lon <= self.manhattan_bounds['max_lon']):
                    
                    lights.append({
                        'id': light_id,
                        'lat': lat,
                        'lon': lon,
                        'intersection': f'{ave_name} & {st_num}th St'
                    })
                    light_id += 1
        
        # Save for future use
        os.makedirs('data', exist_ok=True)
        with open('data/manhattan_traffic_lights.json', 'w') as f:
            json.dump(lights, f, indent=2)
        
        return lights
    
    def _build_distribution_network(self):
        """Build REALISTIC Manhattan power distribution network"""
        
        # REAL Con Edison substation locations - KEEP YOUR EXACT SUBSTATIONS
        manhattan_substations = {
            'Hells Kitchen': {
                'lat': 40.765, 'lon': -73.993,
                'capacity_mva': 750,
                'coverage_area': 'West 42nd to 59th'
            },
            'Times Square': {
                'lat': 40.758, 'lon': -73.986,
                'capacity_mva': 850,
                'coverage_area': 'Times Square Area'
            },
            'Penn Station': {
                'lat': 40.751, 'lon': -73.994,
                'capacity_mva': 900,
                'coverage_area': 'West 34th to 42nd'
            },
            'Grand Central': {
                'lat': 40.753, 'lon': -73.977,
                'capacity_mva': 1000,
                'coverage_area': 'East 42nd to 50th'
            },
            'Murray Hill': {
                'lat': 40.748, 'lon': -73.976,
                'capacity_mva': 650,
                'coverage_area': 'East 34th to 42nd'
            },
            'Turtle Bay': {
                'lat': 40.755, 'lon': -73.968,
                'capacity_mva': 700,
                'coverage_area': 'East Side 45th to 55th'
            },
            'Columbus Circle': {
                'lat': 40.768, 'lon': -73.982,
                'capacity_mva': 600,
                'coverage_area': 'West 55th to 65th'
            },
            'Midtown East': {
                'lat': 40.760, 'lon': -73.969,
                'capacity_mva': 800,
                'coverage_area': 'East 50th to 59th'
            }
        }
        
        # Initialize substations
        for name, data in manhattan_substations.items():
            self.substations[name] = {
                **data,
                'voltage_primary': 138,
                'voltage_secondary': 13.8,
                'operational': True,
                'load_mw': 0,
                'transformers': []
            }
        
        # Create distribution transformers - DENSE GRID FOR FULL COVERAGE
        transformer_id = 0
        
        # Dense grid for complete coverage
        transformer_avenues = [
            -74.006, -74.000, -73.994, -73.988, -73.983,
            -73.978, -73.972, -73.966
        ]
        
        transformer_streets = [
            40.749, 40.752, 40.755, 40.758,
            40.761, 40.764, 40.767, 40.770
        ]
        
        for lon in transformer_avenues:
            for lat in transformer_streets:
                min_dist = float('inf')
                nearest_sub = None
                
                for sub_name, sub_data in self.substations.items():
                    dist = self._manhattan_distance(lat, lon, sub_data['lat'], sub_data['lon'])
                    if dist < min_dist:
                        min_dist = dist
                        nearest_sub = sub_name
                
                if nearest_sub and min_dist < 0.02:
                    transformer_name = f"DT_{transformer_id}"
                    
                    self.distribution_transformers[transformer_name] = DistributionTransformer(
                        id=transformer_name,
                        name=f"Transformer {transformer_id}",
                        lat=lat,
                        lon=lon,
                        substation=nearest_sub,
                        capacity_kva=500,
                        traffic_lights=[]
                    )
                    
                    self.substations[nearest_sub]['transformers'].append(transformer_name)
                    transformer_id += 1
        
        print(f"Created {len(self.distribution_transformers)} distribution transformers")
    
    def _connect_lights_to_power(self):
        """Connect traffic lights to power distribution network"""
        
        if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
            # Connect realistic traffic lights
            for tl_id, tl in self.traffic_controller.traffic_lights.items():
                min_dist = float('inf')
                nearest_dt = None
                
                for dt_name, dt in self.distribution_transformers.items():
                    dist = self._manhattan_distance(tl.lat, tl.lon, dt.lat, dt.lon)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_dt = dt_name
                
                if nearest_dt and min_dist < 0.01:
                    tl.transformer = nearest_dt
                    tl.substation = self.distribution_transformers[nearest_dt].substation
                    
                    self.distribution_transformers[nearest_dt].traffic_lights.append(tl_id)
                    self.distribution_transformers[nearest_dt].load_kw += tl.power_kw
                    self.substations[tl.substation]['load_mw'] += tl.power_kw / 1000
        else:
            # Connect simple traffic lights
            for tl_id, tl in self.traffic_lights.items():
                min_dist = float('inf')
                nearest_dt = None
                
                for dt_name, dt in self.distribution_transformers.items():
                    dist = self._manhattan_distance(tl['lat'], tl['lon'], dt.lat, dt.lon)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_dt = dt_name
                
                if nearest_dt and min_dist < 0.01:
                    tl['transformer'] = nearest_dt
                    tl['substation'] = self.distribution_transformers[nearest_dt].substation
                    
                    self.distribution_transformers[nearest_dt].traffic_lights.append(tl_id)
                    self.distribution_transformers[nearest_dt].load_kw += 0.3
                    self.substations[tl['substation']]['load_mw'] += 0.3 / 1000
    
    def _create_all_cable_routes(self):
        """Create ALL cable routes - KEEP YOUR FULL CABLE NETWORK"""
        
        # Primary cables (13.8kV from substation to transformers)
        for sub_name, sub_data in self.substations.items():
            for dt_name in sub_data['transformers']:
                if dt_name in self.distribution_transformers:
                    dt = self.distribution_transformers[dt_name]
                    
                    cable_path = self._smart_manhattan_routing(
                        sub_data['lat'], sub_data['lon'],
                        dt.lat, dt.lon
                    )
                    
                    self.primary_cables.append({
                        'id': f"primary_{sub_name}_{dt_name}",
                        'type': 'primary',
                        'voltage': '13.8kV',
                        'from': sub_name,
                        'to': dt_name,
                        'path': cable_path,
                        'operational': sub_data['operational'] and dt.operational
                    })
        
        # Secondary cables (480V from transformers to traffic lights)
        # Create ALL secondary cables but limit display for performance
        for dt_name, dt in self.distribution_transformers.items():
            for tl_id in dt.traffic_lights:
                if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
                    if tl_id in self.traffic_controller.traffic_lights:
                        tl = self.traffic_controller.traffic_lights[tl_id]
                        cable_path = self._smart_manhattan_routing(
                            dt.lat, dt.lon,
                            tl.lat, tl.lon,
                            is_service_drop=True
                        )
                else:
                    if tl_id in self.traffic_lights:
                        tl = self.traffic_lights[tl_id]
                        cable_path = self._smart_manhattan_routing(
                            dt.lat, dt.lon,
                            tl['lat'], tl['lon'],
                            is_service_drop=True
                        )
                
                self.secondary_cables.append({
                    'id': f"service_{dt_name}_{tl_id}",
                    'type': 'service',
                    'voltage': '480V',
                    'from': dt_name,
                    'to': tl_id,
                    'path': cable_path,
                    'operational': dt.operational
                })
        
        print(f"Created {len(self.primary_cables)} primary cables")
        print(f"Created {len(self.secondary_cables)} secondary cables")
    
    def _smart_manhattan_routing(self, lat1: float, lon1: float, lat2: float, lon2: float, 
                                  is_service_drop: bool = False) -> List[List[float]]:
        """Cable routing that follows Manhattan grid and stays within bounds"""
        
        # Conservative bounds - stay away from water
        safe_min_lat = self.manhattan_bounds['min_lat'] + 0.001
        safe_max_lat = self.manhattan_bounds['max_lat'] - 0.001
        safe_min_lon = self.manhattan_bounds['min_lon'] + 0.001
        safe_max_lon = self.manhattan_bounds['max_lon'] - 0.001
        
        # Enforce safe bounds
        lat1 = np.clip(lat1, safe_min_lat, safe_max_lat)
        lon1 = np.clip(lon1, safe_min_lon, safe_max_lon)
        lat2 = np.clip(lat2, safe_min_lat, safe_max_lat)
        lon2 = np.clip(lon2, safe_min_lon, safe_max_lon)
        
        path = []
        path.append([lon1, lat1])
        
        # Manhattan L-routing
        if abs(lon2 - lon1) > abs(lat2 - lat1):
            path.append([lon2, lat1])
            path.append([lon2, lat2])
        else:
            path.append([lon1, lat2])
            path.append([lon2, lat2])
        
        return path
    
    def _manhattan_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Manhattan distance"""
        return abs(lat1 - lat2) + abs(lon1 - lon2)
    
    def _add_ev_stations(self):
        """Add EV charging stations at realistic locations"""
        
        ev_locations = [
            {'name': 'Times Square Garage', 'lat': 40.758, 'lon': -73.985, 'chargers': 50},
            {'name': 'Penn Station Hub', 'lat': 40.750, 'lon': -73.993, 'chargers': 40},
            {'name': 'Grand Central Charging', 'lat': 40.752, 'lon': -73.977, 'chargers': 60},
            {'name': 'Bryant Park Station', 'lat': 40.754, 'lon': -73.984, 'chargers': 30},
            {'name': 'Columbus Circle EV', 'lat': 40.768, 'lon': -73.982, 'chargers': 35},
            {'name': 'Murray Hill Garage', 'lat': 40.748, 'lon': -73.978, 'chargers': 25},
            {'name': 'Turtle Bay Charging', 'lat': 40.755, 'lon': -73.969, 'chargers': 20},
            {'name': 'Midtown East Station', 'lat': 40.760, 'lon': -73.970, 'chargers': 30}
        ]
        
        for i, station in enumerate(ev_locations):
            min_dist = float('inf')
            nearest_sub = None
            
            for sub_name, sub_data in self.substations.items():
                dist = self._manhattan_distance(
                    station['lat'], station['lon'],
                    sub_data['lat'], sub_data['lon']
                )
                if dist < min_dist:
                    min_dist = dist
                    nearest_sub = sub_name
            
            self.ev_stations[f"EV_{i}"] = {
                'id': f"EV_{i}",
                'name': station['name'],
                'lat': station['lat'],
                'lon': station['lon'],
                'chargers': station['chargers'],
                'substation': nearest_sub,
                'power_kw': station['chargers'] * 7.2,
                'operational': True,
                'vehicles_charging': 0
            }
            
            if nearest_sub:
                self.substations[nearest_sub]['load_mw'] += (station['chargers'] * 7.2) / 1000
        
        print(f"Added {len(self.ev_stations)} EV charging stations")
    
    def _integrate_with_pypsa(self):
        """Integrate with PyPSA power grid"""
        
        for sub_name, sub_data in self.substations.items():
            bus_name = f"{sub_name}_13.8kV"
            
            if bus_name in self.power_grid.network.buses.index:
                # Create time-varying load profile
                load_profile = self._create_load_profile(sub_data['load_mw'])
                
                self.power_grid.network.add(
                    "Load",
                    f"Distribution_{sub_name}",
                    bus=bus_name,
                    p_set=load_profile
                )
                
                print(f"Added {sub_data['load_mw']:.2f} MW load to {sub_name}")
    
    def _create_load_profile(self, base_load_mw: float) -> pd.Series:
        """Create realistic load profile based on time of day"""
        
        hours = self.power_grid.network.snapshots.hour if hasattr(
            self.power_grid.network.snapshots, 'hour'
        ) else range(24)
        
        load_profile = pd.Series(index=self.power_grid.network.snapshots, dtype=float)
        
        for i, h in enumerate(hours):
            if 6 <= h < 10:  # Morning rush
                factor = 1.2
            elif 15 <= h < 20:  # Evening rush
                factor = 1.3
            elif 23 <= h or h < 6:  # Late night
                factor = 0.7
            else:
                factor = 1.0
            
            load_profile.iloc[i] = base_load_mw * factor
        
        return load_profile
    
    def set_simulation_speed(self, speed: float):
        """Set simulation speed"""
        self.simulation_speed = max(0.1, min(100.0, speed))
    
    def handle_rush_hour(self):
        """Optimize traffic flow for rush hour"""
        
        if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
            self.traffic_controller.optimize_zone("7th_avenue")
            self.traffic_controller.optimize_zone("6th_avenue")
            self.traffic_controller.optimize_zone("42nd_street")
    
    def simulate_substation_failure(self, substation_name: str) -> Dict[str, Any]:
        """Simulate substation failure with cascading effects"""
        
        if substation_name not in self.substations:
            return {'error': f'Substation {substation_name} not found'}
        
        self.substations[substation_name]['operational'] = False
        
        affected = {
            'transformers': 0,
            'traffic_lights': 0,
            'ev_stations': 0,
            'primary_cables': 0,
            'secondary_cables': 0
        }
        
        # Fail distribution transformers
        for dt_name in self.substations[substation_name]['transformers']:
            if dt_name in self.distribution_transformers:
                self.distribution_transformers[dt_name].operational = False
                affected['transformers'] += 1
                
                # Update traffic lights
                for tl_id in self.distribution_transformers[dt_name].traffic_lights:
                    if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
                        if tl_id in self.traffic_controller.traffic_lights:
                            tl = self.traffic_controller.traffic_lights[tl_id]
                            tl.powered = False
                            affected['traffic_lights'] += 1
                    else:
                        if tl_id in self.traffic_lights:
                            self.traffic_lights[tl_id]['powered'] = False
                            self.traffic_lights[tl_id]['color'] = '#000000'
                            self.traffic_lights[tl_id]['phase'] = 'off'
                            affected['traffic_lights'] += 1
        
        # Fail EV stations
        for ev_id, ev in self.ev_stations.items():
            if ev['substation'] == substation_name:
                ev['operational'] = False
                ev['vehicles_charging'] = 0
                affected['ev_stations'] += 1
        
        # Update cable status
        for cable in self.primary_cables:
            if cable['from'] == substation_name:
                cable['operational'] = False
                affected['primary_cables'] += 1
        
        for cable in self.secondary_cables:
            for dt_name in self.substations[substation_name]['transformers']:
                if cable['from'] == dt_name:
                    cable['operational'] = False
                    affected['secondary_cables'] += 1
        
        return {
            'substation': substation_name,
            'capacity_lost_mva': self.substations[substation_name]['capacity_mva'],
            'load_lost_mw': self.substations[substation_name]['load_mw'],
            'transformers_affected': affected['transformers'],
            'traffic_lights_affected': affected['traffic_lights'],
            'ev_stations_affected': affected['ev_stations'],
            'primary_cables_affected': affected['primary_cables'],
            'secondary_cables_affected': affected['secondary_cables'],
            'estimated_customers': int(self.substations[substation_name]['load_mw'] * 1000),
            'affected_area': self.substations[substation_name]['coverage_area']
        }
    
    def restore_substation(self, substation_name: str) -> bool:
        """Restore failed substation"""
        
        if substation_name not in self.substations:
            return False
        
        self.substations[substation_name]['operational'] = True
        
        # Restore transformers
        for dt_name in self.substations[substation_name]['transformers']:
            if dt_name in self.distribution_transformers:
                self.distribution_transformers[dt_name].operational = True
                
                # Restore traffic lights
                for tl_id in self.distribution_transformers[dt_name].traffic_lights:
                    if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
                        if tl_id in self.traffic_controller.traffic_lights:
                            tl = self.traffic_controller.traffic_lights[tl_id]
                            tl.powered = True
                    else:
                        if tl_id in self.traffic_lights:
                            self.traffic_lights[tl_id]['powered'] = True
        
        # Restore EV stations
        for ev in self.ev_stations.values():
            if ev['substation'] == substation_name:
                ev['operational'] = True
        
        # Restore cables
        for cable in self.primary_cables:
            if cable['from'] == substation_name:
                cable['operational'] = True
        
        for cable in self.secondary_cables:
            for dt_name in self.substations[substation_name]['transformers']:
                if cable['from'] == dt_name:
                    cable['operational'] = True
        
        return True
    
    def get_network_state(self) -> Dict[str, Any]:
        """Get complete network state for visualization"""
        
        # Get traffic light states
        if TRAFFIC_CONTROL_AVAILABLE and self.traffic_controller:
            traffic_lights_data = self.traffic_controller.export_for_visualization()
            traffic_stats = self.traffic_controller.get_system_stats()
        else:
            # Simple traffic lights
            traffic_lights_data = []
            for tl in self.traffic_lights.values():
                traffic_lights_data.append({
                    'id': tl['id'],
                    'lat': tl['lat'],
                    'lon': tl['lon'],
                    'powered': tl['powered'],
                    'color': tl['color'],
                    'phase': tl['phase'],
                    'intersection': tl.get('intersection', 'Unknown')
                })
            
            traffic_stats = {
                'total_lights': len(self.traffic_lights),
                'powered_lights': sum(1 for tl in self.traffic_lights.values() if tl['powered'])
            }
        
        # Add vehicle data if available
        vehicle_data = []
        charging_data = []
        vehicle_stats = {}
        
        if self.vehicles_enabled and self.sumo_runner:
            vehicle_data = self.sumo_runner.get_vehicle_data_for_map()
            charging_data = self.sumo_runner.get_charging_status()
            vehicle_stats = self.sumo_runner.stats
        
        # Calculate statistics
        stats = {
            'total_substations': len(self.substations),
            'operational_substations': sum(1 for s in self.substations.values() if s['operational']),
            'total_transformers': len(self.distribution_transformers),
            'total_traffic_lights': len(traffic_lights_data),
            'powered_traffic_lights': sum(1 for tl in traffic_lights_data if tl['powered']),
            'total_ev_stations': len(self.ev_stations),
            'operational_ev_stations': sum(1 for ev in self.ev_stations.values() if ev['operational']),
            'total_load_mw': sum(s['load_mw'] for s in self.substations.values()),
            'total_primary_cables': len(self.primary_cables),
            'total_secondary_cables': len(self.secondary_cables),
            'operational_primary_cables': sum(1 for c in self.primary_cables if c['operational']),
            'operational_secondary_cables': sum(1 for c in self.secondary_cables if c['operational']),
            'system_time': self.system_time.strftime('%H:%M:%S'),
            'simulation_speed': self.simulation_speed
        }
        
        # Add traffic-specific stats
        if TRAFFIC_CONTROL_AVAILABLE:
            stats.update({
                'green_ns': traffic_stats.get('green_ns', 0),
                'green_ew': traffic_stats.get('green_ew', 0),
                'yellow_lights': traffic_stats.get('yellow', 0),
                'red_lights': traffic_stats.get('red', 0),
                'time_of_day': traffic_stats.get('time_of_day', 'unknown')
            })
        else:
            # Simple stats
            green = sum(1 for tl in traffic_lights_data if tl.get('color') == '#00ff00')
            yellow = sum(1 for tl in traffic_lights_data if tl.get('color') == '#ffff00')
            red = sum(1 for tl in traffic_lights_data if tl.get('color') == '#ff0000')
            black = sum(1 for tl in traffic_lights_data if tl.get('color') == '#000000')
            
            stats.update({
                'green_lights': green,
                'yellow_lights': yellow,
                'red_lights': red,
                'black_lights': black
            })
        
        # Add vehicle stats
        stats.update(vehicle_stats)
        
        return {
            'substations': [
                {
                    'name': name,
                    'lat': data['lat'],
                    'lon': data['lon'],
                    'capacity_mva': data['capacity_mva'],
                    'load_mw': data['load_mw'],
                    'operational': data['operational'],
                    'coverage_area': data['coverage_area']
                }
                for name, data in self.substations.items()
            ],
            'traffic_lights': traffic_lights_data,
            'ev_stations': list(self.ev_stations.values()),
            'cables': {
                'primary': self.primary_cables,
                'secondary': self.secondary_cables
            },
            'vehicles': vehicle_data,
            'charging_stations_usage': charging_data,
            'statistics': stats
        }
    
    def shutdown(self):
        """Shutdown simulation"""
        self.simulation_running = False
        
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=2)
        
        if self.vehicles_enabled and self.sumo_runner:
            self.sumo_runner.stop()
        
        print("System shutdown complete")

# For backward compatibility
ManhattanIntegratedSystem = ManhattanIntegratedSystemV2