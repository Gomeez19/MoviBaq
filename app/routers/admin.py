from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Dict, Optional
from pydantic import BaseModel
import uuid

from app.schemas.transmetro import UserRole, FleetVehicleCreate
from app.routers.auth import require_role, MOCK_USERS_DB
from app.services.transmetro_service import BUS_TRACKER_STATE, MOCK_ROUTES
from app.database import get_db, SessionLocal
from app.models import Usuario, Vehiculo
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/admin", tags=["Administración General Transmetro"])


# ─────────────────────────────────────────────
# SCHEMAS INTERNOS PARA EL CRUD
# ─────────────────────────────────────────────
class UserUpdate(BaseModel):
    fullname: Optional[str] = None
    role: Optional[str] = None
    assigned_bus_id: Optional[str] = None
    assigned_route_id: Optional[str] = None
    is_active: Optional[bool] = None

class FleetVehicleUpdate(BaseModel):
    plate: Optional[str] = None
    current_route_id: Optional[str] = None
    operational_status: Optional[str] = None
    capacity: Optional[int] = None
    model_year: Optional[int] = None
    chassis: Optional[str] = None
    last_maintenance: Optional[str] = None


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def get_db_session():
    """Retorna una sesión de BD si está disponible, o None en modo fallback."""
    if SessionLocal is None:
        return None
    return SessionLocal()


# ─────────────────────────────────────────────
# CRUD USUARIOS
# ─────────────────────────────────────────────

@router.get("/users")
def get_all_users(user: dict = Depends(require_role([UserRole.ADMIN]))):
    """Lista todos los usuarios del sistema desde la BD."""
    db = get_db_session()
    if db:
        try:
            db_users = db.query(Usuario).filter(Usuario.is_active == True).order_by(Usuario.created_at).all()
            if db_users:
                return [
                    {
                        "id": u.id,
                        "fullname": u.fullname,
                        "email": u.email,
                        "role": u.role,
                        "assigned_bus": u.assigned_bus_id,
                        "assigned_route": u.assigned_route_id,
                        "is_active": u.is_active
                    }
                    for u in db_users
                ]
        except Exception as e:
            print(f"[Admin GET /users BD Error]: {e}")
        finally:
            db.close()

    # Fallback a MOCK
    return [
        {
            "id": u["id"],
            "fullname": u["fullname"],
            "email": u["email"],
            "role": u["role"],
            "assigned_bus": u.get("assigned_bus"),
            "assigned_route": u.get("assigned_route"),
            "is_active": True
        }
        for u in MOCK_USERS_DB.values()
    ]


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    new_role: str = Body(..., embed=True),
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    """Cambia el rol de un usuario. Persiste en BD."""
    valid_roles = [r.value for r in UserRole]
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Opciones: {', '.join(valid_roles)}")

    db = get_db_session()
    if db:
        try:
            db_user = db.query(Usuario).filter(Usuario.id == user_id).first()
            if db_user:
                db_user.role = new_role
                db.commit()
                # Sync en MOCK
                if db_user.email in MOCK_USERS_DB:
                    MOCK_USERS_DB[db_user.email]["role"] = new_role
                return {"status": "success", "message": f"Rol de {db_user.fullname} actualizado a {new_role}"}
        except Exception as e:
            db.rollback()
            print(f"[Admin PUT /role BD Error]: {e}")
        finally:
            db.close()

    # Fallback MOCK
    for u in MOCK_USERS_DB.values():
        if u["id"] == user_id:
            u["role"] = new_role
            return {"status": "success", "message": f"Rol de {u['fullname']} actualizado a {new_role}"}
    raise HTTPException(status_code=404, detail="Usuario no encontrado")


@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdate,
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    """Edita datos de un usuario (nombre, rol, bus asignado, ruta, estado). Persiste en BD."""
    db = get_db_session()
    if db:
        try:
            db_user = db.query(Usuario).filter(Usuario.id == user_id).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            if payload.fullname is not None:
                db_user.fullname = payload.fullname
            if payload.role is not None:
                valid_roles = [r.value for r in UserRole]
                if payload.role not in valid_roles:
                    raise HTTPException(status_code=400, detail=f"Rol inválido: {payload.role}")
                db_user.role = payload.role
            if payload.assigned_bus_id is not None:
                db_user.assigned_bus_id = payload.assigned_bus_id or None
            if payload.assigned_route_id is not None:
                db_user.assigned_route_id = payload.assigned_route_id or None
            if payload.is_active is not None:
                db_user.is_active = payload.is_active

            db.commit()
            # Sync MOCK
            if db_user.email in MOCK_USERS_DB:
                mock_u = MOCK_USERS_DB[db_user.email]
                if payload.fullname: mock_u["fullname"] = payload.fullname
                if payload.role: mock_u["role"] = payload.role
            return {"status": "success", "message": f"Usuario {db_user.fullname} actualizado correctamente"}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"[Admin PUT /users BD Error]: {e}")
            raise HTTPException(status_code=500, detail="Error al actualizar usuario en la base de datos")
        finally:
            db.close()

    raise HTTPException(status_code=503, detail="Base de datos no disponible")


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    """Elimina (desactiva) un usuario. Soft-delete: marca is_active=False en BD."""
    # Prevenir auto-eliminación
    if user["id"] == user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de administrador.")

    db = get_db_session()
    if db:
        try:
            db_user = db.query(Usuario).filter(Usuario.id == user_id).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            db_user.is_active = False  # Soft delete
            db.commit()
            # Remover de MOCK
            MOCK_USERS_DB.pop(db_user.email, None)
            return {"status": "success", "message": f"Usuario {db_user.fullname} desactivado del sistema"}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"[Admin DELETE /users BD Error]: {e}")
            raise HTTPException(status_code=500, detail="Error al eliminar usuario")
        finally:
            db.close()

    # Fallback MOCK
    for email, u in list(MOCK_USERS_DB.items()):
        if u["id"] == user_id:
            del MOCK_USERS_DB[email]
            return {"status": "success", "message": f"Usuario {u['fullname']} eliminado"}
    raise HTTPException(status_code=404, detail="Usuario no encontrado")


