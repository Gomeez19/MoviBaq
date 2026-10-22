-- ==============================================================================
-- PROYECTO: MoviBAQ / Transmetro Barranquilla
-- MOTOR: PostgreSQL (Neon Serverless Postgres)
-- DESCRIPCIÓN: Esquema relacional optimizado para RBAC, Telemetría GPS,
--              Inspección Preoperacional e Incidentes en Vía.
-- ==============================================================================

-- 1. Habilitar extensión para generación de identificadores UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. ENUMS PERSONALIZADOS
DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('pasajero', 'conductor', 'jefe_ruta', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE bus_status_enum AS ENUM ('Disponible', 'En Ruta', 'En Pausa / Regulación', 'Fuera de Servicio');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE incident_type_enum AS ENUM (
        'Varada Mecánica',
        'Accidente de Tránsito',
        'Bloqueo en Vía / Congestión',
        'Emergencia Médica a Bordo',
        'Alteración del Orden Público'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE incident_priority_enum AS ENUM ('Baja', 'Media', 'Alta', 'Crítica');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE incident_status_enum AS ENUM ('Pendiente', 'En Atención', 'Resuelto');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE preop_approval_enum AS ENUM ('Aprobado', 'Rechazado', 'Pendiente');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ------------------------------------------------------------------------------
-- TABLA 1: RUTAS (Alimentadores y Troncales de Barranquilla)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rutas (
    id VARCHAR(20) PRIMARY KEY, -- Ej: 'A3-2', 'U30'
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'Alimentador', -- 'Alimentador', 'Troncal'
    color VARCHAR(20) NOT NULL DEFAULT '#1D4ED8',
    description TEXT,
    frequency_minutes INT NOT NULL DEFAULT 7,
    schedule VARCHAR(100) NOT NULL DEFAULT '05:00 AM - 10:30 PM',
    path_geojson JSONB NOT NULL, -- Coordenadas [[lat, lng], [lat, lng], ...]
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- TABLA 2: PARADEROS (Stops oficiales a lo largo del trazado)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS paraderos (
    id VARCHAR(50) PRIMARY KEY,
    route_id VARCHAR(20) NOT NULL REFERENCES rutas(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    lat NUMERIC(10, 7) NOT NULL,
    lng NUMERIC(10, 7) NOT NULL,
    stop_order INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_route_stop_order UNIQUE (route_id, stop_order)
);

-- ------------------------------------------------------------------------------
-- TABLA 3: VEHÍCULOS / FLOTA DE BUSES (Padrones Transmetro)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehiculos (
    bus_id VARCHAR(30) PRIMARY KEY, -- Ej: 'TM-3201'
    plate VARCHAR(15) NOT NULL UNIQUE, -- Ej: 'WPL-842'
    current_route_id VARCHAR(20) REFERENCES rutas(id) ON DELETE SET NULL,
    operational_status bus_status_enum DEFAULT 'Disponible',
    capacity INT DEFAULT 50,
    model_year INT DEFAULT 2022,
    chassis VARCHAR(100) DEFAULT 'Scania K250UB / Busscar',
    last_maintenance DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- TABLA 4: USUARIOS (RBAC: Pasajero, Conductor, Jefe de Ruta, Admin)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    fullname VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_role_enum NOT NULL DEFAULT 'pasajero',
    assigned_bus_id VARCHAR(30) REFERENCES vehiculos(bus_id) ON DELETE SET NULL,
    assigned_route_id VARCHAR(20) REFERENCES rutas(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- TABLA 5: TELEMETRÍA GPS EN VIVO (Última posición y rumbo)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetria_en_vivo (
    bus_id VARCHAR(30) PRIMARY KEY REFERENCES vehiculos(bus_id) ON DELETE CASCADE,
    route_id VARCHAR(20) REFERENCES rutas(id) ON DELETE CASCADE,
    driver_id VARCHAR(50) REFERENCES usuarios(id) ON DELETE SET NULL,
    lat NUMERIC(10, 7) NOT NULL,
    lng NUMERIC(10, 7) NOT NULL,
    speed_kmh NUMERIC(5, 2) DEFAULT 0.0,
    heading NUMERIC(5, 2) DEFAULT 0.0,
    eta_minutes INT DEFAULT 5,
    distance_meters INT DEFAULT 1200,
    next_stop_name VARCHAR(150),
    occupancy_percent INT DEFAULT 50,
    last_ping TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- TABLA 6: INSPECCIONES PREOPERACIONALES OBLIGATORIAS (Conductores)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS preoperacionales (
    id VARCHAR(50) PRIMARY KEY DEFAULT ('PRE-' || UPPER(SUBSTRING(uuid_generate_v4()::text, 1, 8))),
    conductor_id VARCHAR(50) NOT NULL REFERENCES usuarios(id),
    bus_id VARCHAR(30) NOT NULL REFERENCES vehiculos(bus_id),
    route_id VARCHAR(20) NOT NULL REFERENCES rutas(id),
    odometro_km INT NOT NULL,
    
    -- Frenos
    freno_servicio_ok BOOLEAN NOT NULL DEFAULT TRUE,
    freno_estacionamiento_ok BOOLEAN NOT NULL DEFAULT TRUE,
    presion_manometros_psi INT NOT NULL DEFAULT 110,
    
    -- Técnico
    neumaticos_labrado_ok BOOLEAN NOT NULL DEFAULT TRUE,
    luces_altas_bajas_ok BOOLEAN NOT NULL DEFAULT TRUE,
    direccionales_freno_ok BOOLEAN NOT NULL DEFAULT TRUE,
    limpiaparabrisas_espejos_ok BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Pasajeros
    timbre_parada_ok BOOLEAN NOT NULL DEFAULT TRUE,
    puertas_neumaticas_ok BOOLEAN NOT NULL DEFAULT TRUE,
    validador_tarjetas_ok BOOLEAN NOT NULL DEFAULT TRUE,
    barras_sujecion_ok BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Seguridad
    extintor_vigente BOOLEAN NOT NULL DEFAULT TRUE,
    botiquin_primeros_auxilios BOOLEAN NOT NULL DEFAULT TRUE,
    martillos_fragmentadores BOOLEAN NOT NULL DEFAULT TRUE,
    kit_carretera_repuesto BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Fluidos
    nivel_aceite_motor_ok BOOLEAN NOT NULL DEFAULT TRUE,
    nivel_refrigerante_ok BOOLEAN NOT NULL DEFAULT TRUE,
    nivel_combustible_porcentaje INT NOT NULL DEFAULT 90,
    
    observaciones TEXT,
    estado_aprobacion preop_approval_enum DEFAULT 'Aprobado',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- TABLA 7: INCIDENTES EN VÍA (Reportados por Conductores al CCO)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidentes (
    id VARCHAR(50) PRIMARY KEY DEFAULT ('INC-' || UPPER(SUBSTRING(uuid_generate_v4()::text, 1, 8))),
    conductor_id VARCHAR(50) NOT NULL REFERENCES usuarios(id),
    bus_id VARCHAR(30) NOT NULL REFERENCES vehiculos(bus_id),
    route_id VARCHAR(20) NOT NULL REFERENCES rutas(id),
    tipo incident_type_enum NOT NULL,
    prioridad incident_priority_enum DEFAULT 'Media',
    ubicacion_referencia VARCHAR(255) NOT NULL,
    descripcion TEXT NOT NULL,
    estado incident_status_enum DEFAULT 'Pendiente',
    resolucion_notas TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- ------------------------------------------------------------------------------
-- TABLA 8: MENSAJES DE REGULACIÓN DE DESPACHO (CCO -> Conductor)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensajes_regulacion (
    id VARCHAR(50) PRIMARY KEY DEFAULT ('MSG-' || UPPER(SUBSTRING(uuid_generate_v4()::text, 1, 8))),
    jefe_id VARCHAR(50) REFERENCES usuarios(id),
    bus_id VARCHAR(30) NOT NULL REFERENCES vehiculos(bus_id),
    mensaje TEXT NOT NULL,
    read_by_driver BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices de alto rendimiento para consultas en tiempo real
CREATE INDEX IF NOT EXISTS idx_telemetria_route ON telemetria_en_vivo(route_id);
CREATE INDEX IF NOT EXISTS idx_paraderos_route ON paraderos(route_id, stop_order);
CREATE INDEX IF NOT EXISTS idx_incidentes_estado ON incidentes(estado);
CREATE INDEX IF NOT EXISTS idx_preoperacionales_fecha ON preoperacionales(created_at DESC);

-- ==============================================================================
-- POBLAMIENTO INICIAL DE DATOS REALISTAS (SEEDS PARA NEON POSTGRESQL)
-- ==============================================================================

-- 1. RUTAS OFICIALES TRANSMETRO (BARRANQUILLA Y SOLEDAD)
INSERT INTO rutas (id, code, name, type, color, description, frequency_minutes, schedule, path_geojson)
VALUES 
('A8-1', 'A8-1', 'Paraíso - Vía 40', 'Alimentador', '#0284C7', 'Conecta la Estación de Retorno Joe Arroyo con los barrios Paraíso, Villa Andalucía y el corredor industrial Vía 40.', 6, '05:00 AM - 10:30 PM', '[[10.9982, -74.8105], [11.0025, -74.8142], [11.0068, -74.8180], [11.0090, -74.8198], [11.0125, -74.8235], [11.0150, -74.8190], [11.0178, -74.8150], [11.0205, -74.8100], [11.0225, -74.8050], [11.0180, -74.8015], [11.0145, -74.8065], [11.0110, -74.8120], [11.0068, -74.8180], [10.9982, -74.8105]]'::jsonb),
('A8-2', 'A8-2', 'Vía 40 - Zoológico', 'Alimentador', '#F59E0B', 'Circuito desde Estación Joe Arroyo por Calle 79 hacia Vía 40, Zoológico de Barranquilla y retorno por Calle 76.', 8, '05:15 AM - 10:00 PM', '[[10.9982, -74.8105], [11.0020, -74.8080], [11.0050, -74.8060], [11.0080, -74.8035], [11.0110, -74.8000], [11.0150, -74.7960], [11.0185, -74.7925], [11.0160, -74.7895], [11.0130, -74.7940], [11.0090, -74.7990], [11.0050, -74.8040], [11.0015, -74.8080], [10.9982, -74.8105]]'::jsonb),
('A9-3', 'A9-3', 'Buenavista - Villa Country', 'Alimentador', '#8B5CF6', 'Conexión directa entre la Estación Joe Arroyo, el distrito comercial Villa Country y el Centro Comercial Buenavista sobre la Cra 51B.', 5, '05:00 AM - 10:30 PM', '[[10.9982, -74.8105], [11.0010, -74.8140], [11.0055, -74.8185], [11.0115, -74.8250], [11.0180, -74.8320], [11.0205, -74.8360], [11.0220, -74.8395], [11.0200, -74.8370], [11.0160, -74.8325], [11.0120, -74.8275], [11.0075, -74.8220], [11.0040, -74.8175], [11.0010, -74.8140], [10.9982, -74.8105]]'::jsonb),
('A7-3', 'A7-3', 'Carrera 38', 'Alimentador', '#10B981', 'Cruza longitudinalmente el centro-norte por la Carrera 38 conectando Estación Joe Arroyo con la troncal Murillo en Estación La Arenosa.', 7, '05:00 AM - 10:30 PM', '[[10.9982, -74.8105], [10.9940, -74.8120], [10.9905, -74.8145], [10.9870, -74.8175], [10.9830, -74.8130], [10.9785, -74.8080], [10.9730, -74.8020], [10.9675, -74.7960], [10.9640, -74.7920], [10.9680, -74.7950], [10.9750, -74.8030], [10.9880, -74.8160], [10.9982, -74.8105]]'::jsonb),
('A7-4', 'A7-4', 'Los Andes - Betania', 'Alimentador', '#EF4444', 'Atiende los sectores tradicionales de Los Andes, Betania y Las Mercedes conectando con la Estación Joe Arroyo y el C.C. Único.', 8, '05:00 AM - 10:00 PM', '[[10.9982, -74.8105], [10.9940, -74.8135], [10.9910, -74.8170], [10.9880, -74.8205], [10.9840, -74.8180], [10.9780, -74.8120], [10.9740, -74.8080], [10.9690, -74.8020], [10.9645, -74.7970], [10.9710, -74.8040], [10.9820, -74.8140], [10.9930, -74.8110], [10.9982, -74.8105]]'::jsonb),
('A1-2', 'A1-2', 'Carrera Ocho', 'Alimentador', '#D97706', 'Recorre el eje vial de la Carrera 8 conectando barrios Las Palmas, El Campito, La Alboraya con la Estación Troncal La Ocho.', 6, '05:00 AM - 10:30 PM', '[[10.9490, -74.7910], [10.9450, -74.7865], [10.9495, -74.7915], [10.9540, -74.7960], [10.9585, -74.8005], [10.9620, -74.8040], [10.9660, -74.8085], [10.9695, -74.8120], [10.9620, -74.8040], [10.9585, -74.8005], [10.9530, -74.7950], [10.9490, -74.7910]]'::jsonb),
('A3-1', 'A3-1', 'Villa Katanga - Plaza del Sol', 'Alimentador', '#059669', 'Comunica la Estación Troncal Pedro Ramayá con la Calle 30, el Centro Comercial Plaza del Sol y Villa Katanga en Soledad.', 7, '05:00 AM - 10:30 PM', '[[10.9380, -74.7930], [10.9335, -74.7890], [10.9290, -74.7850], [10.9250, -74.7820], [10.9210, -74.7760], [10.9165, -74.7715], [10.9190, -74.7670], [10.9230, -74.7720], [10.9280, -74.7790], [10.9340, -74.7880], [10.9380, -74.7930]]'::jsonb),
('A2-1', 'A2-1', 'Hipódromo - Metrocentro', 'Alimentador', '#EA580C', 'Conecta la Estación Joaquín Barrios Polo (Metrocentro) por Av. Las Torres y Cll 30 con los barrios Hipódromo e ITIDA en Soledad.', 6, '05:00 AM - 10:30 PM', '[[10.9490, -74.8020], [10.9460, -74.8055], [10.9410, -74.8020], [10.9350, -74.7970], [10.9300, -74.7900], [10.9320, -74.7800], [10.9360, -74.7730], [10.9410, -74.7710], [10.9440, -74.7750], [10.9380, -74.7810], [10.9330, -74.7920], [10.9490, -74.8020]]'::jsonb),
('A3-2', 'A3-2', 'Soledad - Hipódromo', 'Alimentador', '#D946EF', 'Conexión directa desde Portal de Soledad por Calle 30 hacia el barrio Hipódromo y centro de Soledad.', 7, '05:00 AM - 10:30 PM', '[[10.9254, -74.7788], [10.9280, -74.7750], [10.9315, -74.7720], [10.9360, -74.7695], [10.9412, -74.7725], [10.9430, -74.7760], [10.9385, -74.7810], [10.9320, -74.7800], [10.9254, -74.7788]]'::jsonb),
('A5-3', 'A5-3', 'La Central - Soledad 2000', 'Alimentador', '#06B6D4', 'Recorrido de alta demanda conectando Portal de Soledad con Soledad 2000, Manuela Beltrán y La Central.', 8, '05:15 AM - 10:00 PM', '[[10.9254, -74.7788], [10.9210, -74.7830], [10.9160, -74.7875], [10.9110, -74.7920], [10.9080, -74.7960], [10.9125, -74.7990], [10.9180, -74.7930], [10.9220, -74.7850], [10.9254, -74.7788]]'::jsonb)
ON CONFLICT (id) DO UPDATE SET 
    name = EXCLUDED.name,
    color = EXCLUDED.color,
    description = EXCLUDED.description,
    frequency_minutes = EXCLUDED.frequency_minutes,
    path_geojson = EXCLUDED.path_geojson;

-- 2. PARADEROS OFICIALES REALES
INSERT INTO paraderos (id, route_id, name, lat, lng, stop_order)
VALUES
-- Paraderos A8-1 Paraíso
('a81_s1', 'A8-1', 'Estación Joe Arroyo (Plataforma)', 10.9982000, -74.8105000, 1),
('a81_s2', 'A8-1', 'Cra 46 con Cll 76 (Lado Norte)', 11.0025000, -74.8142000, 2),
('a81_s3', 'A8-1', 'Cra 46 con Cll 82', 11.0068000, -74.8180000, 3),
('a81_s4', 'A8-1', 'Cll 84 con Cra 51B (Macmondongo)', 11.0125000, -74.8235000, 4),
('a81_s5', 'A8-1', 'Cra 65 con Cll 86 (Villa Andalucía)', 11.0178000, -74.8150000, 5),
('a81_s6', 'A8-1', 'Vía 40 con Cll 85 (Barrio Paraíso)', 11.0225000, -74.8050000, 6),
('a81_s7', 'A8-1', 'Vía 40 con Cll 80 (Sector Industrial)', 11.0180000, -74.8015000, 7),
('a81_s8', 'A8-1', 'Cll 82 con Cra 55 (Retorno)', 11.0110000, -74.8120000, 8),

-- Paraderos A8-2 Vía 40 - Zoológico
('a82_s1', 'A8-2', 'Estación Joe Arroyo (Plataforma)', 10.9982000, -74.8105000, 1),
('a82_s2', 'A8-2', 'Cll 79 con Cra 51B', 11.0065000, -74.8045000, 2),
('a82_s3', 'A8-2', 'Cll 79 con Cra 57 (Sector Country)', 11.0110000, -74.8000000, 3),
('a82_s4', 'A8-2', 'Cll 77 con Vía 40 (Outlet Continental)', 11.0185000, -74.7925000, 4),
('a82_s5', 'A8-2', 'Cll 76 con Vía 40 (Kia Motors)', 11.0160000, -74.7895000, 5),
('a82_s6', 'A8-2', 'Cll 76 con Cra 68 (Zoológico de Barranquilla)', 11.0130000, -74.7940000, 6),
('a82_s7', 'A8-2', 'Cll 76 con Cra 57 (Combarranquilla)', 11.0090000, -74.7990000, 7),
('a82_s8', 'A8-2', 'Cll 76 con Cra 53 (Parque Parrish)', 11.0050000, -74.8040000, 8),

-- Paraderos A9-3 Buenavista - Villa Country
('a93_s1', 'A9-3', 'Estación Joe Arroyo (Plataforma)', 10.9982000, -74.8105000, 1),
('a93_s2', 'A9-3', 'Cra 54 con Cll 79 (Sector Villa Country)', 11.0055000, -74.8185000, 2),
('a93_s3', 'A9-3', 'Cra 53 con Cll 94', 11.0180000, -74.8320000, 3),
('a93_s4', 'A9-3', 'Cll 98 con Cra 52 (C.C. Buenavista)', 11.0220000, -74.8395000, 4),
('a93_s5', 'A9-3', 'Cra 51B con Cll 96A', 11.0200000, -74.8370000, 5),
('a93_s6', 'A9-3', 'Cra 51B con Cll 87 (Colegio Cervantes)', 11.0120000, -74.8275000, 6),
('a93_s7', 'A9-3', 'Cra 51B con Cll 82', 11.0075000, -74.8220000, 7),
('a93_s8', 'A9-3', 'Cra 51B con Cll 79 (Hotel El Prado)', 11.0040000, -74.8175000, 8),

-- Paraderos A7-3 Carrera 38
('a73_s1', 'A7-3', 'Estación Joe Arroyo (Plataforma)', 10.9982000, -74.8105000, 1),
('a73_s2', 'A7-3', 'Cll 76 con Cra 43 (Clínica La Merced)', 10.9905000, -74.8145000, 2),
('a73_s3', 'A7-3', 'Cll 76 con Cra 38 (Universidad Metropolitana)', 10.9870000, -74.8175000, 3),
('a73_s4', 'A7-3', 'Cra 38 con Cll 72 (C.C. Americano)', 10.9830000, -74.8130000, 4),
('a73_s5', 'A7-3', 'Cra 38 con Cll 54 (Éxito San Francisco)', 10.9730000, -74.8020000, 5),
('a73_s6', 'A7-3', 'Av. Murillo (Conexión Estación La Arenosa)', 10.9640000, -74.7920000, 6),
('a73_s7', 'A7-3', 'Cra 43 con Cll 54 (Retorno Norte)', 10.9680000, -74.7950000, 7),

-- Paraderos A7-4 Los Andes - Betania
('a74_s1', 'A7-4', 'Estación Joe Arroyo (Plataforma)', 10.9982000, -74.8105000, 1),
('a74_s2', 'A7-4', 'Cll 76 con Cra 39 (C.C. Único)', 10.9910000, -74.8170000, 2),
('a74_s3', 'A7-4', 'Cll 76 con Cra 38A (Colegio Betania)', 10.9880000, -74.8205000, 3),
('a74_s4', 'A7-4', 'Cll 79A con Cra 33 (Parque Las Mercedes)', 10.9840000, -74.8180000, 4),
('a74_s5', 'A7-4', 'Cra 27 con Cll 61 (Parque Los Andes)', 10.9740000, -74.8080000, 5),
('a74_s6', 'A7-4', 'Cra 24 con Cll 54 (Seguro Los Andes)', 10.9690000, -74.8020000, 6),
('a74_s7', 'A7-4', 'Cra 27 con Cll 45 (Éxito Murillo)', 10.9645000, -74.7970000, 7),
('a74_s8', 'A7-4', 'Cll 79 con Cra 42F (Litoral)', 10.9930000, -74.8110000, 8),

-- Paraderos A1-2 Carrera Ocho
('a12_s1', 'A1-2', 'Cra 8 con Cll 31 (Punto Sur)', 10.9490000, -74.7910000, 1),
('a12_s2', 'A1-2', 'Cll 30 con Cra 4B (C.C. Panorama)', 10.9450000, -74.7865000, 2),
('a12_s3', 'A1-2', 'Cra 8 con Cll 34 (Torres de Las Palmas)', 10.9495000, -74.7915000, 3),
('a12_s4', 'A1-2', 'Cra 8 con Cll 45 (Conexión Estación La Ocho)', 10.9585000, -74.8005000, 4),
('a12_s5', 'A1-2', 'Cra 8 con Cll 49', 10.9620000, -74.8040000, 5),
('a12_s6', 'A1-2', 'Cll 53 con Cra 8G (El Santuario)', 10.9660000, -74.8085000, 6),
('a12_s7', 'A1-2', 'Cll 56 con Cra 9D (Retorno)', 10.9695000, -74.8120000, 7),

-- Paraderos A3-1 Villa Katanga - Plaza del Sol
('a31_s1', 'A3-1', 'Estación Pedro Ramayá (Plataforma)', 10.9380000, -74.7930000, 1),
('a31_s2', 'A3-1', 'Cra 24 con Cll 55B', 10.9335000, -74.7890000, 2),
('a31_s3', 'A3-1', 'Cra 24 con Cll 48', 10.9290000, -74.7850000, 3),
('a31_s4', 'A3-1', 'Cra 30 con Cll 40', 10.9210000, -74.7760000, 4),
('a31_s5', 'A3-1', 'Cra 30 con Cll 30 (C.C. Plaza del Sol)', 10.9165000, -74.7715000, 5),
('a31_s6', 'A3-1', 'Cll 35 con Cra 30 (Villa Katanga)', 10.9190000, -74.7670000, 6),
('a31_s7', 'A3-1', 'Cll 45 con Cra 27A', 10.9280000, -74.7790000, 7),

-- Paraderos A2-1 Hipódromo - Metrocentro
('a21_s1', 'A2-1', 'Estación Joaquín Barrios Polo (Metrocentro)', 10.9490000, -74.8020000, 1),
('a21_s2', 'A2-1', 'Cll 45D con Cra 1 (Metrocentro)', 10.9460000, -74.8055000, 2),
('a21_s3', 'A2-1', 'Av. Las Torres con Cll 48', 10.9380000, -74.8000000, 3),
('a21_s4', 'A2-1', 'Cll 30 (Colegio ITIDA)', 10.9320000, -74.7800000, 4),
('a21_s5', 'A2-1', 'Cra 30 con Cll 30 (SAO Hipódromo)', 10.9360000, -74.7730000, 5),
('a21_s6', 'A2-1', 'Cll 18 con Cra 27 (Sector Hipódromo)', 10.9410000, -74.7710000, 6),
('a21_s7', 'A2-1', 'Cll 30 (Colegio INEM / Entrada Tucán)', 10.9380000, -74.7810000, 7),

-- Paraderos A3-2 Soledad - Hipódromo
('a32_s1', 'A3-2', 'Portal de Soledad (Cabecera)', 10.9254000, -74.7788000, 1),
('a32_s2', 'A3-2', 'Calle 30 con Cra 19 (Olímpica)', 10.9315000, -74.7720000, 2),
('a32_s3', 'A3-2', 'Parque Hipódromo', 10.9412000, -74.7725000, 3),
('a32_s4', 'A3-2', 'Calle 24 Soledad Centro', 10.9430000, -74.7760000, 4),
('a32_s5', 'A3-2', 'Cra 15 Retorno Portal', 10.9385000, -74.7810000, 5),

-- Paraderos A5-3 La Central - Soledad 2000
('a53_s1', 'A5-3', 'Portal de Soledad (Cabecera)', 10.9254000, -74.7788000, 1),
('a53_s2', 'A5-3', 'Av. Murillo con Cra 14', 10.9210000, -74.7830000, 2),
('a53_s3', 'A5-3', 'Entrada Soledad 2000', 10.9160000, -74.7875000, 3),
('a53_s4', 'A5-3', 'Sector La Central Plaza', 10.9080000, -74.7960000, 4),
('a53_s5', 'A5-3', 'Retorno Manuela Beltrán', 10.9180000, -74.7930000, 5)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    lat = EXCLUDED.lat,
    lng = EXCLUDED.lng,
    stop_order = EXCLUDED.stop_order;

-- 3. VEHÍCULOS / FLOTA TRANSMETRO
INSERT INTO vehiculos (bus_id, plate, current_route_id, operational_status, capacity, model_year, chassis, last_maintenance)
VALUES
('TM-8101', 'WPL-612', 'A8-1', 'En Ruta', 50, 2023, 'Scania K250UB Euro VI / Busscar', '2026-10-15'),
('TM-8105', 'WPL-735', 'A8-1', 'En Ruta', 50, 2023, 'Scania K250UB Euro VI / Busscar', '2026-10-12'),
('TM-8201', 'WPL-418', 'A8-2', 'En Ruta', 50, 2022, 'Scania K250UB Euro VI / Busscar', '2026-09-28'),
('TM-9301', 'WPL-902', 'A9-3', 'En Ruta', 50, 2024, 'Scania K250UB / Busscar Urbanuss', '2026-10-10'),
('TM-9304', 'WPL-511', 'A9-3', 'En Ruta', 50, 2024, 'Volvo B290R / Marcopolo Torino', '2026-10-08'),
('TM-7301', 'WPL-331', 'A7-3', 'En Ruta', 50, 2023, 'Scania K250UB Euro VI / Busscar', '2026-10-14'),
('TM-7401', 'WPL-720', 'A7-4', 'En Ruta', 50, 2023, 'Scania K250UB Euro VI / Busscar', '2026-10-11'),
('TM-1201', 'WPL-128', 'A1-2', 'En Ruta', 50, 2022, 'Scania K250UB Euro VI / Busscar', '2026-09-30'),
('TM-3101', 'WPL-240', 'A3-1', 'En Ruta', 50, 2022, 'Scania K250UB / Busscar', '2026-09-25'),
('TM-2101', 'WPL-842', 'A2-1', 'En Ruta', 50, 2022, 'Scania K250UB / Busscar', '2026-09-18'),
('TM-3201', 'WPL-722', 'A3-2', 'En Ruta', 50, 2022, 'Scania K250UB / Busscar', '2026-09-15'),
('TM-5301', 'WPL-755', 'A5-3', 'En Ruta', 50, 2023, 'Mercedes-Benz OF-1721 / Marcopolo', '2026-10-01')
ON CONFLICT (bus_id) DO UPDATE SET
    operational_status = EXCLUDED.operational_status,
    current_route_id = EXCLUDED.current_route_id;

-- 4. USUARIOS CON RBAC (Pasajero, Conductores, Despachador CCO y Administrador)
INSERT INTO usuarios (id, fullname, email, password_hash, role, assigned_bus_id, assigned_route_id)
VALUES
('usr-pas-01', 'Carlos Mario Arteta', 'pasajero@barranquilla.gov.co', 'transmetro2026', 'pasajero', NULL, NULL),
('usr-cond-01', 'Álvaro Montero Cantillo', 'conductor@transmetro.gov.co', 'conductor2026', 'conductor', 'TM-8101', 'A8-1'),
('usr-cond-02', 'Wilson Palacio Salcedo', 'marlon.gutierrez@transmetro.gov.co', 'conductor2026', 'conductor', 'TM-8105', 'A8-1'),
('usr-cond-03', 'Eder Bolaño Pacheco', 'eder.bolano@transmetro.gov.co', 'conductor2026', 'conductor', 'TM-8201', 'A8-2'),
('usr-cond-04', 'Roberto Polo Mendoza', 'alvaro.montero@transmetro.gov.co', 'conductor2026', 'conductor', 'TM-9301', 'A9-3'),
('usr-cond-05', 'Guillermo Celis Acosta', 'wilson.palacio@transmetro.gov.co', 'conductor2026', 'conductor', 'TM-9304', 'A9-3'),
('usr-jefe-01', 'Ing. Brenda Carvajal (CCO)', 'jeferuta@transmetro.gov.co', 'jeferuta2026', 'jefe_ruta', NULL, NULL),
('usr-adm-01', 'Secretaría Distrital de Tránsito y Seguridad Vial', 'admin@barranquilla.gov.co', 'adminbarranquilla', 'admin', NULL, NULL)
ON CONFLICT (email) DO UPDATE SET
    fullname = EXCLUDED.fullname,
    assigned_bus_id = EXCLUDED.assigned_bus_id,
    assigned_route_id = EXCLUDED.assigned_route_id;

-- 5. TELEMETRÍA GPS EN VIVO (POSICIÓN ACTIVA DE LA FLOTA)
INSERT INTO telemetria_en_vivo (bus_id, route_id, driver_id, lat, lng, speed_kmh, heading, eta_minutes, distance_meters, next_stop_name, occupancy_percent)
VALUES
('TM-8101', 'A8-1', 'usr-cond-01', 11.0068000, -74.8180000, 32.00, 45.0, 3, 750, 'Cll 84 con Cra 51B (Macmondongo)', 65),
('TM-8105', 'A8-1', 'usr-cond-02', 11.0180000, -74.8015000, 28.50, 190.0, 8, 1900, 'Cll 82 con Cra 55 (Retorno)', 45),
('TM-8201', 'A8-2', 'usr-cond-03', 11.0130000, -74.7940000, 29.00, 220.0, 4, 980, 'Cll 76 con Cra 57 (Combarranquilla)', 70),
('TM-9301', 'A9-3', 'usr-cond-04', 11.0180000, -74.8320000, 35.00, 340.0, 5, 1250, 'Cll 98 con Cra 52 (C.C. Buenavista)', 82)
ON CONFLICT (bus_id) DO UPDATE SET
    lat = EXCLUDED.lat,
    lng = EXCLUDED.lng,
    speed_kmh = EXCLUDED.speed_kmh,
    heading = EXCLUDED.heading,
    eta_minutes = EXCLUDED.eta_minutes,
    distance_meters = EXCLUDED.distance_meters,
    next_stop_name = EXCLUDED.next_stop_name,
    occupancy_percent = EXCLUDED.occupancy_percent,
    last_ping = CURRENT_TIMESTAMP;

-- 6. INSPECCIONES PREOPERACIONALES DE SEGURIDAD
INSERT INTO preoperacionales (
    id, conductor_id, bus_id, route_id, odometro_km,
    freno_servicio_ok, freno_estacionamiento_ok, presion_manometros_psi,
    neumaticos_labrado_ok, luces_altas_bajas_ok, direccionales_freno_ok, limpiaparabrisas_espejos_ok,
    timbre_parada_ok, puertas_neumaticas_ok, validador_tarjetas_ok, barras_sujecion_ok,
    extintor_vigente, botiquin_primeros_auxilios, martillos_fragmentadores, kit_carretera_repuesto,
    nivel_aceite_motor_ok, nivel_refrigerante_ok, nivel_combustible_porcentaje,
    observaciones, estado_aprobacion
)
VALUES
('PRE-001', 'usr-cond-01', 'TM-8101', 'A8-1', 138450, TRUE, TRUE, 115, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 92, 'Vehículo en óptimas condiciones para inicio de turno matutino.', 'Aprobado'),
('PRE-002', 'usr-cond-02', 'TM-8105', 'A8-1', 142100, TRUE, TRUE, 110, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 85, 'Presión de llantas revisada en patio taller.', 'Aprobado'),
('PRE-003', 'usr-cond-03', 'TM-8201', 'A8-2', 98320, TRUE, TRUE, 120, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 88, 'Validador contactless actualizado con tarifa vigente.', 'Aprobado'),
('PRE-004', 'usr-cond-04', 'TM-9301', 'A9-3', 115600, TRUE, TRUE, 108, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 78, 'Aire acondicionado y timbres funcionando con normalidad.', 'Aprobado')
ON CONFLICT (id) DO NOTHING;

-- 7. INCIDENTES Y NOVEDADES EN VÍA
INSERT INTO incidentes (
    id, conductor_id, bus_id, route_id, tipo, prioridad,
    ubicacion_referencia, descripcion, estado, resolucion_notas
)
VALUES
('INC-101', 'usr-cond-01', 'TM-8101', 'A8-1', 'Bloqueo en Vía / Congestión', 'Media', 'Calle 84 con Carrera 51B', 'Alto flujo vehicular por reparaciones de acueducto en el carril derecho. Retraso estimado de 6 min.', 'En Atención', 'Despacho CCO autoriza desvío preventivo por Cra 52.'),
('INC-102', 'usr-cond-04', 'TM-9301', 'A9-3', 'Accidente de Tránsito', 'Alta', 'Calle 98 con Carrera 52 (Frente a Buenavista)', 'Colisión leve entre dos vehículos particulares obstruye el giro hacia el centro comercial.', 'En Atención', 'Patrulla de tránsito y regulador de Transmetro agilizan el flujo.'),
('INC-103', 'usr-cond-03', 'TM-8201', 'A8-2', 'Varada Mecánica', 'Baja', 'Estación Joe Arroyo - Plataforma Norte', 'Ajuste preventivo en sensor de puerta delantera antes de iniciar despacho.', 'Resuelto', 'Técnico de patio solucionó el contacto en 8 minutos.')
ON CONFLICT (id) DO NOTHING;

-- 8. MENSAJES DE REGULACIÓN RADIAL (CCO -> CABINA CONDUCTOR)
INSERT INTO mensajes_regulacion (id, jefe_id, bus_id, mensaje, read_by_driver)
VALUES
('MSG-001', 'usr-jefe-01', 'TM-8101', 'Mantener intervalo de 6 minutos respecto a unidad TM-8105 en Paraíso. Tráfico fluido en Vía 40.', TRUE),
('MSG-002', 'usr-jefe-01', 'TM-9301', 'Precaución en intersección Villa Country por flujo comercial. Modular velocidad a 30 km/h.', FALSE),
('MSG-003', 'usr-jefe-01', 'TM-8201', 'Despacho autorizado a tiempo. Mantener frecuencia de 8 min hacia el Zoológico.', TRUE)
ON CONFLICT (id) DO NOTHING;

