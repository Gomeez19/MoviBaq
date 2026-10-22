from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import uuid
from datetime import datetime

from app.schemas.transmetro import (
    UserRole,
    PreoperacionalCreate,
    PreoperacionalRecord,
    IncidenteCreate,
    IncidenteRecord,
    DriverGPSUpdate,
    DriverStateChange
)
from app.routers.auth import require_role
from app.services.transmetro_service import (
    PREOPERACIONALES_DB,
    INCIDENTES_DB,
    REGULACION_CCO_MESSAGES,
    BUS_TRACKER_STATE,
    MOCK_ROUTES,
    update_driver_gps,
    update_driver_status
)

router = APIRouter(prefix="/api/conductor", tags=["Portal Conductor Transmetro"])

@router.get("/shift-info")
def get_shift_info(user: dict = Depends(require_role([UserRole.CONDUCTOR, UserRole.ADMIN]))):
    bus_id = user.get("assigned_bus", "TM-3201")
    route_id = user.get("assigned_route", "A3-2")
    route = MOCK_ROUTES.get(route_id, {})
    bus_state = BUS_TRACKER_STATE.get(bus_id, {})

    # Comprobar si ya hizo preoperacional hoy
    preop_today = next((p for p in PREOPERACIONALES_DB if p.bus_id == bus_id), None)

    return {
        "status": "success",
        "conductor": {
            "id": user["id"],
            "name": user["fullname"],
            "bus_id": bus_id,
            "route_id": route_id,
            "route_name": route.get("name", "Ruta Alimentadora"),
            "route_color": route.get("color", "#1D4ED8"),
            "plate": bus_state.get("plate", "WPL-842"),
            "operational_status": bus_state.get("status", "Disponible"),
            "in_shift": bus_state.get("in_shift", False),
            "preoperacional_completado": preop_today is not None,
            "preoperacional_estado": preop_today.estado_aprobacion if preop_today else "Pendiente de realizar"
        },
        "mensajes_cco": [m for m in REGULACION_CCO_MESSAGES if m["bus_id"] == bus_id]
    }

@router.post("/preoperacional", response_model=PreoperacionalRecord)
def submit_preoperacional(
    payload: PreoperacionalCreate,
    user: dict = Depends(require_role([UserRole.CONDUCTOR, UserRole.ADMIN]))
):
    """
    Inspección preoperacional diaria obligatoria antes de iniciar la ruta.
    Valida Frenos, Técnico, Pasajeros, Seguridad y Fluidos.
    """
    # Verificar criterios mínimos de seguridad vial
    es_aprobado = (
        payload.frenos.freno_servicio_ok and
        payload.frenos.freno_estacionamiento_ok and
        payload.frenos.presion_manometros_psi >= 85 and
        payload.tecnico.luces_altas_bajas_ok and
        payload.tecnico.direccionales_freno_ok and
        payload.pasajeros.puertas_neumaticas_ok and
        payload.seguridad.extintor_vigente and
        payload.fluidos.nivel_aceite_motor_ok and
        payload.fluidos.nivel_combustible_porcentaje >= 20
    )

    estado = "Aprobado" if es_aprobado else "Rechazado"

    record = PreoperacionalRecord(
        id=f"PRE-{str(uuid.uuid4())[:6].upper()}",
        conductor_id=user["id"],
        conductor_nombre=user["fullname"],
        bus_id=payload.bus_id,
        route_id=payload.route_id,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        estado_aprobacion=estado,
        detalles=payload
    )

    try:
        from app.database import SessionLocal
        from app.models import Preoperacional
        if SessionLocal:
            db = SessionLocal()
            try:
                db_preop = Preoperacional(
                    id=record.id,
                    conductor_id=record.conductor_id,
                    bus_id=record.bus_id,
                    route_id=record.route_id,
                    odometro_km=payload.odometro_km,
                    freno_servicio_ok=payload.frenos.freno_servicio_ok,
                    freno_estacionamiento_ok=payload.frenos.freno_estacionamiento_ok,
                    presion_manometros_psi=payload.frenos.presion_manometros_psi,
                    neumaticos_labrado_ok=payload.tecnico.neumaticos_labrado_ok,
                    luces_altas_bajas_ok=payload.tecnico.luces_altas_bajas_ok,
                    direccionales_freno_ok=payload.tecnico.direccionales_freno_ok,
                    limpiaparabrisas_espejos_ok=payload.tecnico.limpiaparabrisas_espejos_ok,
                    timbre_parada_ok=payload.pasajeros.timbre_parada_ok,
                    puertas_neumaticas_ok=payload.pasajeros.puertas_neumaticas_ok,
                    validador_tarjetas_ok=payload.pasajeros.validador_tarjetas_ok,
                    barras_sujecion_ok=payload.pasajeros.barras_sujecion_ok,
                    extintor_vigente=payload.seguridad.extintor_vigente,
                    botiquin_primeros_auxilios=payload.seguridad.botiquin_primeros_auxilios,
                    martillos_fragmentadores=payload.seguridad.martillos_fragmentadores,
                    kit_carretera_repuesto=payload.seguridad.kit_carretera_repuesto,
                    nivel_aceite_motor_ok=payload.fluidos.nivel_aceite_motor_ok,
                    nivel_refrigerante_ok=payload.fluidos.nivel_refrigerante_ok,
                    nivel_combustible_porcentaje=payload.fluidos.nivel_combustible_porcentaje,
                    observaciones=payload.observaciones,
                    estado_aprobacion=estado
                )
                db.add(db_preop)
                db.commit()
            finally:
                db.close()
    except Exception as db_err:
        print(f"[BD Neon Preoperacional]: {db_err}")

    PREOPERACIONALES_DB.insert(0, record)

    # Si se aprueba, habilitar bus
    if estado == "Aprobado" and payload.bus_id in BUS_TRACKER_STATE:
        BUS_TRACKER_STATE[payload.bus_id]["status"] = "Disponible"

    return record

