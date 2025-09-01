"""
Manhattan Traffic Light Control System
Professional NYC DOT-style traffic management with realistic phases and coordination
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import math

class TrafficPhase(Enum):
    """NYC traffic light phases"""
    # Main phases
    NS_GREEN = "north_south_green"
    NS_YELLOW = "north_south_yellow"
    NS_RED = "north_south_red"
    EW_GREEN = "east_west_green"
    EW_YELLOW = "east_west_yellow"
    EW_RED = "east_west_red"
    ALL_RED = "all_red"  # Safety clearance
    
    # Special phases
    PEDESTRIAN = "pedestrian_only"
    FLASHING_YELLOW = "flashing_yellow"  # Late night
    FLASHING_RED = "flashing_red"  # Power failure
    OFF = "off"  # No power

class TimeOfDay(Enum):
    """NYC traffic patterns by time"""
    MORNING_RUSH = "morning_rush"      # 6:00-10:00
    MIDDAY = "midday"                  # 10:00-15:00
    EVENING_RUSH = "evening_rush"      # 15:00-20:00
    EVENING = "evening"                # 20:00-23:00
    LATE_NIGHT = "late_night"          # 23:00-6:00

@dataclass
class TrafficTiming:
    """Traffic light cycle timing parameters"""
    green_ns: int = 40  # Seconds for N-S green
    yellow_ns: int = 3
    green_ew: int = 35  # Seconds for E-W green
    yellow_ew: int = 3
    all_red: int = 2    # Clearance time
    pedestrian: int = 7  # Walk signal time
    
    @property
    def cycle_length(self) -> int:
        """Total cycle length in seconds"""
        return (self.green_ns + self.yellow_ns + self.all_red +
                self.green_ew + self.yellow_ew + self.all_red)

@dataclass
class TrafficLight:
    """Individual traffic light with state management"""
    id: str
    lat: float
    lon: float
    intersection: str
    avenue: str = ""  # e.g., "7th Ave"
    street: int = 0   # e.g., 42 for 42nd Street
    
    # Power and control
    powered: bool = True
    substation: str = ""
    transformer: str = ""
    power_kw: float = 0.3
    battery_backup: bool = False
    
    # Traffic state
    current_phase: TrafficPhase = TrafficPhase.NS_RED
    phase_timer: int = 0  # Seconds in current phase
    next_phase: Optional[TrafficPhase] = None
    
    # Timing configuration
    timing: TrafficTiming = field(default_factory=TrafficTiming)
    offset: int = 0  # Offset for coordination (seconds)
    
    # Coordination
    zone: str = ""  # Coordination zone
    priority: str = "normal"  # normal, arterial, emergency
    
    def get_color(self) -> str:
        """Get current display color based on phase"""
        if not self.powered:
            return "#000000"  # Black - no power
        
        color_map = {
            TrafficPhase.NS_GREEN: "#00ff00",
            TrafficPhase.EW_GREEN: "#00ff00",
            TrafficPhase.NS_YELLOW: "#ffff00",
            TrafficPhase.EW_YELLOW: "#ffff00",
            TrafficPhase.NS_RED: "#ff0000",
            TrafficPhase.EW_RED: "#ff0000",
            TrafficPhase.ALL_RED: "#ff0000",
            TrafficPhase.PEDESTRIAN: "#ff8800",  # Orange for pedestrian
            TrafficPhase.FLASHING_YELLOW: "#ffff00",
            TrafficPhase.FLASHING_RED: "#ff0000",
            TrafficPhase.OFF: "#000000"
        }
        return color_map.get(self.current_phase, "#ff0000")
    
    def get_ns_state(self) -> str:
        """Get North-South direction state"""
        if self.current_phase in [TrafficPhase.NS_GREEN]:
            return "green"
        elif self.current_phase in [TrafficPhase.NS_YELLOW]:
            return "yellow"
        else:
            return "red"
    
    def get_ew_state(self) -> str:
        """Get East-West direction state"""
        if self.current_phase in [TrafficPhase.EW_GREEN]:
            return "green"
        elif self.current_phase in [TrafficPhase.EW_YELLOW]:
            return "yellow"
        else:
            return "red"

class ManhattanTrafficController:
    """
    Professional traffic control system for Manhattan
    Implements NYC DOT traffic management strategies
    """
    
    def __init__(self):
        self.traffic_lights: Dict[str, TrafficLight] = {}
        self.coordination_zones: Dict[str, List[str]] = {}
        self.current_time = datetime.now()
        self.time_of_day = self._get_time_of_day()
        
        # Manhattan traffic patterns
        self.avenue_priority = True  # Avenues get more green time
        self.progressive_timing = True  # Green wave coordination
        
        # Zone definitions for coordination
        self._define_coordination_zones()
        
    def _get_time_of_day(self) -> TimeOfDay:
        """Determine current traffic pattern period"""
        hour = self.current_time.hour
        
        if 6 <= hour < 10:
            return TimeOfDay.MORNING_RUSH
        elif 10 <= hour < 15:
            return TimeOfDay.MIDDAY
        elif 15 <= hour < 20:
            return TimeOfDay.EVENING_RUSH
        elif 20 <= hour < 23:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.LATE_NIGHT
    
    def _define_coordination_zones(self):
        """Define traffic coordination zones for Manhattan"""
        
        # Major avenue corridors (green waves)
        self.coordination_zones = {
            "7th_avenue": [],    # Times Square corridor
            "6th_avenue": [],    # Avenue of the Americas
            "5th_avenue": [],    # Shopping/Museum corridor
            "park_avenue": [],   # Business corridor
            "lexington": [],     # East side arterial
            "broadway": [],      # Diagonal arterial
            
            # Major crosstown streets
            "42nd_street": [],   # Major crosstown
            "34th_street": [],   # Penn Station/Herald Square
            "57th_street": [],   # Crosstown arterial
            "14th_street": [],   # Downtown crosstown
            
            # Special zones
            "times_square": [],  # Special timing for Times Square
            "grand_central": [], # Grand Central area
            "penn_station": []   # Penn Station area
        }
    
    def initialize_traffic_lights(self, lights_data: List[Dict]):
        """Initialize traffic lights with proper configuration"""
        
        for light_data in lights_data:
            # Parse intersection info
            intersection = light_data.get('intersection', '')
            avenue, street = self._parse_intersection(intersection)
            
            # Create traffic light
            tl = TrafficLight(
                id=str(light_data['id']),
                lat=light_data['lat'],
                lon=light_data['lon'],
                intersection=intersection,
                avenue=avenue,
                street=street,
                powered=True,
                battery_backup=(street % 5 == 0)  # Major intersections
            )
            
            # Set timing based on location and type
            tl.timing = self._get_timing_for_intersection(avenue, street)
            
            # Set coordination offset for progressive timing
            tl.offset = self._calculate_offset(avenue, street)
            
            # Assign to zone
            tl.zone = self._assign_zone(avenue, street)
            if tl.zone and tl.zone in self.coordination_zones:
                self.coordination_zones[tl.zone].append(tl.id)
            
            # Set initial phase based on coordination
            tl.current_phase = self._get_initial_phase(avenue, street)
            
            self.traffic_lights[tl.id] = tl
    
    def _parse_intersection(self, intersection: str) -> Tuple[str, int]:
        """Parse intersection string to get avenue and street"""
        # Example: "7th Ave & 42th St" -> ("7th Ave", 42)
        
        avenue = ""
        street = 0
        
        if '&' in intersection:
            parts = intersection.split('&')
            if len(parts) == 2:
                avenue = parts[0].strip()
                street_part = parts[1].strip()
                
                # Extract street number
                try:
                    street = int(''.join(filter(str.isdigit, street_part)))
                except:
                    street = 0
        
        return avenue, street
    
    def _get_timing_for_intersection(self, avenue: str, street: int) -> TrafficTiming:
        """Get appropriate timing based on intersection type"""
        
        timing = TrafficTiming()
        
        # Adjust based on time of day
        if self.time_of_day == TimeOfDay.MORNING_RUSH:
            # Favor north-bound (uptown) in morning
            timing.green_ns = 50
            timing.green_ew = 30
            
        elif self.time_of_day == TimeOfDay.EVENING_RUSH:
            # Favor south-bound (downtown) in evening
            timing.green_ns = 50
            timing.green_ew = 30
            
        elif self.time_of_day == TimeOfDay.LATE_NIGHT:
            # Shorter cycles at night
            timing.green_ns = 25
            timing.green_ew = 20
            
        else:
            # Standard midday timing
            timing.green_ns = 40
            timing.green_ew = 35
        
        # Major intersections get longer cycles
        major_streets = [34, 42, 57, 14, 23, 59]
        if street in major_streets:
            timing.green_ew += 10  # More time for crosstown traffic
        
        # Major avenues get priority
        major_avenues = ["5th Ave", "6th Ave", "7th Ave", "Park Ave", "Lexington"]
        if any(ave in avenue for ave in major_avenues):
            timing.green_ns += 10  # More time for avenue traffic
        
        return timing
    
    def _calculate_offset(self, avenue: str, street: int) -> int:
        """Calculate offset for progressive timing (green wave)"""
        
        # Progressive timing on avenues
        # Lights are offset to create green wave at 25 mph (NYC speed limit)
        
        offset = 0
        
        # Base street for calculation (42nd Street as reference)
        base_street = 42
        street_diff = street - base_street
        
        # Each block is ~260 feet, at 25 mph = 37 ft/sec
        # Time between blocks = 260/37 = ~7 seconds
        seconds_per_block = 7
        
        # Major avenues get progressive timing
        if "Ave" in avenue or "Avenue" in avenue:
            offset = street_diff * seconds_per_block
            
            # Wrap around to stay within cycle
            cycle_length = 90  # Typical cycle
            offset = offset % cycle_length
        
        # Broadway is diagonal - special calculation
        if "Broadway" in avenue:
            offset = int(street_diff * seconds_per_block * 0.7)  # Adjusted for angle
        
        return max(0, offset)
    
    def _assign_zone(self, avenue: str, street: int) -> str:
        """Assign traffic light to coordination zone"""
        
        # Special zones
        if 40 <= street <= 44 and "7th" in avenue:
            return "times_square"
        elif 40 <= street <= 44 and ("Park" in avenue or "Lexington" in avenue):
            return "grand_central"
        elif 32 <= street <= 36 and ("7th" in avenue or "8th" in avenue):
            return "penn_station"
        
        # Avenue zones
        avenue_map = {
            "7th Ave": "7th_avenue",
            "6th Ave": "6th_avenue",
            "5th Ave": "5th_avenue",
            "Park Ave": "park_avenue",
            "Lexington": "lexington",
            "Broadway": "broadway"
        }
        
        for ave_name, zone_name in avenue_map.items():
            if ave_name in avenue:
                return zone_name
        
        # Street zones
        if street == 42:
            return "42nd_street"
        elif street == 34:
            return "34th_street"
        elif street == 57:
            return "57th_street"
        elif street == 14:
            return "14th_street"
        
        return "general"
    
    def _get_initial_phase(self, avenue: str, street: int) -> TrafficPhase:
        """Set initial phase based on coordination strategy"""
        
        # Start with opposite phases for adjacent intersections
        # This prevents gridlock at startup
        
        if (street % 2 == 0):
            return TrafficPhase.NS_GREEN
        else:
            return TrafficPhase.EW_GREEN
    
    def update(self, current_time: datetime):
        """Update all traffic lights - main control loop"""
        
        self.current_time = current_time
        self.time_of_day = self._get_time_of_day()
        
        for tl in self.traffic_lights.values():
            if tl.powered:
                self._update_traffic_light(tl)
            else:
                # No power - flashing red or off
                if tl.battery_backup:
                    tl.current_phase = TrafficPhase.FLASHING_RED
                else:
                    tl.current_phase = TrafficPhase.OFF
    
    def _update_traffic_light(self, tl: TrafficLight):
        """Update individual traffic light phase"""
        
        # Late night mode - flashing yellow on avenues, red on streets
        if self.time_of_day == TimeOfDay.LATE_NIGHT and tl.street not in [34, 42, 57]:
            if "Ave" in tl.avenue:
                tl.current_phase = TrafficPhase.FLASHING_YELLOW
            else:
                tl.current_phase = TrafficPhase.FLASHING_RED
            return
        
        # Normal phase progression
        tl.phase_timer += 1
        
        # Get current phase duration
        phase_duration = self._get_phase_duration(tl)
        
        # Check if time to transition
        if tl.phase_timer >= phase_duration:
            self._transition_phase(tl)
            tl.phase_timer = 0
    
    def _get_phase_duration(self, tl: TrafficLight) -> int:
        """Get duration for current phase"""
        
        phase = tl.current_phase
        
        # Apply offset for coordination
        effective_timer = (tl.phase_timer + tl.offset) % tl.timing.cycle_length
        
        duration_map = {
            TrafficPhase.NS_GREEN: tl.timing.green_ns,
            TrafficPhase.NS_YELLOW: tl.timing.yellow_ns,
            TrafficPhase.EW_GREEN: tl.timing.green_ew,
            TrafficPhase.EW_YELLOW: tl.timing.yellow_ew,
            TrafficPhase.ALL_RED: tl.timing.all_red,
            TrafficPhase.PEDESTRIAN: tl.timing.pedestrian
        }
        
        return duration_map.get(phase, 30)
    
    def _transition_phase(self, tl: TrafficLight):
        """Transition to next phase in cycle"""
        
        transitions = {
            TrafficPhase.NS_GREEN: TrafficPhase.NS_YELLOW,
            TrafficPhase.NS_YELLOW: TrafficPhase.ALL_RED,
            TrafficPhase.ALL_RED: TrafficPhase.EW_GREEN if tl.current_phase == TrafficPhase.NS_YELLOW else TrafficPhase.NS_GREEN,
            TrafficPhase.EW_GREEN: TrafficPhase.EW_YELLOW,
            TrafficPhase.EW_YELLOW: TrafficPhase.ALL_RED,
            TrafficPhase.NS_RED: TrafficPhase.NS_GREEN,
            TrafficPhase.EW_RED: TrafficPhase.EW_GREEN
        }
        
        # Special handling for pedestrian phase
        if self._should_add_pedestrian_phase(tl):
            tl.current_phase = TrafficPhase.PEDESTRIAN
        else:
            tl.current_phase = transitions.get(tl.current_phase, TrafficPhase.ALL_RED)
    
    def _should_add_pedestrian_phase(self, tl: TrafficLight) -> bool:
        """Determine if pedestrian phase should be added"""
        
        # Major intersections get pedestrian phases
        major_streets = [34, 42, 57, 14, 23, 59]
        if tl.street in major_streets:
            # Every 3rd cycle during rush hours
            cycle_count = tl.phase_timer // tl.timing.cycle_length
            if cycle_count % 3 == 0 and self.time_of_day in [TimeOfDay.MORNING_RUSH, TimeOfDay.EVENING_RUSH]:
                return True
        
        return False
    
    def handle_emergency_vehicle(self, route: List[str]):
        """Handle emergency vehicle preemption"""
        
        # Set lights along route to green
        for light_id in route:
            if light_id in self.traffic_lights:
                tl = self.traffic_lights[light_id]
                # Determine which direction the emergency vehicle needs
                # For now, give north-south priority
                tl.current_phase = TrafficPhase.NS_GREEN
                tl.phase_timer = 0
                tl.priority = "emergency"
        
        # Set cross traffic to red
        # (In real system, this would be more sophisticated)
    
    def optimize_zone(self, zone_name: str):
        """Optimize timing for a specific zone based on current conditions"""
        
        if zone_name not in self.coordination_zones:
            return
        
        lights_in_zone = self.coordination_zones[zone_name]
        
        # Adjust timing based on congestion patterns
        # This would normally use real traffic data
        
        for light_id in lights_in_zone:
            tl = self.traffic_lights[light_id]
            
            # Example: Add more green time during rush hour
            if self.time_of_day in [TimeOfDay.MORNING_RUSH, TimeOfDay.EVENING_RUSH]:
                if "avenue" in zone_name:
                    # Favor avenue traffic
                    tl.timing.green_ns += 10
                    tl.timing.green_ew -= 5
                elif "street" in zone_name:
                    # Favor crosstown traffic
                    tl.timing.green_ew += 10
                    tl.timing.green_ns -= 5
    
    def get_system_stats(self) -> Dict:
        """Get current system statistics"""
        
        stats = {
            'total_lights': len(self.traffic_lights),
            'powered_lights': sum(1 for tl in self.traffic_lights.values() if tl.powered),
            'green_ns': sum(1 for tl in self.traffic_lights.values() 
                          if tl.current_phase in [TrafficPhase.NS_GREEN]),
            'green_ew': sum(1 for tl in self.traffic_lights.values() 
                          if tl.current_phase in [TrafficPhase.EW_GREEN]),
            'yellow': sum(1 for tl in self.traffic_lights.values() 
                        if tl.current_phase in [TrafficPhase.NS_YELLOW, TrafficPhase.EW_YELLOW]),
            'red': sum(1 for tl in self.traffic_lights.values() 
                     if tl.current_phase in [TrafficPhase.NS_RED, TrafficPhase.EW_RED, TrafficPhase.ALL_RED]),
            'time_of_day': self.time_of_day.value,
            'zones_active': len(self.coordination_zones)
        }
        
        return stats
    
    def export_for_visualization(self) -> List[Dict]:
        """Export traffic light states for visualization"""
        
        lights_data = []
        
        for tl in self.traffic_lights.values():
            lights_data.append({
                'id': tl.id,
                'lat': tl.lat,
                'lon': tl.lon,
                'intersection': tl.intersection,
                'color': tl.get_color(),
                'phase': tl.current_phase.value,
                'ns_state': tl.get_ns_state(),
                'ew_state': tl.get_ew_state(),
                'powered': tl.powered,
                'zone': tl.zone,
                'cycle_position': f"{tl.phase_timer}s",
                'battery_backup': tl.battery_backup
            })
        
        return lights_data

# Example usage integration
def integrate_with_power_system(controller: ManhattanTrafficController, power_system):
    """Integrate traffic controller with power system"""
    
    # Update traffic lights based on power status
    for tl_id, tl in controller.traffic_lights.items():
        # Check power status from power system
        power_status = power_system.get_component_status(tl_id)
        tl.powered = power_status
        
        # If no power and no battery backup, light goes off
        if not tl.powered and not tl.battery_backup:
            tl.current_phase = TrafficPhase.OFF
        elif not tl.powered and tl.battery_backup:
            # Battery backup - flashing red
            tl.current_phase = TrafficPhase.FLASHING_RED