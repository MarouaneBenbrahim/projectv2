"""
fix_vehicle_coordinates.py - Fix vehicle positions on map
This ensures vehicles stay on roads and don't jump when zooming
"""

# Add this improved method to your manhattan_sumo_manager.py

def get_vehicle_positions_for_visualization(self) -> List[Dict]:
    """Get vehicle data with CORRECTED coordinates for web visualization"""
    
    if not self.running:
        return []
    
    try:
        import traci
        vehicles_data = []
        
        for vehicle in self.vehicles.values():
            try:
                if vehicle.id in traci.vehicle.getIDList():
                    # Get position from SUMO (in SUMO's internal coordinate system)
                    x, y = traci.vehicle.getPosition(vehicle.id)
                    
                    # CRITICAL: Use SUMO's built-in coordinate conversion
                    # This ensures vehicles stay on the actual roads
                    lon, lat = traci.simulation.convertGeo(x, y)
                    
                    # Additional validation - ensure within Manhattan bounds
                    if not (self.bounds['south'] <= lat <= self.bounds['north'] and
                            self.bounds['west'] <= lon <= self.bounds['east']):
                        # If outside bounds, try alternative conversion
                        lon, lat = self.net.convertXY2LonLat(x, y)
                    
                    # Final bounds check
                    if (self.bounds['south'] <= lat <= self.bounds['north'] and
                        self.bounds['west'] <= lon <= self.bounds['east']):
                        
                        # Get the actual road/edge the vehicle is on
                        edge_id = traci.vehicle.getRoadID(vehicle.id)
                        lane_pos = traci.vehicle.getLanePosition(vehicle.id)
                        lane_id = traci.vehicle.getLaneID(vehicle.id)
                        
                        # Get vehicle angle for proper orientation
                        angle = traci.vehicle.getAngle(vehicle.id)
                        
                        vehicles_data.append({
                            'id': vehicle.id,
                            'lat': lat,
                            'lon': lon,
                            'type': vehicle.config.vtype.value,
                            'speed': vehicle.speed,
                            'speed_kmh': round(vehicle.speed * 3.6, 1),
                            'soc': vehicle.config.current_soc if vehicle.config.is_ev else 1.0,
                            'battery_percent': round(vehicle.config.current_soc * 100) if vehicle.config.is_ev else 100,
                            'is_charging': vehicle.is_charging,
                            'is_ev': vehicle.config.is_ev,
                            'distance_traveled': round(vehicle.distance_traveled, 1),
                            'waiting_time': round(vehicle.waiting_time, 1),
                            'destination': vehicle.destination,
                            'assigned_station': vehicle.assigned_ev_station,
                            'color': self._get_vehicle_color(vehicle),
                            'angle': angle,  # For proper vehicle orientation
                            'edge': edge_id,  # Which road they're on
                            'lane_pos': lane_pos,  # Position along the road
                            'lane_id': lane_id  # Which lane
                        })
            except Exception as e:
                # Skip vehicle if position can't be determined
                continue
        
        return vehicles_data
    
    except Exception as e:
        print(f"Error getting vehicle positions: {e}")
        return []

# Also update the main route to ensure vehicles are on connected roads
def spawn_vehicles_improved(self, count: int = 10, ev_percentage: float = 0.3) -> int:
    """Spawn vehicles ensuring they start on actual roads"""
    
    if not self.running:
        return 0
    
    import traci
    spawned = 0
    
    # Use validated spawn edges
    spawn_edges = self.spawn_edges if self.spawn_edges else self.edges
    if not spawn_edges:
        return 0
    
    for i in range(count):
        vehicle_id = f"veh_{self.stats['total_vehicles'] + i}"
        
        # Vehicle type selection
        is_ev = random.random() < ev_percentage
        if is_ev:
            vtype = "ev_sedan" if random.random() < 0.6 else "ev_suv"
        else:
            vtype = random.choice(["car", "taxi"])
        
        # Try to create a valid route on actual roads
        for attempt in range(5):
            try:
                # Use edges we know are connected
                origin = spawn_edges[i % len(spawn_edges)]
                dest = spawn_edges[(i + 10) % len(spawn_edges)]
                
                if origin != dest:
                    # Create route that SUMO can actually follow
                    route_id = f"route_{vehicle_id}"
                    
                    # Let SUMO compute the actual route between edges
                    # This ensures vehicles follow real roads
                    route = traci.simulation.findRoute(origin, dest)
                    
                    if route and route.edges:
                        # Use the computed route
                        traci.route.add(route_id, route.edges)
                    else:
                        # Fallback to direct route
                        traci.route.add(route_id, [origin, dest])
                    
                    # Add vehicle on this route
                    traci.vehicle.add(
                        vehicle_id,
                        route_id,
                        typeID=vtype,
                        depart="now"
                    )
                    
                    # Track the vehicle
                    self.vehicles[vehicle_id] = Vehicle(
                        vehicle_id,
                        VehicleConfig(
                            id=vehicle_id,
                            vtype=VehicleType.EV_SEDAN if vtype == "ev_sedan" else 
                                   VehicleType.EV_SUV if vtype == "ev_suv" else
                                   VehicleType.TAXI if vtype == "taxi" else VehicleType.CAR,
                            origin=origin,
                            destination=dest,
                            is_ev=is_ev,
                            battery_capacity_kwh=75 if vtype == "ev_sedan" else (100 if vtype == "ev_suv" else 0),
                            current_soc=random.uniform(0.3, 0.9) if is_ev else 1.0
                        )
                    )
                    
                    spawned += 1
                    if is_ev:
                        self.stats['ev_vehicles'] += 1
                    
                    break  # Success, move to next vehicle
                    
            except Exception as e:
                continue  # Try again
    
    self.stats['total_vehicles'] += spawned
    return spawned