"""
Manhattan Vehicle Type Definitions for SUMO
Creates proper vehicle type file with all EV and gas vehicles
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom

def create_vehicle_types():
    """Create comprehensive vehicle type definitions"""
    
    root = ET.Element("additional")
    
    # EV Types with proper colors (RGBA format)
    ev_types = {
        "tesla_model3": {
            "length": "4.69",
            "width": "1.85",
            "height": "1.44",
            "color": "204,26,26,255",  # Tesla Red
            "accel": "2.6",
            "decel": "4.5",
            "maxSpeed": "60",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/zero",
            "guiShape": "passenger/sedan",
            "battery_capacity": "75000"
        },
        "tesla_modely": {
            "length": "4.75",
            "width": "1.92",
            "height": "1.62",
            "color": "230,230,230,255",  # Pearl White
            "accel": "3.5",
            "decel": "4.5",
            "maxSpeed": "55",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/zero",
            "guiShape": "passenger/van",
            "battery_capacity": "82000"
        },
        "nissan_leaf": {
            "length": "4.48",
            "width": "1.79",
            "height": "1.55",
            "color": "0,153,76,255",  # Green
            "accel": "2.2",
            "decel": "4.3",
            "maxSpeed": "50",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/zero",
            "guiShape": "passenger/sedan",
            "battery_capacity": "40000"
        },
        "rivian_r1t": {
            "length": "5.51",
            "width": "2.01",
            "height": "1.8",
            "color": "51,102,51,255",  # Rivian Green
            "accel": "3.0",
            "decel": "4.0",
            "maxSpeed": "60",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/zero",
            "guiShape": "truck",
            "battery_capacity": "135000"
        },
        "bmw_i4": {
            "length": "4.78",
            "width": "1.85",
            "height": "1.45",
            "color": "0,76,178,255",  # BMW Blue
            "accel": "2.4",
            "decel": "4.5",
            "maxSpeed": "65",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/zero",
            "guiShape": "passenger/sedan",
            "battery_capacity": "80000"
        },
        "ford_mache": {
            "length": "4.71",
            "width": "1.88",
            "height": "1.6",
            "color": "255,128,0,255",  # Orange
            "accel": "2.6",
            "decel": "4.3",
            "maxSpeed": "60",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/zero",
            "guiShape": "passenger/van",
            "battery_capacity": "88000"
        }
    }
    
    # Gas vehicle types
    gas_types = {
        "toyota_camry": {
            "length": "4.88",
            "width": "1.84",
            "height": "1.45",
            "color": "178,178,178,255",  # Silver
            "accel": "2.8",
            "decel": "4.2",
            "maxSpeed": "55",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/PC_G_EU4",
            "guiShape": "passenger/sedan"
        },
        "honda_accord": {
            "length": "4.93",
            "width": "1.86",
            "height": "1.45",
            "color": "51,51,51,255",  # Dark Gray
            "accel": "2.9",
            "decel": "4.1",
            "maxSpeed": "55",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/PC_G_EU4",
            "guiShape": "passenger/sedan"
        },
        "ford_f150": {
            "length": "5.89",
            "width": "2.03",
            "height": "1.96",
            "color": "0,0,127,255",  # Ford Blue
            "accel": "3.5",
            "decel": "3.8",
            "maxSpeed": "50",
            "vClass": "passenger",
            "emissionClass": "HBEFA3/PC_G_EU4",
            "guiShape": "truck"
        }
    }
    
    # Create EV types
    for type_id, props in ev_types.items():
        vtype = ET.SubElement(root, "vType")
        vtype.set("id", type_id)
        vtype.set("length", props["length"])
        vtype.set("width", props["width"])
        vtype.set("height", props["height"])
        vtype.set("color", props["color"])
        vtype.set("accel", props["accel"])
        vtype.set("decel", props["decel"])
        vtype.set("maxSpeed", props["maxSpeed"])
        vtype.set("vClass", props["vClass"])
        vtype.set("emissionClass", props["emissionClass"])
        vtype.set("guiShape", props["guiShape"])
        
        # Battery parameters
        ET.SubElement(vtype, "param", key="has.battery.device", value="true")
        ET.SubElement(vtype, "param", key="maximumBatteryCapacity", value=props["battery_capacity"])
        ET.SubElement(vtype, "param", key="vehicleMass", value="1800")
    
    # Create gas types
    for type_id, props in gas_types.items():
        vtype = ET.SubElement(root, "vType")
        vtype.set("id", type_id)
        vtype.set("length", props["length"])
        vtype.set("width", props["width"])
        vtype.set("height", props["height"])
        vtype.set("color", props["color"])
        vtype.set("accel", props["accel"])
        vtype.set("decel", props["decel"])
        vtype.set("maxSpeed", props["maxSpeed"])
        vtype.set("vClass", props["vClass"])
        vtype.set("emissionClass", props["emissionClass"])
        vtype.set("guiShape", props["guiShape"])
    
    # Pretty print
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")
    
    with open("data/vehicle_types.add.xml", "w") as f:
        f.write(xml_str)
    
    print("✅ Created vehicle type definitions")

if __name__ == "__main__":
    create_vehicle_types()