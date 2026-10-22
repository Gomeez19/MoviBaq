from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.schemas.transmetro import RouteDetail, BusLiveStatus
from app.services.transmetro_service import (
    get_all_routes_summary,
    get_route_full_detail,
    step_bus_simulation,
    MOCK_ROUTES
)

router = APIRouter(prefix="/api/transmetro", tags=["Transmetro Rutas & Monitoreo"])

@router.get("/routes", summary="Obtener lista de todas las rutas y alimentadores")
def get_routes():
    """Retorna el listado de alimentadores y troncales disponibles en Barranquilla."""
    return get_all_routes_summary()

@router.get("/buses/live", response_model=List[BusLiveStatus], summary="Telemetría GPS en vivo de buses por query param")
def get_live_buses_query(route_id: Optional[str] = Query(None)):
    """Retorna la telemetría en vivo para una ruta o para toda la flota."""
    route_key = route_id.upper() if route_id else None
    return step_bus_simulation(route_key)

@router.get("/routes/{route_id}", response_model=RouteDetail, summary="Detalle de ruta, trazado geográfico y paraderos")
def get_route_details(route_id: str):
    """
    Retorna la polyline completa (coordenadas GPS) de la ruta,
    los paraderos oficiales y los buses actualmente en circulación.
    """
    route = get_route_full_detail(route_id.upper())
    if not route:
        raise HTTPException(status_code=404, detail=f"La ruta '{route_id}' no fue encontrada.")
    return route

@router.get("/routes/{route_id}/buses", response_model=List[BusLiveStatus], summary="Telemetría GPS en vivo de buses")
def get_live_buses(route_id: str):
    """
    Simula la telemetría periódica GPS enviada por los buses alimentadores en tránsito.
    Actualiza la ubicación en la ruta, la velocidad, el ETA y la distancia.
    """
    route_key = route_id.upper()
    if route_key not in MOCK_ROUTES:
        raise HTTPException(status_code=404, detail=f"Ruta '{route_id}' no encontrada.")
    
    return step_bus_simulation(route_key)

@router.get("/quick-eta", summary="Consulta rápida de ETA para una parada")
def get_quick_eta(
    route_id: str = Query(..., description="Código de ruta ej: A3-2"),
    stop_id: Optional[str] = Query(None, description="ID del paradero")
):
    """Calcula el tiempo estimado para el bus más cercano a la parada solicitada."""
    route_key = route_id.upper()
    if route_key not in MOCK_ROUTES:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    
    buses = step_bus_simulation(route_key)
    if not buses:
        return {"status": "no_buses", "eta_minutes": None}

    closest_bus = min(buses, key=lambda b: b.eta_minutes)
    return {
        "status": "success",
        "route_id": route_key,
        "closest_bus": closest_bus.bus_id,
        "plate": closest_bus.plate,
        "eta_minutes": closest_bus.eta_minutes,
        "distance_meters": closest_bus.distance_meters,
        "bus_status": closest_bus.status,
        "occupancy": closest_bus.occupancy_percent
    }
