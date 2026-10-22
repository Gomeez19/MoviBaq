from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Dict
import uuid

from app.schemas.transmetro import UserRole, FleetVehicleCreate
from app.routers.auth import require_role, MOCK_USERS_DB
from app.services.transmetro_service import BUS_TRACKER_STATE, MOCK_ROUTES

router = APIRouter(prefix="/api/admin", tags=["Administración General Transmetro"])

FLEET_DETAILS: Dict[str, dict] = {
    "TM-3201": {"plate": "WPL-842", "capacity": 50, "model_year": 2022, "chassis": "Scania K250UB", "last_maintenance": "2026-09-10"},
    "TM-3205": {"plate": "WPL-890", "capacity": 50, "model_year": 2022, "chassis": "Scania K250UB", "last_maintenance": "2026-09-18"},
    "TM-5301": {"plate": "WPL-722", "capacity": 50, "model_year": 2023, "chassis": "Mercedes-Benz OH1621", "last_maintenance": "2026-10-02"},
    "TM-7102": {"plate": "WPL-511", "capacity": 50, "model_year": 2021, "chassis": "Scania K250UB", "last_maintenance": "2026-08-30"},
    "TM-7108": {"plate": "WPL-903", "capacity": 50, "model_year": 2022, "chassis": "Scania K250UB", "last_maintenance": "2026-09-25"},
    "TM-8820": {"plate": "WPL-101", "capacity": 80, "model_year": 2024, "chassis": "Volvo B8RLE", "last_maintenance": "2026-10-12"},
    "TM-8824": {"plate": "WPL-450", "capacity": 80, "model_year": 2024, "chassis": "Volvo B8RLE", "last_maintenance": "2026-10-14"}
}

@router.get("/users")
def get_all_users(user: dict = Depends(require_role([UserRole.ADMIN]))):
    """Gestión de usuarios registrados y roles asignados."""
    users_list = []
    for email, u in MOCK_USERS_DB.items():
        users_list.append({
            "id": u["id"],
            "fullname": u["fullname"],
            "email": u["email"],
            "role": u["role"],
            "assigned_bus": u.get("assigned_bus"),
            "assigned_route": u.get("assigned_route")
        })
    return users_list

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    new_role: str = Body(..., embed=True),
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    for u in MOCK_USERS_DB.values():
        if u["id"] == user_id:
            u["role"] = new_role
            return {"status": "success", "message": f"Rol de {u['fullname']} actualizado a {new_role}"}
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

@router.get("/fleet")
def get_fleet_vehicles(user: dict = Depends(require_role([UserRole.ADMIN]))):
    """CRUD de flota y vehículos."""
    vehicles = []
    for bus_id, tracker in BUS_TRACKER_STATE.items():
        meta = FLEET_DETAILS.get(bus_id, {})
        vehicles.append({
            "bus_id": bus_id,
            "plate": tracker["plate"],
            "route_id": tracker["route_id"],
            "driver_name": tracker.get("driver_name", "Sin asignar"),
            "status": tracker.get("status", "Disponible"),
            "capacity": meta.get("capacity", 50),
            "model_year": meta.get("model_year", 2022),
            "chassis": meta.get("chassis", "Scania Padron"),
            "last_maintenance": meta.get("last_maintenance", "2026-09-01")
        })
    return vehicles

@router.post("/fleet")
def add_fleet_vehicle(
    payload: FleetVehicleCreate,
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    BUS_TRACKER_STATE[payload.bus_id] = {
        "route_id": payload.route_id,
        "plate": payload.plate,
        "path_idx": 0,
        "sub_step": 0.0,
        "speed_kmh": 0.0,
        "occupancy": 0,
        "driver_name": "Por asignar",
        "status": "Disponible",
        "in_shift": False,
        "manual_gps": False
    }
    FLEET_DETAILS[payload.bus_id] = {
        "plate": payload.plate,
        "capacity": payload.capacity,
        "model_year": payload.model_year,
        "chassis": payload.chassis,
        "last_maintenance": payload.last_maintenance
    }
    return {"status": "success", "message": f"Vehículo {payload.bus_id} registrado en la flota"}
