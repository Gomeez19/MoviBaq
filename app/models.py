import os
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Text, ForeignKey, TIMESTAMP, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class Ruta(Base):
    __tablename__ = "rutas"

    id = Column(String(20), primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    type = Column(String(50), default="Alimentador")
    color = Column(String(20), default="#0252CD")
    description = Column(Text, nullable=True)
    frequency_minutes = Column(Integer, default=7)
    schedule = Column(String(100), default="05:00 AM - 10:30 PM")
    path_geojson = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    paraderos = relationship("Paradero", back_populates="ruta", cascade="all, delete-orphan")


class Paradero(Base):
    __tablename__ = "paraderos"

    id = Column(String(50), primary_key=True)
    route_id = Column(String(20), ForeignKey("rutas.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    lat = Column(Numeric(10, 7), nullable=False)
    lng = Column(Numeric(10, 7), nullable=False)
    stop_order = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    ruta = relationship("Ruta", back_populates="paraderos")


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    bus_id = Column(String(30), primary_key=True)
    plate = Column(String(15), unique=True, nullable=False)
    current_route_id = Column(String(20), ForeignKey("rutas.id", ondelete="SET NULL"), nullable=True)
    operational_status = Column(String(50), default="Disponible")
    capacity = Column(Integer, default=50)
    model_year = Column(Integer, default=2022)
    chassis = Column(String(100), default="Scania K250UB / Busscar")
    last_maintenance = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(String(50), primary_key=True)
    fullname = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="pasajero")
    assigned_bus_id = Column(String(30), ForeignKey("vehiculos.bus_id", ondelete="SET NULL"), nullable=True)
    assigned_route_id = Column(String(20), ForeignKey("rutas.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class TelemetriaEnVivo(Base):
    __tablename__ = "telemetria_en_vivo"

    bus_id = Column(String(30), ForeignKey("vehiculos.bus_id", ondelete="CASCADE"), primary_key=True)
    route_id = Column(String(20), ForeignKey("rutas.id", ondelete="CASCADE"), nullable=True)
    driver_id = Column(String(50), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    lat = Column(Numeric(10, 7), nullable=False)
    lng = Column(Numeric(10, 7), nullable=False)
    speed_kmh = Column(Numeric(5, 2), default=0.0)
    heading = Column(Numeric(5, 2), default=0.0)
    eta_minutes = Column(Integer, default=5)
    distance_meters = Column(Integer, default=1200)
    next_stop_name = Column(String(150), nullable=True)
    occupancy_percent = Column(Integer, default=50)
    last_ping = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class Preoperacional(Base):
    __tablename__ = "preoperacionales"

    id = Column(String(50), primary_key=True)
    conductor_id = Column(String(50), ForeignKey("usuarios.id"), nullable=False)
    bus_id = Column(String(30), ForeignKey("vehiculos.bus_id"), nullable=False)
    route_id = Column(String(20), ForeignKey("rutas.id"), nullable=False)
    odometro_km = Column(Integer, nullable=False)

    freno_servicio_ok = Column(Boolean, default=True)
    freno_estacionamiento_ok = Column(Boolean, default=True)
    presion_manometros_psi = Column(Integer, default=110)

    neumaticos_labrado_ok = Column(Boolean, default=True)
    luces_altas_bajas_ok = Column(Boolean, default=True)
    direccionales_freno_ok = Column(Boolean, default=True)
    limpiaparabrisas_espejos_ok = Column(Boolean, default=True)

    timbre_parada_ok = Column(Boolean, default=True)
    puertas_neumaticas_ok = Column(Boolean, default=True)
    validador_tarjetas_ok = Column(Boolean, default=True)
    barras_sujecion_ok = Column(Boolean, default=True)

    extintor_vigente = Column(Boolean, default=True)
    botiquin_primeros_auxilios = Column(Boolean, default=True)
    martillos_fragmentadores = Column(Boolean, default=True)
    kit_carretera_repuesto = Column(Boolean, default=True)

    nivel_aceite_motor_ok = Column(Boolean, default=True)
    nivel_refrigerante_ok = Column(Boolean, default=True)
    nivel_combustible_porcentaje = Column(Integer, default=90)

    observaciones = Column(Text, nullable=True)
    estado_aprobacion = Column(String(50), default="Aprobado")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Incidente(Base):
    __tablename__ = "incidentes"

    id = Column(String(50), primary_key=True)
    conductor_id = Column(String(50), ForeignKey("usuarios.id"), nullable=False)
    bus_id = Column(String(30), ForeignKey("vehiculos.bus_id"), nullable=False)
    route_id = Column(String(20), ForeignKey("rutas.id"), nullable=False)
    tipo = Column(String(100), nullable=False)
    prioridad = Column(String(20), default="Media")
    ubicacion_referencia = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=False)
    estado = Column(String(50), default="Pendiente")
    resolucion_notas = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)


class MensajeRegulacion(Base):
    __tablename__ = "mensajes_regulacion"

    id = Column(String(50), primary_key=True)
    jefe_id = Column(String(50), ForeignKey("usuarios.id"), nullable=True)
    bus_id = Column(String(30), ForeignKey("vehiculos.bus_id"), nullable=False)
    mensaje = Column(Text, nullable=False)
    read_by_driver = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
