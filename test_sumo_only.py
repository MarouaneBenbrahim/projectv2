from core.sumo_manager import ManhattanSUMOManager
from integrated_backend import ManhattanIntegratedSystem
from core.power_system import ManhattanPowerGrid

# Initialize minimal system
power_grid = ManhattanPowerGrid()
integrated_system = ManhattanIntegratedSystem(power_grid)
sumo_manager = ManhattanSUMOManager(integrated_system)

# Test SUMO only
if sumo_manager.start_sumo(gui=False):
    spawned = sumo_manager.spawn_vehicles(10, 0.7)
    print(f"Test result: {spawned}/10 vehicles spawned")
    sumo_manager.stop()