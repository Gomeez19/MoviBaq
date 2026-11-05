from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from typing import List, Optional
from datetime import datetime
import uuid

from app.schemas.transmetro import (
    UserRole,
    PreoperacionalRecord,
    IncidenteRecord,
    BusLiveStatus
)
from app.routers.auth import require_role
from app.services.transmetro_service import (
    PREOPERACIONALES_DB,
    INCIDENTES_DB,
    REGULACION_CCO_MESSAGES,
    BUS_TRACKER_STATE,
    MOCK_ROUTES,
    step_bus_simulation
)

router = APIRouter(prefix="/api/jefe-ruta", tags=["Centro de Control CCO - Jefe de Ruta"])

@router.get("/fleet-overview")
def get_fleet_overview(user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))):
    """
    Retorna el estado integral de la flota:
    - Todos los buses con ubicación GPS, velocidad, estado y retrasos.
    - Resumen de preoperacionales del día.
    - Incidentes activos.
    """
    all_buses = step_bus_simulation()

    # Identificar buses con posible retraso (ETA superior al promedio de frecuencia)
    delayed_buses = [b for b in all_buses if b.eta_minutes > 12]

    return {
        "status": "success",
        "jefe_control": user["fullname"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kpis": {
            "total_flota": len(BUS_TRACKER_STATE),
            "buses_en_ruta": len([b for b in BUS_TRACKER_STATE.values() if b.get("status") == "En Ruta"]),
            "buses_retrasados": len(delayed_buses),
            "incidentes_pendientes": len([i for i in INCIDENTES_DB if i.estado == "Pendiente"]),
            "preoperacionales_aprobados": len([p for p in PREOPERACIONALES_DB if p.estado_aprobacion == "Aprobado"]),
            "preoperacionales_rechazados": len([p for p in PREOPERACIONALES_DB if p.estado_aprobacion == "Rechazado"])
        },
        "buses": all_buses,
        "incidentes_recientes": INCIDENTES_DB[:5],
        "rutas": list(MOCK_ROUTES.values())
    }

@router.get("/preoperacionales", response_model=List[PreoperacionalRecord])
def get_all_preoperacionales(
    estado: Optional[str] = Query(None, description="Filtrar por Aprobado o Rechazado"),
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    """Listado de inspecciones preoperacionales enviadas por los conductores."""
    if estado:
        return [p for p in PREOPERACIONALES_DB if p.estado_aprobacion.lower() == estado.lower()]
    return PREOPERACIONALES_DB

@router.put("/preoperacionales/{preop_id}/status")
def update_preoperacional_status(
    preop_id: str,
    nuevo_estado: str = Body(..., embed=True), # "Aprobado", "Rechazado"
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    for p in PREOPERACIONALES_DB:
        if p.id == preop_id:
            p.estado_aprobacion = nuevo_estado
            # Actualizar estado del bus
            if p.bus_id in BUS_TRACKER_STATE:
                if nuevo_estado == "Aprobado":
                    BUS_TRACKER_STATE[p.bus_id]["status"] = "Disponible"
                else:
                    BUS_TRACKER_STATE[p.bus_id]["status"] = "Fuera de Servicio"
            return {"status": "success", "message": f"Preoperacional {preop_id} marcado como {nuevo_estado}"}
    raise HTTPException(status_code=404, detail="Preoperacional no encontrado")

@router.get("/incidentes", response_model=List[IncidenteRecord])
def get_all_incidentes(user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))):
    """Historial completo de incidentes reportados en vía."""
    return INCIDENTES_DB

