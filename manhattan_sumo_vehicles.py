"""
Manhattan SUMO Vehicle Simulation - Step 1: Vehicle Generation
Creates cool vehicles with EVs that seek charging stations
"""

import os
import sys
import random
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import numpy as np

class ManhattanVehicleGenerator:
    """
    Generate awesome vehicles for Manhattan with:
    - Cool colors and types
    - EVs with battery management
    - Realistic routes
    """
    
    def __init__(self):
        # Load your existing data
        self.load_existing_data()
        
        # Vehicle type definitions with COOL colors
        self.vehicle_types = {
            # Regular vehicles (70%)
            "tesla_model3": {
                "vClass": "passenger",
                "length": "4.69",
                "width": "2.1",
                "height": "1.44",
                "color": "0.8,0.1,0.1",  # Tesla Red
                "maxSpeed": "16.67",  # 60 km/h city speed
                "accel": "2.6",
                "decel": "4.5",
                "sigma": "0.5",
                "is_ev": True,
                "battery_capacity": "75000",  # 75 kWh
                "icon": "🔴"
            },
            "tesla_modely": {
                "vClass": "passenger",
                "length": "4.75",
                "width": "2.2",
                "height": "1.62",
                "color": "0.9,0.9,0.9",  # Pearl White
                "maxSpeed": "16.67",
                "accel": "3.5",
                "decel": "4.5",
                "is_ev": True,
                "battery_capacity": "82000",  # 82 kWh
                "icon": "⚪"
            },
            "yellow_cab": {
                "vClass": "taxi",
                "length": "4.8",
                "width": "1.9",
                "height": "1.5",
                "color": "1,0.9,0",  # NYC Taxi Yellow
                "maxSpeed": "16.67",
                "accel": "2.0",
                "decel": "4.0",
                "is_ev": False,
                "icon": "🚕"
            },
            "uber_black": {
                "vClass": "passenger",
                "length": "5.0",
                "width": "2.0",
                "height": "1.5",
                "color": "0.1,0.1,0.1",  # Black
                "maxSpeed": "16.67",
                "accel": "2.2",
                "decel": "4.2",
                "is_ev": False,
                "icon": "⚫"
            },
            "nypd_cruiser": {
                "vClass": "emergency",
                "length": "4.9",
                "width": "2.0",
                "height": "1.5",
                "color": "0,0,1",  # NYPD Blue
                "maxSpeed": "22.22",  # Can speed in emergency
                "accel": "3.0",
                "decel": "5.0",
                "is_ev": False,
                "icon": "🚔"
            },
            "fdny_truck": {
                "vClass": "emergency",
                "length": "10.0",
                "width": "2.5",
                "height": "3.5",
                "color": "1,0,0",  # Fire Red
                "maxSpeed": "19.44",
                "accel": "1.5",
                "decel": "3.5",
                "is_ev": False,
                "icon": "🚒"
            },
            "ups_truck": {
                "vClass": "delivery",
                "length": "7.0",
                "width": "2.4",
                "height": "3.0",
                "color": "0.4,0.2,0",  # UPS Brown
                "maxSpeed": "13.89",
                "accel": "1.2",
                "decel": "3.0",
                "is_ev": False,
                "icon": "📦"
            },
            "mta_bus": {
                "vClass": "bus",
                "length": "12.0",
                "width": "2.5",
                "height": "3.2",
                "color": "0,0.3,0.8",  # MTA Blue
                "maxSpeed": "11.11",
                "accel": "1.0",
                "decel": "3.0",
                "is_ev": False,
                "icon": "🚌"
            },
            "nissan_leaf": {
                "vClass": "passenger",
                "length": "4.48",
                "width": "1.79",
                "height": "1.55",
                "color": "0,0.6,0.3",  # Green for EV
                "maxSpeed": "16.67",
                "accel": "2.2",
                "decel": "4.3",
                "is_ev": True,
                "battery_capacity": "40000",  # 40 kWh
                "icon": "🟢"
            },
            "rivian_truck": {
                "vClass": "passenger",
                "length": "5.5",
                "width": "2.1",
                "height": "1.8",
                "color": "0.2,0.4,0.2",  # Rivian Green
                "maxSpeed": "16.67",
                "accel": "3.0",
                "decel": "4.0",
                "is_ev": True,
                "battery_capacity": "135000",  # 135 kWh
                "icon": "🟩"
            }
        }
        
        # Manhattan hotspots for destinations
        self.destinations = {
            "times_square": {"lat": 40.7580, "lon": -73.9855, "type": "entertainment"},
            "grand_central": {"lat": 40.7527, "lon": -73.9772, "type": "transport"},
            "penn_station": {"lat": 40.7505, "lon": -73.9934, "type": "transport"},
            "columbus_circle": {"lat": 40.7681, "lon": -73.9819, "type": "shopping"},
            "bryant_park": {"lat": 40.7536, "lon": -73.9832, "type": "leisure"},
            "herald_square": {"lat": 40.7484, "lon": -73.9878, "type": "shopping"},
            "rockefeller": {"lat": 40.7587, "lon": -73.9787, "type": "business"},
            "madison_square": {"lat": 40.7462, "lon": -73.9872, "type": "leisure"}
        }
        
    def load_existing_data(self):
        """Load your existing charging stations and traffic lights"""
        
        # Load EV charging stations from your integrated backend
        self.charging_stations = [
            {"id": "cs_times_square", "lat": 40.758, "lon": -73.985, "capacity": 50},
            {"id": "cs_penn_station", "lat": 40.750, "lon": -73.993, "capacity": 40},
            {"id": "cs_grand_central", "lat": 40.752, "lon": -73.977, "capacity": 60},
            {"id": "cs_bryant_park", "lat": 40.754, "lon": -73.984, "capacity": 30},
            {"id": "cs_columbus_circle", "lat": 40.768, "lon": -73.982, "capacity": 35},
            {"id": "cs_murray_hill", "lat": 40.748, "lon": -73.978, "capacity": 25},
            {"id": "cs_turtle_bay", "lat": 40.755, "lon": -73.969, "capacity": 20},
            {"id": "cs_midtown_east", "lat": 40.760, "lon": -73.970, "capacity": 30}
        ]
        
        # Check if SUMO network exists
        self.network_file = "data/manhattan.net.xml"
        if not os.path.exists(self.network_file):
            print("WARNING: manhattan.net.xml not found. Run get_manhattan_network.py first!")
    
    def generate_vehicle_types_xml(self):
        """Generate vType definitions for SUMO"""
        
        root = ET.Element("additional")
        
        for type_id, config in self.vehicle_types.items():
            vtype = ET.SubElement(root, "vType")
            vtype.set("id", type_id)
            vtype.set("vClass", config["vClass"])
            vtype.set("length", config["length"])
            vtype.set("width", config["width"])
            vtype.set("height", config["height"])
            vtype.set("color", config["color"])
            vtype.set("maxSpeed", config["maxSpeed"])
            vtype.set("accel", config["accel"])
            vtype.set("decel", config["decel"])
            
            # Add battery for EVs
            if config.get("is_ev", False):
                # Battery device
                ET.SubElement(vtype, "param", key="has.battery.device", value="true")
                ET.SubElement(vtype, "param", key="battery.capacity", value=config["battery_capacity"])
                
                # Start with 50-90% charge
                initial_charge = random.uniform(0.5, 0.9) * float(config["battery_capacity"])
                ET.SubElement(vtype, "param", key="battery.actualCharge", value=str(initial_charge))
                
                # Consumption model
                ET.SubElement(vtype, "param", key="battery.vehicleMass", value="1800")
                ET.SubElement(vtype, "param", key="battery.maximumPower", value="150000")
                
                # Make EVs seek charging when low
                ET.SubElement(vtype, "param", key="device.battery.chargingStationId", value="")
                ET.SubElement(vtype, "param", key="device.battery.chargeInTransit", value="false")
        
        # Pretty print
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")
        
        with open("data/vehicle_types.add.xml", "w") as f:
            f.write(xml_str)
        
        print("✅ Generated vehicle_types.add.xml with cool vehicle definitions!")
    
    def generate_charging_stations_xml(self):
        """Generate charging station definitions for SUMO"""
        
        root = ET.Element("additional")
        
        for station in self.charging_stations:
            cs = ET.SubElement(root, "chargingStation")
            cs.set("id", station["id"])
            
            # Place on nearest edge (simplified - you'd match to actual edges)
            edge_id = f"edge_near_{station['id']}"
            cs.set("lane", f"{edge_id}_0")
            cs.set("startPos", "10")
            cs.set("endPos", str(10 + station["capacity"] * 2))  # Bigger stations are longer
            cs.set("power", "150000")  # 150kW fast charging
            cs.set("efficiency", "0.95")
            
            # Visual indicator
            ET.SubElement(cs, "param", key="color", value="0,1,0")  # Green for charging
            ET.SubElement(cs, "param", key="capacity", value=str(station["capacity"]))
        
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")
        
        with open("data/charging_stations.add.xml", "w") as f:
            f.write(xml_str)
        
        print(f"✅ Generated {len(self.charging_stations)} charging stations!")
    
    def generate_vehicle_routes(self, num_vehicles=500, duration=3600):
        """Generate realistic vehicle routes with time-based patterns"""
        
        root = ET.Element("routes")
        
        # Vehicle distribution
        vehicle_distribution = {
            "tesla_model3": 0.10,      # 10% Tesla Model 3
            "tesla_modely": 0.08,      # 8% Tesla Model Y
            "nissan_leaf": 0.07,       # 7% Nissan Leaf
            "rivian_truck": 0.05,      # 5% Rivian (30% total EVs)
            "yellow_cab": 0.20,        # 20% Yellow cabs
            "uber_black": 0.15,        # 15% Uber
            "nypd_cruiser": 0.02,      # 2% Police
            "fdny_truck": 0.01,        # 1% Fire trucks
            "ups_truck": 0.07,         # 7% Delivery
            "mta_bus": 0.05,           # 5% Buses
            # Rest are random cars (20%)
        }
        
        current_time = 0
        vehicle_id = 0
        
        # Generate vehicles throughout the simulation
        while current_time < duration:
            # Determine spawn rate based on time (simplified)
            hour = (current_time // 3600) % 24
            
            if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
                spawn_rate = 0.5  # Vehicle every 0.5 seconds
            elif 0 <= hour <= 6:  # Night
                spawn_rate = 5.0  # Vehicle every 5 seconds
            else:  # Normal hours
                spawn_rate = 1.0  # Vehicle every second
            
            # Choose vehicle type
            rand = random.random()
            cumulative = 0
            chosen_type = "tesla_model3"  # Default
            
            for vtype, prob in vehicle_distribution.items():
                cumulative += prob
                if rand < cumulative:
                    chosen_type = vtype
                    break
            
            # Create vehicle
            vehicle = ET.SubElement(root, "vehicle")
            vehicle.set("id", f"veh_{vehicle_id}")
            vehicle.set("type", chosen_type)
            vehicle.set("depart", str(current_time))
            
            # Determine route based on vehicle type and time
            route = self.generate_route_for_vehicle(chosen_type, hour)
            vehicle.set("from", route["from"])
            vehicle.set("to", route["to"])
            
            # Special behavior for EVs - monitor battery
            if self.vehicle_types[chosen_type].get("is_ev", False):
                ET.SubElement(vehicle, "param", key="device.battery.chargingStrategy", 
                            value="opportunistic")
                ET.SubElement(vehicle, "param", key="device.battery.minCharge", value="10000")
            
            vehicle_id += 1
            current_time += spawn_rate
        
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")
        
        with open("data/vehicle_routes.rou.xml", "w") as f:
            f.write(xml_str)
        
        print(f"✅ Generated {vehicle_id} vehicles with realistic routes!")
        print(f"   - {int(vehicle_id * 0.3)} EVs that will seek charging")
        print(f"   - {int(vehicle_id * 0.2)} Taxis")
        print(f"   - {int(vehicle_id * 0.03)} Emergency vehicles")
    
    def generate_route_for_vehicle(self, vehicle_type, hour):
        """Generate realistic route based on vehicle type and time"""
        
        # Simplified - in reality you'd use actual edge IDs from your network
        edges = ["edge_1", "edge_2", "edge_3", "edge_4", "edge_5"]
        
        if vehicle_type in ["yellow_cab", "uber_black"]:
            # Taxis go between popular destinations
            destinations = list(self.destinations.keys())
            from_dest = random.choice(destinations)
            to_dest = random.choice([d for d in destinations if d != from_dest])
        
        elif vehicle_type in ["nypd_cruiser", "fdny_truck"]:
            # Emergency vehicles patrol or respond
            from_dest = "times_square"
            to_dest = random.choice(list(self.destinations.keys()))
        
        elif vehicle_type == "mta_bus":
            # Buses follow fixed routes
            from_dest = "penn_station"
            to_dest = "grand_central"
        
        else:
            # Regular vehicles - time-based patterns
            if 7 <= hour <= 9:  # Morning commute
                from_dest = random.choice(["columbus_circle", "bryant_park"])
                to_dest = random.choice(["rockefeller", "grand_central"])
            elif 17 <= hour <= 19:  # Evening commute
                from_dest = random.choice(["rockefeller", "grand_central"])
                to_dest = random.choice(["columbus_circle", "bryant_park"])
            else:  # Random trips
                destinations = list(self.destinations.keys())
                from_dest = random.choice(destinations)
                to_dest = random.choice([d for d in destinations if d != from_dest])
        
        return {"from": from_dest, "to": to_dest}
    
    def generate_sumo_config(self):
        """Generate SUMO configuration file"""
        
        config = """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="manhattan.net.xml"/>
        <route-files value="vehicle_routes.rou.xml"/>
        <additional-files value="vehicle_types.add.xml,charging_stations.add.xml"/>
    </input>
    
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="1"/>
    </time>
    
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="300"/>
        <max-depart-delay value="900"/>
        <device.emissions.probability value="1"/>
        <device.battery.probability value="1"/>
        <device.electricity.probability value="1"/>
    </processing>
    
    <gui_only>
        <gui-settings-file value="gui_settings.xml"/>
    </gui_only>
</configuration>"""
        
        with open("data/manhattan.sumocfg", "w") as f:
            f.write(config)
        
        print("✅ Generated SUMO configuration!")
    
    def generate_gui_settings(self):
        """Generate cool GUI settings for SUMO visualization"""
        
        settings = """<?xml version="1.0" encoding="UTF-8"?>
<viewsettings>
    <viewport y="40.758" x="-73.980" zoom="200"/>
    <scheme name="real-world">
        <vehicles vehicleMode="10" vehicleQuality="2" 
                  showBlinker="true" showBrakeLights="true" 
                  showRoute="true" vehicleSize="2.0">
            <colorScheme name="by_type"/>
        </vehicles>
        <persons personMode="1" personQuality="2" personSize="1.0"/>
        <background backgroundColor="20,20,20" showGrid="false"/>
    </scheme>
</viewsettings>"""
        
        with open("data/gui_settings.xml", "w") as f:
            f.write(settings)
        
        print("✅ Generated cool GUI settings!")
    
    def generate_all(self):
        """Generate all SUMO files"""
        
        print("\n🚗 GENERATING MANHATTAN VEHICLE SIMULATION 🚗\n")
        
        # Create data directory if not exists
        os.makedirs("data", exist_ok=True)
        
        # Generate all files
        self.generate_vehicle_types_xml()
        self.generate_charging_stations_xml()
        self.generate_vehicle_routes()
        self.generate_sumo_config()
        self.generate_gui_settings()
        
        print("\n✨ ALL FILES GENERATED! ✨")
        print("\nTo run the simulation:")
        print("  sumo-gui -c data/manhattan.sumocfg")
        print("\nVehicle Features:")
        print("  🔴 Tesla Model 3 - Seeks charging when low")
        print("  ⚪ Tesla Model Y - Long range EV")
        print("  🚕 Yellow Cabs - Classic NYC")
        print("  🚔 NYPD - Emergency response")
        print("  🚒 FDNY - Fire trucks")
        print("  📦 UPS - Delivery trucks")
        print("  🚌 MTA Buses - Public transport")
        print("  🟢 Nissan Leaf - Affordable EV")
        print("  🟩 Rivian - Electric truck")

if __name__ == "__main__":
    generator = ManhattanVehicleGenerator()
    generator.generate_all()