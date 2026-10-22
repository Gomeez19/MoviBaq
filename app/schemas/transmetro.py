from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class UserRole(str, Enum):
    PASAJERO = "pasajero"
    CONDUCTOR = "conductor"
    JEFE_RUTA = "jefe_ruta"
    ADMIN = "admin"

class BusOperationalStatus(str, Enum):
    DISPONIBLE = "Disponible"
    EN_RUTA = "En Ruta"
    EN_PAUSA = "En Pausa / Regulación"
    FUERA_SERVICIO = "Fuera de Servicio"

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class UserRegister(BaseModel):
    fullname: str
    email: EmailStr
    password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)
    role: UserRole = UserRole.PASAJERO

class UserResponse(BaseModel):
    id: str
    fullname: str
    email: str
    role: UserRole

# ----------------- PREOPERACIONAL SCHEMAS -----------------
class PreoperacionalFrenos(BaseModel):
    freno_servicio_ok: bool = True
    freno_estacionamiento_ok: bool = True
    presion_manometros_psi: int = Field(default=110, ge=60, le=140)

class PreoperacionalTecnico(BaseModel):
    neumaticos_labrado_ok: bool = True
    luces_altas_bajas_ok: bool = True
    direccionales_freno_ok: bool = True
    limpiaparabrisas_espejos_ok: bool = True

class PreoperacionalPasajeros(BaseModel):
    timbre_parada_ok: bool = True
    puertas_neumaticas_ok: bool = True
    validador_tarjetas_ok: bool = True
    barras_sujecion_ok: bool = True

class PreoperacionalSeguridad(BaseModel):
    extintor_vigente: bool = True
    botiquin_primeros_auxilios: bool = True
    martillos_fragmentadores: bool = True
    kit_carretera_repuesto: bool = True

class PreoperacionalFluidos(BaseModel):
    nivel_aceite_motor_ok: bool = True
    nivel_refrigerante_ok: bool = True
    nivel_combustible_porcentaje: int = Field(default=85, ge=0, le=100)

class PreoperacionalCreate(BaseModel):
    bus_id: str
    route_id: str
    odometro_km: int = 124500
    frenos: PreoperacionalFrenos
    tecnico: PreoperacionalTecnico
    pasajeros: PreoperacionalPasajeros
    seguridad: PreoperacionalSeguridad
    fluidos: PreoperacionalFluidos
    observaciones: Optional[str] = None

class PreoperacionalRecord(BaseModel):
    id: str
    conductor_id: str
    conductor_nombre: str
    bus_id: str
    route_id: str
    created_at: str
    estado_aprobacion: str = "Aprobado" # "Aprobado", "Rechazado", "Pendiente"
    detalles: PreoperacionalCreate

# ----------------- INCIDENTES SCHEMAS -----------------
class IncidenteTipo(str, Enum):
    VARADA_MECANICA = "Varada Mecánica"
    ACCIDENTE_TRANSITO = "Accidente de Tránsito"
    BLOQUEO_CONGESTION = "Bloqueo en Vía / Congestión"
    EMERGENCIA_MEDICA = "Emergencia Médica a Bordo"
    ORDEN_PUBLICO = "Alteración del Orden Público"

class IncidentePrioridad(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    CRITICA = "Crítica"

class IncidenteCreate(BaseModel):
    tipo: IncidenteTipo
    prioridad: IncidentePrioridad = IncidentePrioridad.MEDIA
    bus_id: str
    route_id: str
    ubicacion_referencia: str
    descripcion: str
    lat: Optional[float] = None
    lng: Optional[float] = None

class IncidenteRecord(BaseModel):
    id: str
    conductor_id: str
    conductor_nombre: str
    bus_id: str
    route_id: str
    tipo: IncidenteTipo
    prioridad: IncidentePrioridad
    ubicacion_referencia: str
    descripcion: str
    estado: str = "Pendiente" # "Pendiente", "En Atención", "Resuelto"
    created_at: str
    resolucion_notas: Optional[str] = None

# ----------------- TELEMETRÍA Y GPS CONDUCTOR -----------------
class DriverGPSUpdate(BaseModel):
    bus_id: str
    route_id: str
    lat: float
    lng: float
    speed_kmh: float = 30.0
    heading: float = 0.0
    occupancy_percent: int = 50

class DriverStateChange(BaseModel):
    bus_id: str
    route_id: str
    status: BusOperationalStatus
    in_shift: bool = True

# ----------------- RUTAS Y MAPAS -----------------
class BusStop(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    order: int

class BusLiveStatus(BaseModel):
    bus_id: str
    plate: str
    current_lat: float
    current_lng: float
    speed_kmh: float
    next_stop: str
    eta_minutes: int
    distance_meters: int
    status: str
    occupancy_percent: int
    heading: float
    driver_name: Optional[str] = "Conductor Operativo"

class RouteDetail(BaseModel):
    id: str
    code: str
    name: str
    type: str
    color: str
    description: str
    frequency_minutes: int
    schedule: str
    path: List[List[float]]
    stops: List[BusStop]
    buses: List[BusLiveStatus]

# ----------------- ADMIN FLEET SCHEMAS -----------------
class FleetVehicleCreate(BaseModel):
    bus_id: str
    plate: str
    route_id: str
    capacity: int = 50
    model_year: int = 2022
    chassis: str = "Scania K250UB / Busscar"
    last_maintenance: str = "2026-09-15"
