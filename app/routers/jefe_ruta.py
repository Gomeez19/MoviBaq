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
    """Retorna la lista de todos los conductores registrados y su ruta/bus actual."""
    from app.routers.auth import MOCK_USERS_DB
    conductors = []
    for email, u in MOCK_USERS_DB.items():
        if u.get("role") == UserRole.CONDUCTOR.value:
            conductors.append({
                "id": u["id"],
                "fullname": u["fullname"],
                "email": u["email"],
                "assigned_bus": u.get("assigned_bus"),
                "assigned_route": u.get("assigned_route")
            })
    return {"status": "success", "conductors": conductors}

@router.post("/assign-driver-route")
def assign_driver_route(
    driver_id: str = Body(..., embed=True),
    route_id: str = Body(..., embed=True),
    bus_id: Optional[str] = Body(None, embed=True),
    user: dict = Depends(require_role([UserRole.JEFE_RUTA, UserRole.ADMIN]))
):
    """Permite al Jefe de Ruta asignar o cambiar la ruta y el bus a un conductor específico."""
    from app.routers.auth import MOCK_USERS_DB
    if route_id not in MOCK_ROUTES:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    
    target_driver = None
    for u in MOCK_USERS_DB.values():
        if u["id"] == driver_id and u.get("role") == UserRole.CONDUCTOR.value:
            target_driver = u
            break
            
    if not target_driver:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
        
    target_driver["assigned_route"] = route_id
    if bus_id:
        target_driver["assigned_bus"] = bus_id
        if bus_id in BUS_TRACKER_STATE:
            BUS_TRACKER_STATE[bus_id]["route_id"] = route_id
            BUS_TRACKER_STATE[bus_id]["driver_name"] = target_driver["fullname"]
            BUS_TRACKER_STATE[bus_id]["path_idx"] = 0
            BUS_TRACKER_STATE[bus_id]["sub_step"] = 0.0

    return {
        "status": "success",
        "message": f"Conductor {target_driver['fullname']} asignado exitosamente a la ruta {route_id} (Bus: {target_driver.get('assigned_bus', 'Sin bus')})"
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