# ─────────────────────────────────────────────
# CRUD FLOTA DE VEHÍCULOS
# ─────────────────────────────────────────────

@router.get("/fleet")
def get_fleet_vehicles(user: dict = Depends(require_role([UserRole.ADMIN]))):
    """Lista toda la flota de vehículos desde la BD."""
    db = get_db_session()
    if db:
        try:
            db_vehicles = db.query(Vehiculo).order_by(Vehiculo.bus_id).all()
            if db_vehicles:
                return [
                    {
                        "bus_id": v.bus_id,
                        "plate": v.plate,
                        "route_id": v.current_route_id,
                        "status": v.operational_status,
                        "capacity": v.capacity,
                        "model_year": v.model_year,
                        "chassis": v.chassis,
                        "last_maintenance": str(v.last_maintenance) if v.last_maintenance else "N/A"
                    }
                    for v in db_vehicles
                ]
        except Exception as e:
            print(f"[Admin GET /fleet BD Error]: {e}")
        finally:
            db.close()

    # Fallback MOCK
    return [
        {
            "bus_id": bus_id,
            "plate": tracker.get("plate", "N/A"),
            "route_id": tracker.get("route_id", "N/A"),
            "status": tracker.get("status", "Disponible"),
            "capacity": 50,
            "model_year": 2022,
            "chassis": "Scania K250UB / Busscar",
            "last_maintenance": "N/A"
        }
        for bus_id, tracker in BUS_TRACKER_STATE.items()
    ]


@router.post("/fleet")
def add_fleet_vehicle(
    payload: FleetVehicleCreate,
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    """Registra un nuevo vehículo. Persiste en BD."""
    db = get_db_session()
    if db:
        try:
            existing = db.query(Vehiculo).filter(Vehiculo.bus_id == payload.bus_id).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"El vehículo {payload.bus_id} ya existe en la flota.")

            new_vehicle = Vehiculo(
                bus_id=payload.bus_id,
                plate=payload.plate,
                current_route_id=payload.route_id or None,
                operational_status="Disponible",
                capacity=payload.capacity,
                model_year=payload.model_year,
                chassis=payload.chassis,
                last_maintenance=payload.last_maintenance
            )
            db.add(new_vehicle)
            db.commit()
            print(f"[Admin POST /fleet] Vehículo {payload.bus_id} registrado en BD")
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"[Admin POST /fleet BD Error]: {e}")
        finally:
            db.close()

    # Sync en BUS_TRACKER_STATE (memoria para telemetría en vivo)
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
    return {"status": "success", "message": f"Vehículo {payload.bus_id} registrado en la flota"}


@router.put("/fleet/{bus_id}")
def update_fleet_vehicle(
    bus_id: str,
    payload: FleetVehicleUpdate,
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    """Actualiza datos de un vehículo. Persiste en BD."""
    db = get_db_session()
    if db:
        try:
            db_vehicle = db.query(Vehiculo).filter(Vehiculo.bus_id == bus_id).first()
            if not db_vehicle:
                raise HTTPException(status_code=404, detail=f"Vehículo {bus_id} no encontrado")

            if payload.plate is not None:
                db_vehicle.plate = payload.plate
            if payload.current_route_id is not None:
                db_vehicle.current_route_id = payload.current_route_id or None
            if payload.operational_status is not None:
                db_vehicle.operational_status = payload.operational_status
            if payload.capacity is not None:
                db_vehicle.capacity = payload.capacity
            if payload.model_year is not None:
                db_vehicle.model_year = payload.model_year
            if payload.chassis is not None:
                db_vehicle.chassis = payload.chassis
            if payload.last_maintenance is not None:
                db_vehicle.last_maintenance = payload.last_maintenance

            db.commit()
            return {"status": "success", "message": f"Vehículo {bus_id} actualizado correctamente"}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"[Admin PUT /fleet BD Error]: {e}")
            raise HTTPException(status_code=500, detail="Error al actualizar vehículo")
        finally:
            db.close()

    raise HTTPException(status_code=503, detail="Base de datos no disponible")


@router.delete("/fleet/{bus_id}")
def delete_fleet_vehicle(
    bus_id: str,
    user: dict = Depends(require_role([UserRole.ADMIN]))
):
    """Elimina un vehículo de la flota. Persiste en BD."""
    db = get_db_session()
    if db:
        try:
            db_vehicle = db.query(Vehiculo).filter(Vehiculo.bus_id == bus_id).first()
            if not db_vehicle:
                raise HTTPException(status_code=404, detail=f"Vehículo {bus_id} no encontrado")

            db.delete(db_vehicle)
            db.commit()
            BUS_TRACKER_STATE.pop(bus_id, None)
            return {"status": "success", "message": f"Vehículo {bus_id} eliminado de la flota"}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"[Admin DELETE /fleet BD Error]: {e}")
            raise HTTPException(status_code=500, detail="Error al eliminar vehículo")
        finally:
            db.close()

    # Fallback MOCK
    if bus_id in BUS_TRACKER_STATE:
        del BUS_TRACKER_STATE[bus_id]
        return {"status": "success", "message": f"Vehículo {bus_id} eliminado (modo local)"}
    raise HTTPException(status_code=404, detail=f"Vehículo {bus_id} no encontrado")
