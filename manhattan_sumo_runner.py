"""
Manhattan SUMO Integration - Step 2: Run Simulation with Power Grid
Real-time vehicle simulation that responds to traffic lights and seeks charging
"""

import os
import sys
import traci
import sumolib
import json
import time
import threading
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Add SUMO to path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    print("Please set SUMO_HOME environment variable")

@dataclass
class VehicleInfo:
    """Track vehicle information"""
    id: str
    type: str
    position: Tuple[float, float]
    speed: float
    route: str
    battery: Optional[float] = None
    is_charging: bool = False
    destination: Optional[str] = None
    state: str = "moving"  # moving, stopped, charging, waiting

class ManhattanSUMORunner:
    """
    Runs SUMO simulation integrated with your power grid
    """
    
    def __init__(self, power_system=None):
        self.power_system = power_system
        self.running = False
        self.vehicles = {}
        self.charging_queue = {}  # Station ID -> List of waiting vehicles
        self.traffic_light_states = {}
        self.charging_stations_status = {}
        self.simulation_time = 0
        
        # Statistics
        self.stats = {
            "total_vehicles": 0,
            "evs": 0,
            "evs_charging": 0,
            "evs_seeking_charge": 0,
            "average_speed": 0,
            "stopped_at_lights": 0,
            "total_distance": 0,
            "energy_consumed": 0
        }
        
    def start_sumo(self, gui=True):
        """Start SUMO simulation"""
        
        sumo_binary = "sumo-gui" if gui else "sumo"
        
        # Check if files exist
        config_file = "data/manhattan.sumocfg"
        if not os.path.exists(config_file):
            print("ERROR: Run vehicle generator first!")
            return False
        
        # SUMO command with cool options
        sumo_cmd = [
            sumo_binary,
            "-c", config_file,
            "--step-length", "0.1",  # 100ms steps for smooth movement
            "--collision.action", "warn",
            "--collision.check-junctions", "true",
            "--gui-settings-file", "data/gui_settings.xml"
        ]
        
        if gui:
            sumo_cmd.extend([
                "--window-size", "1920,1080",
                "--window-pos", "50,50",
                "--delay", "50",  # 50ms delay for visible movement
                "--scheme", "real-world"
            ])
        
        try:
            traci.start(sumo_cmd)
            self.running = True
            print("✅ SUMO started successfully!")
            
            # Get traffic lights
            self.traffic_light_ids = traci.trafficlight.getIDList()
            print(f"Found {len(self.traffic_light_ids)} traffic lights")
            
            # Initialize charging stations
            self._init_charging_stations()
            
            return True
            
        except Exception as e:
            print(f"Failed to start SUMO: {e}")
            return False
    
    def _init_charging_stations(self):
        """Initialize charging station status"""
        
        # Your charging stations from the generator
        stations = [
            {"id": "cs_times_square", "capacity": 50, "power_per_charger": 150},
            {"id": "cs_penn_station", "capacity": 40, "power_per_charger": 150},
            {"id": "cs_grand_central", "capacity": 60, "power_per_charger": 150},
            {"id": "cs_bryant_park", "capacity": 30, "power_per_charger": 150},
            {"id": "cs_columbus_circle", "capacity": 35, "power_per_charger": 150},
            {"id": "cs_murray_hill", "capacity": 25, "power_per_charger": 150},
            {"id": "cs_turtle_bay", "capacity": 20, "power_per_charger": 150},
            {"id": "cs_midtown_east", "capacity": 30, "power_per_charger": 150}
        ]
        
        for station in stations:
            self.charging_stations_status[station["id"]] = {
                "capacity": station["capacity"],
                "occupied": 0,
                "available": station["capacity"],
                "queue": [],
                "power_kw": station["power_per_charger"],
                "operational": True,
                "total_power_draw": 0
            }
            self.charging_queue[station["id"]] = []
        
        print(f"Initialized {len(self.charging_stations_status)} charging stations")
    
    def sync_with_power_grid(self):
        """Sync traffic lights with power grid status"""
        
        if not self.power_system:
            return
        
        # Get traffic light states from your power system
        network_state = self.power_system.get_network_state()
        
        for tl in network_state.get('traffic_lights', []):
            tl_id = f"tl_{tl['id']}"  # Match SUMO traffic light ID
            
            if tl_id in self.traffic_light_ids:
                if not tl['powered']:
                    # No power - set to blinking or off
                    self._set_traffic_light_failed(tl_id)
                else:
                    # Update based on phase from your traffic controller
                    phase = tl.get('phase', 'normal')
                    self._update_traffic_light_phase(tl_id, phase)
        
        # Update charging station availability based on power
        for station_id, status in self.charging_stations_status.items():
            # Check if substation powering this station is operational
            # This would come from your power grid
            status["operational"] = self._check_station_power(station_id)
    
    def _set_traffic_light_failed(self, tl_id):
        """Set traffic light to failed state (no power)"""
        try:
            # Set all lights to blinking red or off
            program = traci.trafficlight.getProgram(tl_id)
            
            # Create all-red state
            red_state = "r" * len(traci.trafficlight.getRedYellowGreenState(tl_id))
            traci.trafficlight.setRedYellowGreenState(tl_id, red_state)
            
        except:
            pass
    
    def _update_traffic_light_phase(self, tl_id, phase):
        """Update traffic light based on your controller phase"""
        try:
            current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
            
            # Map your phases to SUMO states
            if phase == "ns_green":
                new_state = "GGrrGGrr"  # N-S green, E-W red
            elif phase == "ew_green":
                new_state = "rrGGrrGG"  # E-W green, N-S red
            elif phase == "ns_yellow":
                new_state = "yyrryyyr"  # N-S yellow
            elif phase == "ew_yellow":
                new_state = "rryyrryy"  # E-W yellow
            else:
                new_state = "rrrrrrrr"  # All red
            
            # Ensure state length matches
            if len(new_state) == len(current_state):
                traci.trafficlight.setRedYellowGreenState(tl_id, new_state)
                
        except:
            pass
    
    def _check_station_power(self, station_id):
        """Check if charging station has power"""
        # Map station to substation
        station_substations = {
            "cs_times_square": "Times Square",
            "cs_penn_station": "Penn Station",
            "cs_grand_central": "Grand Central",
            "cs_bryant_park": "Times Square",
            "cs_columbus_circle": "Columbus Circle",
            "cs_murray_hill": "Murray Hill",
            "cs_turtle_bay": "Turtle Bay",
            "cs_midtown_east": "Midtown East"
        }
        
        if self.power_system:
            substation = station_substations.get(station_id)
            # Check if substation is operational
            # This would query your actual power system
            return True  # Simplified
        
        return True
    
    def simulation_step(self):
        """Execute one simulation step"""
        
        if not self.running:
            return
        
        try:
            # Advance SUMO simulation
            traci.simulationStep()
            self.simulation_time += 0.1  # 100ms per step
            
            # Update vehicle information
            self._update_vehicles()
            
            # Manage EV charging
            self._manage_ev_charging()
            
            # Sync with power grid
            if int(self.simulation_time) % 10 == 0:  # Every 10 seconds
                self.sync_with_power_grid()
            
            # Update statistics
            self._update_statistics()
            
        except traci.exceptions.FatalTraCIError:
            print("Simulation ended")
            self.running = False
    
    def _update_vehicles(self):
        """Update all vehicle information"""
        
        vehicle_ids = traci.vehicle.getIDList()
        
        for veh_id in vehicle_ids:
            # Get vehicle data
            position = traci.vehicle.getPosition(veh_id)
            speed = traci.vehicle.getSpeed(veh_id)
            vtype = traci.vehicle.getTypeID(veh_id)
            route = traci.vehicle.getRouteID(veh_id)
            
            # Check if EV and get battery
            battery = None
            is_charging = False
            
            try:
                # Get battery level for EVs
                battery = traci.vehicle.getParameter(veh_id, "device.battery.actualBatteryCapacity")
                if battery:
                    battery = float(battery)
                    
                    # Check if charging
                    charging_station = traci.vehicle.getParameter(veh_id, "device.battery.chargingStationID")
                    is_charging = (charging_station != "")
                    
                    # If battery < 20% and not charging, seek charging station
                    if battery < 10000 and not is_charging:  # 10kWh threshold
                        self._route_to_charging_station(veh_id)
                        
            except:
                pass
            
            # Determine state
            state = "moving"
            if speed < 0.1:
                # Check if at traffic light
                if self._is_at_traffic_light(veh_id):
                    state = "stopped_at_light"
                elif is_charging:
                    state = "charging"
                else:
                    state = "stopped"
            
            # Store vehicle info
            self.vehicles[veh_id] = VehicleInfo(
                id=veh_id,
                type=vtype,
                position=position,
                speed=speed,
                route=route,
                battery=battery,
                is_charging=is_charging,
                state=state
            )
    
    def _is_at_traffic_light(self, veh_id):
        """Check if vehicle is stopped at traffic light"""
        try:
            # Get next traffic light
            next_tls = traci.vehicle.getNextTLS(veh_id)
            if next_tls and len(next_tls) > 0:
                # Check if close to traffic light and red
                distance = next_tls[0][2]
                state = next_tls[0][3]
                return distance < 10 and state in ['r', 'y']
        except:
            pass
        return False
    
    def _route_to_charging_station(self, veh_id):
        """Route EV to nearest available charging station"""
        
        # Find nearest available station
        position = traci.vehicle.getPosition(veh_id)
        nearest_station = None
        min_distance = float('inf')
        
        for station_id, status in self.charging_stations_status.items():
            if status["operational"] and status["available"] > 0:
                # Calculate distance (simplified)
                # In reality, you'd use the road network distance
                station_edge = f"edge_near_{station_id}"
                try:
                    # Get station position
                    # This is simplified - you'd have actual positions
                    distance = min_distance  # Placeholder
                    
                    if distance < min_distance:
                        min_distance = distance
                        nearest_station = station_id
                except:
                    pass
        
        if nearest_station:
            # Add to queue
            if veh_id not in self.charging_queue[nearest_station]:
                self.charging_queue[nearest_station].append(veh_id)
                print(f"🔋 EV {veh_id} seeking charging at {nearest_station}")
    
    def _manage_ev_charging(self):
        """Manage EV charging queues and power draw"""
        
        for station_id, queue in self.charging_queue.items():
            status = self.charging_stations_status[station_id]
            
            # Process queue
            for veh_id in queue[:]:
                if veh_id in self.vehicles:
                    vehicle = self.vehicles[veh_id]
                    
                    if vehicle.is_charging:
                        # Update charging progress
                        if vehicle.battery:
                            # Charge at station rate
                            charge_rate = status["power_kw"] * 0.1  # kWh per step
                            # This would actually update SUMO's battery
                            
                            # Check if charged enough (80%)
                            if vehicle.battery > 60000:  # 60kWh
                                # Release charger
                                queue.remove(veh_id)
                                status["occupied"] -= 1
                                status["available"] += 1
                                print(f"✅ EV {veh_id} finished charging")
                    
                    elif status["available"] > 0:
                        # Start charging
                        status["occupied"] += 1
                        status["available"] -= 1
                        print(f"🔌 EV {veh_id} started charging at {station_id}")
            
            # Update power draw for power grid
            status["total_power_draw"] = status["occupied"] * status["power_kw"]
    
    def _update_statistics(self):
        """Update simulation statistics"""
        
        if not self.vehicles:
            return
        
        total_speed = 0
        evs = 0
        evs_charging = 0
        stopped_at_lights = 0
        
        for vehicle in self.vehicles.values():
            total_speed += vehicle.speed
            
            if vehicle.battery is not None:
                evs += 1
                if vehicle.is_charging:
                    evs_charging += 1
            
            if vehicle.state == "stopped_at_light":
                stopped_at_lights += 1
        
        self.stats["total_vehicles"] = len(self.vehicles)
        self.stats["evs"] = evs
        self.stats["evs_charging"] = evs_charging
        self.stats["average_speed"] = total_speed / max(1, len(self.vehicles))
        self.stats["stopped_at_lights"] = stopped_at_lights
    
    def get_vehicle_data_for_map(self):
        """Get vehicle data formatted for map display"""
        
        vehicles_data = []
        
        for vehicle in self.vehicles.values():
            # Convert SUMO position to lat/lon
            # This is simplified - you'd use actual coordinate conversion
            lon = -73.980 + (vehicle.position[0] / 111000)
            lat = 40.758 + (vehicle.position[1] / 111000)
            
            # Determine icon based on type
            icons = {
                "tesla_model3": "🔴",
                "tesla_modely": "⚪",
                "yellow_cab": "🚕",
                "uber_black": "⚫",
                "nypd_cruiser": "🚔",
                "fdny_truck": "🚒",
                "ups_truck": "📦",
                "mta_bus": "🚌",
                "nissan_leaf": "🟢",
                "rivian_truck": "🟩"
            }
            
            vehicles_data.append({
                "id": vehicle.id,
                "lat": lat,
                "lon": lon,
                "type": vehicle.type,
                "icon": icons.get(vehicle.type, "🚗"),
                "speed": vehicle.speed,
                "state": vehicle.state,
                "battery": vehicle.battery,
                "is_charging": vehicle.is_charging
            })
        
        return vehicles_data
    
    def get_charging_status(self):
        """Get charging station status for power grid"""
        
        charging_data = []
        
        for station_id, status in self.charging_stations_status.items():
            charging_data.append({
                "id": station_id,
                "capacity": status["capacity"],
                "occupied": status["occupied"],
                "available": status["available"],
                "queue_length": len(self.charging_queue[station_id]),
                "power_draw_kw": status["total_power_draw"],
                "operational": status["operational"]
            })
        
        return charging_data
    
    def run_continuous(self):
        """Run simulation continuously"""
        
        print("\n🚗 STARTING MANHATTAN TRAFFIC SIMULATION 🚗\n")
        
        while self.running:
            self.simulation_step()
            
            # Print stats every 10 seconds
            if int(self.simulation_time) % 100 == 0:  # Every 10 seconds (100 * 0.1s)
                print(f"\n📊 Time: {self.simulation_time:.1f}s")
                print(f"   Vehicles: {self.stats['total_vehicles']}")
                print(f"   EVs: {self.stats['evs']} ({self.stats['evs_charging']} charging)")
                print(f"   Avg Speed: {self.stats['average_speed']:.1f} m/s")
                print(f"   At Lights: {self.stats['stopped_at_lights']}")
                
                # Show charging station status
                total_charging = sum(s["occupied"] for s in self.charging_stations_status.values())
                total_capacity = sum(s["capacity"] for s in self.charging_stations_status.values())
                print(f"   Charging: {total_charging}/{total_capacity} stations in use")
            
            time.sleep(0.01)  # Small delay for GUI
    
    def stop(self):
        """Stop simulation"""
        self.running = False
        traci.close()
        print("Simulation stopped")

def main():
    """Run the integrated simulation"""
    
    # Initialize runner
    runner = ManhattanSUMORunner()
    
    # Start SUMO with GUI
    if runner.start_sumo(gui=True):
        try:
            # Run simulation
            runner.run_continuous()
        except KeyboardInterrupt:
            print("\nStopping simulation...")
        finally:
            runner.stop()

if __name__ == "__main__":
    main()