@router.put("/incidentes/{incidente_id}/status")
def update_incidente_status(
    incidente_id: str,
    nuevo_estado: str = Body(..., embed=True), # "En Atención", "Resuelto"
    notas: Optional[str] = Body(None, embed=True),
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    for inc in INCIDENTES_DB:
        if inc.id == incidente_id:
            inc.estado = nuevo_estado
            if notas:
                inc.resolucion_notas = notas
            return {"status": "success", "message": f"Incidente {incidente_id} actualizado a {nuevo_estado}"}
    raise HTTPException(status_code=404, detail="Incidente no encontrado")

@router.post("/reassign-route")
def reassign_bus_route(
    bus_id: str = Body(..., embed=True),
    new_route_id: str = Body(..., embed=True),
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    """Reasigna un alimentador a otra ruta ante picos de demanda."""
    if bus_id not in BUS_TRACKER_STATE:
        raise HTTPException(status_code=404, detail="Bus no encontrado")
    if new_route_id not in MOCK_ROUTES:
        raise HTTPException(status_code=404, detail="Ruta destino no válida")

    BUS_TRACKER_STATE[bus_id]["route_id"] = new_route_id
    BUS_TRACKER_STATE[bus_id]["path_idx"] = 0
    BUS_TRACKER_STATE[bus_id]["sub_step"] = 0.0

    return {
        "status": "success",
        "message": f"Bus {bus_id} reasignado exitosamente a ruta {new_route_id}"
    }

@router.get("/conductors")
def get_conductors_list(user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))):
    """Retorna la lista de todos los conductores registrados en la BD y en memoria."""
    from app.routers.auth import MOCK_USERS_DB
    conductors_map = {}

    # 1. Buscar en BD Neon primero
    try:
        from app.database import SessionLocal
        from app.models import Usuario
        if SessionLocal:
            db = SessionLocal()
            try:
                # En PostgreSQL Neon, la columna role es tipo ENUM ('user_role_enum')
                # Por eso se debe comparar directamente con el valor exacto 'conductor'
                db_conductors = db.query(Usuario).filter(
                    Usuario.role == "conductor",
                    Usuario.is_active == True
                ).all()

                for u in db_conductors:
                    conductors_map[u.id] = {
                        "id": u.id,
                        "fullname": u.fullname,
                        "email": u.email,
                        "assigned_bus": u.assigned_bus_id,
                        "assigned_route": u.assigned_route_id
                    }
            finally:
                db.close()
    except Exception as e:
        print(f"[JefeRuta /conductors BD Error]: {e}")

    # 2. Complementar con MOCK_USERS_DB
    for email, u in MOCK_USERS_DB.items():
        if u.get("role") == UserRole.CONDUCTOR.value:
            uid = u["id"]
            if uid not in conductors_map:
                conductors_map[uid] = {
                    "id": u["id"],
                    "fullname": u["fullname"],
                    "email": u["email"],
                    "assigned_bus": u.get("assigned_bus"),
                    "assigned_route": u.get("assigned_route")
                }
            else:
                # Si en memoria tiene una asignación más reciente, preservarla
                if u.get("assigned_bus"):
                    conductors_map[uid]["assigned_bus"] = u.get("assigned_bus")
                if u.get("assigned_route"):
                    conductors_map[uid]["assigned_route"] = u.get("assigned_route")

    return {"status": "success", "conductors": list(conductors_map.values())}

@router.post("/assign-driver-route")
def assign_driver_route(
    driver_id: str = Body(..., embed=True),
    route_id: str = Body(..., embed=True),
    bus_id: Optional[str] = Body(None, embed=True),
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    """Permite al Jefe de Ruta asignar o cambiar la ruta y el bus a un conductor específico, guardando en BD y memoria."""
    from app.routers.auth import MOCK_USERS_DB
    if route_id not in MOCK_ROUTES:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    
    driver_name = "Conductor"
    driver_found = False

    # 1. Actualizar en Base de Datos Neon
    try:
        from app.database import SessionLocal
        from app.models import Usuario
        if SessionLocal:
            db = SessionLocal()
            try:
                db_user = db.query(Usuario).filter(Usuario.id == driver_id).first()
                if db_user:
                    db_user.assigned_route_id = route_id
                    db_user.assigned_bus_id = bus_id
                    db.commit()
                    driver_name = db_user.fullname
                    driver_found = True
                    # Mantener en MOCK_USERS_DB
                    if db_user.email in MOCK_USERS_DB:
                        MOCK_USERS_DB[db_user.email]["assigned_route"] = route_id
                        MOCK_USERS_DB[db_user.email]["assigned_bus"] = bus_id
            finally:
                db.close()
    except Exception as db_err:
        print(f"[AssignDriver BD Error]: {db_err}")

    # 2. Actualizar en MOCK_USERS_DB si no fue por BD o sincronizar
    for u in MOCK_USERS_DB.values():
        if u["id"] == driver_id:
            u["assigned_route"] = route_id
            u["assigned_bus"] = bus_id
            driver_name = u["fullname"]
            driver_found = True
            break
            
    if not driver_found:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")

    # 3. Actualizar estado del bus
    if bus_id:
        if bus_id not in BUS_TRACKER_STATE:
            BUS_TRACKER_STATE[bus_id] = {
                "route_id": route_id,
                "plate": "WPL-000",
                "path_idx": 0,
                "sub_step": 0.0,
                "speed_kmh": 0.0,
                "occupancy": 0,
                "driver_name": driver_name,
                "status": "Disponible",
                "in_shift": True,
                "manual_gps": False
            }
        else:
            BUS_TRACKER_STATE[bus_id]["route_id"] = route_id
            BUS_TRACKER_STATE[bus_id]["driver_name"] = driver_name
            BUS_TRACKER_STATE[bus_id]["path_idx"] = 0
            BUS_TRACKER_STATE[bus_id]["sub_step"] = 0.0

    return {
        "status": "success",
        "message": f"Conductor {driver_name} asignado exitosamente a la ruta {route_id} (Bus: {bus_id or 'Sin bus'})"
    }

@router.post("/send-message")
def send_regulation_message(
    bus_id: str = Body(..., embed=True),
    text: str = Body(..., embed=True),
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    """Envía un mensaje de regulación directa a la cabina del conductor."""
    msg = {
        "id": f"msg-{str(uuid.uuid4())[:6]}",
        "bus_id": bus_id,
        "sender": f"Jefe de Ruta ({user['fullname']})",
        "text": text,
        "time": datetime.now().strftime("%I:%M %p")
    }
    REGULACION_CCO_MESSAGES.insert(0, msg)
    return {"status": "success", "message": "Mensaje enviado a cabina"}