@router.post("/incidente", response_model=IncidenteRecord)
def report_incident(
    payload: IncidenteCreate,
    user: dict = Depends(require_role([UserRole.CONDUCTOR, UserRole.ADMIN]))
):
    """
    Reporta un incidente inmediato en vía (Varada, Choque, Bloqueo, etc.)
    notificando instantáneamente al CCO / Despacho.
    """
    record = IncidenteRecord(
        id=f"INC-{str(uuid.uuid4())[:6].upper()}",
        conductor_id=user["id"],
        conductor_nombre=user["fullname"],
        bus_id=payload.bus_id,
        route_id=payload.route_id,
        tipo=payload.tipo,
        prioridad=payload.prioridad,
        ubicacion_referencia=payload.ubicacion_referencia,
        descripcion=payload.descripcion,
        estado="Pendiente",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    try:
        from app.database import SessionLocal
        from app.models import Incidente
        if SessionLocal:
            db = SessionLocal()
            try:
                db_inc = Incidente(
                    id=record.id,
                    conductor_id=record.conductor_id,
                    bus_id=record.bus_id,
                    route_id=record.route_id,
                    tipo=payload.tipo.value if hasattr(payload.tipo, 'value') else str(payload.tipo),
                    prioridad=payload.prioridad.value if hasattr(payload.prioridad, 'value') else str(payload.prioridad),
                    ubicacion_referencia=payload.ubicacion_referencia,
                    descripcion=payload.descripcion,
                    estado="Pendiente"
                )
                db.add(db_inc)
                db.commit()
            finally:
                db.close()
    except Exception as db_err:
        print(f"[BD Neon Incidente]: {db_err}")

    INCIDENTES_DB.insert(0, record)

    # Si es varada o accidente, cambiar estado de bus automáticamente
    if payload.tipo.value in ["Varada Mecánica", "Accidente de Tránsito"]:
        if payload.bus_id in BUS_TRACKER_STATE:
            BUS_TRACKER_STATE[payload.bus_id]["status"] = "Fuera de Servicio"

    return record

@router.post("/telemetry/gps")
def send_driver_gps(
    payload: DriverGPSUpdate,
    user: dict = Depends(require_role([UserRole.CONDUCTOR, UserRole.ADMIN]))
):
    """
    Simulación o envío real de coordenadas GPS emitidas por el smartphone/tablet del conductor.
    Actualiza la ubicación vista en tiempo real por pasajeros y jefe de ruta.
    """
    update_driver_gps(payload)
    return {"status": "success", "message": "Telemetría GPS actualizada"}

@router.post("/status")
def update_operational_status(
    payload: DriverStateChange,
    user: dict = Depends(require_role([UserRole.CONDUCTOR, UserRole.ADMIN]))
):
    """
    Cambio de estado: "Disponible", "En Ruta", "En Pausa / Regulación", "Fuera de Servicio".
    """
    update_driver_status(payload)
    return {
        "status": "success",
        "message": f"Estado actualizado a: {payload.status.value}",
        "in_shift": payload.in_shift
    }
