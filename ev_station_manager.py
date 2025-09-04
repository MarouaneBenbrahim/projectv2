"""
World-Class EV Charging Station Manager
"""

import heapq
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

@dataclass
class ChargingRequest:
    """Charging request with priority"""
    vehicle_id: str
    battery_soc: float
    arrival_time: datetime
    priority: int = 0  # 0=normal, 1=low battery, 2=emergency
    
    def __lt__(self, other):
        # Higher priority or lower battery gets precedence
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.battery_soc < other.battery_soc

@dataclass
class ChargingPort:
    """Individual charging port at a station"""
    port_id: str
    power_kw: float
    occupied_by: Optional[str] = None
    charging_start: Optional[datetime] = None
    expected_finish: Optional[datetime] = None

class EVStationManager:
    """Manages all EV charging stations with intelligent routing"""
    
    def __init__(self, integrated_system, sumo_net):
        self.integrated_system = integrated_system
        self.sumo_net = sumo_net
        self.stations = {}
        self.charging_queues = {}  # Priority queues per station
        self.vehicle_reservations = {}  # vehicle_id -> station_id
        
        self._initialize_stations()
    
    def _initialize_stations(self):
        """Initialize stations on valid SUMO edges using actual station names"""
        
        for ev_id, ev_station in self.integrated_system.ev_stations.items():
            # Find nearest valid edge
            edge = self._find_nearest_valid_edge(
                ev_station['lat'], 
                ev_station['lon']
            )
            
            if edge:
                # Create charging ports based on actual station capacity
                ports = []
                num_fast = min(2, ev_station['chargers'] // 4)  # 25% fast chargers max
                
                # Create 20 ports maximum per station
                num_ports = min(20, ev_station['chargers'])
                
                for i in range(num_ports):
                    # Mix of DC fast and Level 2
                    if i < num_fast:
                        power = 150  # DC fast charging
                    else:
                        power = 22   # Level 2
                    
                    ports.append(ChargingPort(
                        port_id=f"{ev_id}_port_{i}",
                        power_kw=power
                    ))
                
                self.stations[ev_id] = {
                    'id': ev_id,
                    'name': ev_station['name'],
                    'edge': edge,
                    'lat': ev_station['lat'],
                    'lon': ev_station['lon'],
                    'ports': ports,
                    'queue': [],
                    'operational': ev_station['operational'],  # Get from integrated system
                    'substation': ev_station['substation'],
                    'total_power_kw': sum(p.power_kw for p in ports),
                    'current_load_kw': 0
                }
                
                self.charging_queues[ev_id] = []
                
                print(f"✅ Initialized {ev_station['name']} on edge {edge} with {len(ports)} ports (Max 20 charging, 20 queue)")
    def _find_nearest_valid_edge(self, lat, lon):
        """Find nearest edge that can be routed to"""
        
        try:
            x, y = self.sumo_net.convertLonLat2XY(lon, lat)
            
            # Get edges that allow passenger vehicles
            valid_edges = [
                e for e in self.sumo_net.getEdges() 
                if e.allows("passenger") and not e.isSpecial()
            ]
            
            nearest_edge = None
            min_dist = float('inf')
            
            for edge in valid_edges:
                # Get edge center
                shape = edge.getShape()
                if shape:
                    edge_x = sum(p[0] for p in shape) / len(shape)
                    edge_y = sum(p[1] for p in shape) / len(shape)
                    
                    dist = np.sqrt((x - edge_x)**2 + (y - edge_y)**2)
                    
                    if dist < min_dist:
                        min_dist = dist
                        nearest_edge = edge.getID()
            
            return nearest_edge
            
        except Exception as e:
            print(f"Error finding edge: {e}")
            return None
    
    def request_charging(self, vehicle_id, current_soc, current_edge, 
                        current_position, is_emergency=False):
        """
        Smart charging station selection
        
        Returns:
            (station_id, edge_id, estimated_wait_minutes, distance_km)
        """
        
        print(f"\n🔍 Finding charging station for {vehicle_id} (SOC: {current_soc:.1%})")
        
        best_option = None
        min_total_time = float('inf')
        stations_checked = []
        
        for station_id, station in self.stations.items():
            # First check if station has power from integrated system
            ev_station = self.integrated_system.ev_stations.get(station_id)
            if not ev_station or not ev_station['operational']:
                stations_checked.append(f"{station['name']} (NO POWER)")
                continue
            
            # Double check substation
            substation = self.integrated_system.substations.get(station['substation'])
            if not substation or not substation['operational']:
                stations_checked.append(f"{station['name']} (Substation DOWN)")
                continue
            
            # CHECK CAPACITY - MAX 20 CHARGING, 20 IN QUEUE
            current_charging = len([p for p in station['ports'] if p.occupied_by is not None])
            current_queue = len(station.get('queue', []))
            
            # Skip if station is completely full
            if current_charging >= 20 and current_queue >= 20:
                stations_checked.append(f"{station['name']} (FULL: {current_charging}/20 charging, {current_queue}/20 queue)")
                continue
            
            # Calculate travel distance
            try:
                # Simple distance for now
                if not current_edge or current_edge.startswith(':'):
                    continue
                    
                distance = 1.0  # Simplified - 1km default
                travel_time_min = 2  # 2 minutes to get there
                
                # Calculate wait time
                if current_charging < 20:
                    wait_time_min = 0
                    stations_checked.append(f"{station['name']} (AVAILABLE: {current_charging}/20 charging)")
                else:
                    position_in_queue = current_queue + 1
                    wait_time_min = (position_in_queue * 5) / 10  # Estimate
                    stations_checked.append(f"{station['name']} (QUEUE: {current_queue}/20)")
                
                # Total time
                total_time = travel_time_min + wait_time_min + 5  # 5 min charge time
                
                if total_time < min_total_time:
                    min_total_time = total_time
                    best_option = (
                        station_id,
                        station['edge'],
                        wait_time_min,
                        distance
                    )
                    
            except Exception as e:
                stations_checked.append(f"{station['name']} (ERROR: {e})")
                continue
        
        print(f"   Checked stations: {', '.join(stations_checked)}")
        
        if best_option:
            station_id = best_option[0]
            station = self.stations[station_id]
            
            # Add to queue/reservation
            if station_id not in self.charging_queues:
                self.charging_queues[station_id] = []
                
            request = ChargingRequest(
                vehicle_id=vehicle_id,
                battery_soc=current_soc,
                arrival_time=datetime.now(),
                priority=2 if is_emergency else (1 if current_soc < 0.2 else 0)
            )
            
            heapq.heappush(self.charging_queues[station_id], request)
            self.vehicle_reservations[vehicle_id] = station_id
            
            print(f"   ✅ {vehicle_id} → {station['name']} (Wait: {best_option[2]:.0f} min)")
        else:
            print(f"   ❌ {vehicle_id} NO AVAILABLE STATIONS!")
        
        return best_option
    
    def _calculate_route_distance(self, route):
        """Calculate route distance in km"""
        
        total_distance = 0
        for edge_id in route:
            try:
                edge = self.sumo_net.getEdge(edge_id)
                total_distance += edge.getLength()
            except:
                total_distance += 100  # Default 100m per edge
        
        return total_distance / 1000  # Convert to km
    
    def _check_power_available(self, station):
        """Check if station's substation is operational"""
        
        substation_name = station['substation']
        
        # Check in the integrated system's substations
        if substation_name in self.integrated_system.substations:
            is_operational = self.integrated_system.substations[substation_name]['operational']
            if not is_operational:
                print(f"      {substation_name} substation is DOWN")
            return is_operational
        
        # If substation not found, assume it's operational
        print(f"      Warning: Substation {substation_name} not found, assuming operational")
        return True
    def handle_blackout(self, substation_name):
        """Handle substation blackout - mark stations as offline"""
        
        affected_stations = []
        for station_id, station in self.stations.items():
            if station['substation'] == substation_name:
                station['operational'] = False
                affected_stations.append(station['name'])
                
                # Update in integrated system too
                if station_id in self.integrated_system.ev_stations:
                    self.integrated_system.ev_stations[station_id]['operational'] = False
                
                # Clear any charging vehicles
                for port in station['ports']:
                    if port.occupied_by:
                        # Force stop charging
                        self.finish_charging(port.occupied_by)
                
                # Clear queue
                if 'queue' in station:
                    station['queue'].clear()
        
        if affected_stations:
            print(f"⚡ BLACKOUT: {', '.join(affected_stations)} offline!")
        
        return affected_stations

    def restore_power(self, substation_name):
        """Restore power to stations"""
        
        restored_stations = []
        for station_id, station in self.stations.items():
            if station['substation'] == substation_name:
                station['operational'] = True
                restored_stations.append(station['name'])
                
                # Update in integrated system too
                if station_id in self.integrated_system.ev_stations:
                    self.integrated_system.ev_stations[station_id]['operational'] = True
        
        if restored_stations:
            print(f"✅ POWER RESTORED: {', '.join(restored_stations)} back online!")
        
        return restored_stations
    
    def restore_power(self, substation_name):
        """Restore power to stations"""
        
        restored_stations = []
        for station_id, station in self.stations.items():
            if station['substation'] == substation_name:
                station['operational'] = True
                restored_stations.append(station['name'])
        
        if restored_stations:
            print(f"✅ POWER RESTORED: {', '.join(restored_stations)} back online!")
        
        return restored_stations        
    
    def start_charging(self, vehicle_id, station_id):
        """Start charging a vehicle"""
        
        if station_id not in self.stations:
            return False
        
        station = self.stations[station_id]
        
        # Find available port
        for port in station['ports']:
            if port.occupied_by is None:
                port.occupied_by = vehicle_id
                port.charging_start = datetime.now()
                
                # Estimate finish time (simplified)
                port.expected_finish = port.charging_start + timedelta(minutes=20)
                
                # Update power load
                station['current_load_kw'] += port.power_kw
                
                return True
        
        return False
    
    def update_charging(self, vehicle_id, current_soc):
            """Update charging progress - FASTER for simulation"""
            
            for station in self.stations.values():
                for port in station['ports']:
                    if port.occupied_by == vehicle_id:
                        # Calculate charge delivered
                        if port.charging_start:
                            # SIMULATION SPEED: Much faster charging
                            # DC Fast: 150kW = ~2% per step at simulation speed
                            # Level 2: 22kW = ~0.5% per step at simulation speed
                            
                            if current_soc < 0.5:
                                # Fast charging below 50%
                                if port.power_kw >= 150:
                                    energy_kwh = 1.5  # Super fast for simulation
                                else:
                                    energy_kwh = 0.4
                            elif current_soc < 0.8:
                                # Medium speed 50-80%
                                if port.power_kw >= 150:
                                    energy_kwh = 0.8
                                else:
                                    energy_kwh = 0.3
                            else:
                                # Slow above 80%
                                energy_kwh = 0.2
                            
                            return energy_kwh
            
            return 0
    
    def finish_charging(self, vehicle_id):
        """Finish charging and free up port"""
        
        for station in self.stations.values():
            for port in station['ports']:
                if port.occupied_by == vehicle_id:
                    # Free the port
                    station['current_load_kw'] -= port.power_kw
                    port.occupied_by = None
                    port.charging_start = None
                    port.expected_finish = None
                    
                    # Process queue
                    if station['queue']:
                        next_vehicle = station['queue'].pop(0)
                        self.start_charging(next_vehicle, station['id'])
                    
                    return True
        
        return False
    
    def get_station_status(self, station_id):
        """Get detailed station status"""
        
        if station_id not in self.stations:
            return None
        
        station = self.stations[station_id]
        
        return {
            'operational': station['operational'],
            'total_ports': len(station['ports']),
            'available_ports': sum(1 for p in station['ports'] if p.occupied_by is None),
            'queue_length': len(station['queue']),
            'current_load_kw': station['current_load_kw'],
            'max_load_kw': station['total_power_kw'],
            'charging_vehicles': [p.occupied_by for p in station['ports'] if p.occupied_by]
        }