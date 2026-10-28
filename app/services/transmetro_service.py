import math
import random
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from app.schemas.transmetro import (
    RouteDetail, BusStop, BusLiveStatus, BusOperationalStatus,
    PreoperacionalRecord, PreoperacionalCreate,
    IncidenteRecord, IncidenteCreate, DriverGPSUpdate, DriverStateChange
)

MOCK_ROUTES: Dict[str, dict] = {
    # 1. A8-1 Paraíso (Estación Joe Arroyo - Calle 84 - Vía 40)
    "A8-1": {
        "id": "A8-1",
        "code": "A8-1",
        "name": "Paraíso - Vía 40",
        "type": "Alimentador",
        "color": "#0284C7",  # Sky blue
        "description": "Conecta la Estación de Retorno Joe Arroyo con los barrios Paraíso, Villa Andalucía y el corredor industrial Vía 40.",
        "frequency_minutes": 6,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9982, -74.8105],  # Estación Joe Arroyo
            [11.0025, -74.8142],  # Cra 46 con Cll 76
            [11.0068, -74.8180],  # Cra 46 con Cll 82
            [11.0090, -74.8198],  # Cll 84 con Cra 47
            [11.0125, -74.8235],  # Cll 84 con Cra 52
            [11.0150, -74.8190],  # Cll 84 con Cra 65
            [11.0178, -74.8150],  # Cra 65 con Cll 86 (Villa Andalucía)
            [11.0205, -74.8100],  # Cra 75B con Cll 85
            [11.0225, -74.8050],  # Vía 40 con Cll 85 (Sector Paraíso)
            [11.0180, -74.8015],  # Vía 40 con Cll 80
            [11.0145, -74.8065],  # Cll 80 con Cra 64
            [11.0110, -74.8120],  # Cll 82 con Cra 55
            [11.0068, -74.8180],  # Retorno a Cra 46
            [10.9982, -74.8105]   # Llegada Estación Joe Arroyo
        ],
        "stops": [
            {"id": "a81_s1", "name": "Estación Joe Arroyo (Plataforma)", "lat": 10.9982, "lng": -74.8105, "order": 1},
            {"id": "a81_s2", "name": "Cra 46 con Cll 76 (Lado Norte)", "lat": 11.0025, "lng": -74.8142, "order": 2},
            {"id": "a81_s3", "name": "Cra 46 con Cll 82", "lat": 11.0068, "lng": -74.8180, "order": 3},
            {"id": "a81_s4", "name": "Cll 84 con Cra 51B (Macmondongo)", "lat": 11.0125, "lng": -74.8235, "order": 4},
            {"id": "a81_s5", "name": "Cra 65 con Cll 86 (Villa Andalucía)", "lat": 11.0178, "lng": -74.8150, "order": 5},
            {"id": "a81_s6", "name": "Vía 40 con Cll 85 (Barrio Paraíso)", "lat": 11.0225, "lng": -74.8050, "order": 6},
            {"id": "a81_s7", "name": "Vía 40 con Cll 80 (Sector Industrial)", "lat": 11.0180, "lng": -74.8015, "order": 7},
            {"id": "a81_s8", "name": "Cll 82 con Cra 55 (Retorno)", "lat": 11.0110, "lng": -74.8120, "order": 8}
        ],
        "bus_seeds": [
            {"bus_id": "TM-8101", "plate": "WPL-612", "path_index": 2, "driver_name": "Alvaro Montero"},
            {"bus_id": "TM-8105", "plate": "WPL-735", "path_index": 6, "driver_name": "Wilson Palacio"}
        ]
    },

    # 2. A8-2 Vía 40 / Zoológico - Gran Malecón (Estación Joe Arroyo)
    "A8-2": {
        "id": "A8-2",
        "code": "A8-2",
        "name": "Vía 40 - Zoológico",
        "type": "Alimentador",
        "color": "#F59E0B",  # Amber
        "description": "Circuito desde Estación Joe Arroyo por Calle 79 hacia Vía 40, Zoológico de Barranquilla y retorno por Calle 76.",
        "frequency_minutes": 8,
        "schedule": "05:15 AM - 10:00 PM",
        "path": [
            [10.9982, -74.8105],  # Estación Joe Arroyo
            [11.0020, -74.8080],  # Cra 46 con Cll 76
            [11.0050, -74.8060],  # Cll 79 con Cra 50
            [11.0080, -74.8035],  # Cll 79 con Cra 53
            [11.0110, -74.8000],  # Cll 79 con Cra 57 (Country)
            [11.0150, -74.7960],  # Cll 77 con Cra 68 (Sutherland)
            [11.0185, -74.7925],  # Cll 77 con Vía 40 (Outlet Continental)
            [11.0160, -74.7895],  # Vía 40 con Cll 76 (Kia Motors)
            [11.0130, -74.7940],  # Cll 76 con Cra 68 (Zoológico de Barranquilla)
            [11.0090, -74.7990],  # Cll 76 con Cra 57 (Combarranquilla)
            [11.0050, -74.8040],  # Cll 76 con Cra 53 (Parque Karl C. Parrish)
            [11.0015, -74.8080],  # Cll 76 con Cra 49B (Olímpica)
            [10.9982, -74.8105]   # Regreso a Estación Joe Arroyo
        ],
        "stops": [
            {"id": "a82_s1", "name": "Estación Joe Arroyo (Plataforma)", "lat": 10.9982, "lng": -74.8105, "order": 1},
            {"id": "a82_s2", "name": "Cll 79 con Cra 51B", "lat": 11.0065, "lng": -74.8045, "order": 2},
            {"id": "a82_s3", "name": "Cll 79 con Cra 57 (Sector Country)", "lat": 11.0110, "lng": -74.8000, "order": 3},
            {"id": "a82_s4", "name": "Cll 77 con Vía 40 (Outlet Continental)", "lat": 11.0185, "lng": -74.7925, "order": 4},
            {"id": "a82_s5", "name": "Cll 76 con Vía 40 (Kia Motors)", "lat": 11.0160, "lng": -74.7895, "order": 5},
            {"id": "a82_s6", "name": "Cll 76 con Cra 68 (Zoológico de Barranquilla)", "lat": 11.0130, "lng": -74.7940, "order": 6},
            {"id": "a82_s7", "name": "Cll 76 con Cra 57 (Combarranquilla)", "lat": 11.0090, "lng": -74.7990, "order": 7},
            {"id": "a82_s8", "name": "Cll 76 con Cra 53 (Parque Parrish)", "lat": 11.0050, "lng": -74.8040, "order": 8}
        ],
        "bus_seeds": [
            {"bus_id": "TM-8201", "plate": "WPL-418", "path_index": 3, "driver_name": "Eder Bolaño"}
        ]
    },

    # 3. A9-3 Buenavista (Estación Joe Arroyo - Villa Country - C.C. Buenavista - Cra 51B)
    "A9-3": {
        "id": "A9-3",
        "code": "A9-3",
        "name": "Buenavista - Villa Country",
        "type": "Alimentador",
        "color": "#8B5CF6",  # Purple
        "description": "Conexión directa entre la Estación Joe Arroyo, el distrito comercial Villa Country y el Centro Comercial Buenavista sobre la Cra 51B.",
        "frequency_minutes": 5,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9982, -74.8105],  # Estación Joe Arroyo
            [11.0010, -74.8140],  # Cll 74 hacia Cra 54
            [11.0055, -74.8185],  # Cra 54 con Cll 79 (Villa Country)
            [11.0115, -74.8250],  # Cra 53 con Cll 85
            [11.0180, -74.8320],  # Cra 53 con Cll 94
            [11.0205, -74.8360],  # Cra 64 con Cll 96
            [11.0220, -74.8395],  # Cll 98 con Cra 52 (C.C. Buenavista I y II)
            [11.0200, -74.8370],  # Cra 51B con Cll 96A
            [11.0160, -74.8325],  # Cra 51B con Cll 91
            [11.0120, -74.8275],  # Cra 51B con Cll 87 (Colegio Cervantes)
            [11.0075, -74.8220],  # Cra 51B con Cll 82
            [11.0040, -74.8175],  # Cra 51B con Cll 79
            [11.0010, -74.8140],  # Cll 76 hacia Cra 46
            [10.9982, -74.8105]   # Estación Joe Arroyo
        ],
        "stops": [
            {"id": "a93_s1", "name": "Estación Joe Arroyo (Plataforma)", "lat": 10.9982, "lng": -74.8105, "order": 1},
            {"id": "a93_s2", "name": "Cra 54 con Cll 79 (Sector Villa Country)", "lat": 11.0055, "lng": -74.8185, "order": 2},
            {"id": "a93_s3", "name": "Cra 53 con Cll 94", "lat": 11.0180, "lng": -74.8320, "order": 3},
            {"id": "a93_s4", "name": "Cll 98 con Cra 52 (C.C. Buenavista)", "lat": 11.0220, "lng": -74.8395, "order": 4},
            {"id": "a93_s5", "name": "Cra 51B con Cll 96A", "lat": 11.0200, "lng": -74.8370, "order": 5},
            {"id": "a93_s6", "name": "Cra 51B con Cll 87 (Colegio Cervantes)", "lat": 11.0120, "lng": -74.8275, "order": 6},
            {"id": "a93_s7", "name": "Cra 51B con Cll 82", "lat": 11.0075, "lng": -74.8220, "order": 7},
            {"id": "a93_s8", "name": "Cra 51B con Cll 79 (Hotel El Prado)", "lat": 11.0040, "lng": -74.8175, "order": 8}
        ],
        "bus_seeds": [
            {"bus_id": "TM-9301", "plate": "WPL-902", "path_index": 2, "driver_name": "Roberto Polo"},
            {"bus_id": "TM-9304", "plate": "WPL-511", "path_index": 6, "driver_name": "Guillermo Celis"}
        ]
    },

    # 4. A7-3 Carrera 38 (Estación Joe Arroyo - Cra 38 - Estación La Arenosa / Murillo)
    "A7-3": {
        "id": "A7-3",
        "code": "A7-3",
        "name": "Carrera 38",
        "type": "Alimentador",
        "color": "#10B981",  # Emerald green
        "description": "Cruza longitudinalmente el centro-norte por la Carrera 38 conectando Estación Joe Arroyo con la troncal Murillo en Estación La Arenosa.",
        "frequency_minutes": 7,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9982, -74.8105],  # Estación Joe Arroyo
            [10.9940, -74.8120],  # Cll 74 con Cra 48
            [10.9905, -74.8145],  # Cll 76 con Cra 43
            [10.9870, -74.8175],  # Cll 76 con Cra 38 (Universidad Metropolitana)
            [10.9830, -74.8130],  # Cra 38 con Cll 72 (C.C. Americano)
            [10.9785, -74.8080],  # Cra 38 con Cll 65
            [10.9730, -74.8020],  # Cra 38 con Cll 54 (Éxito San Francisco)
            [10.9675, -74.7960],  # Cra 44 con Cll 50
            [10.9640, -74.7920],  # Av. Murillo (Estación La Arenosa)
            [10.9680, -74.7950],  # Cra 43 con Cll 54 (Retorno)
            [10.9750, -74.8030],  # Cra 38 retorno hacia el norte
            [10.9880, -74.8160],  # Cll 76B con Cra 42F
            [10.9982, -74.8105]   # Llegada Estación Joe Arroyo
        ],
        "stops": [
            {"id": "a73_s1", "name": "Estación Joe Arroyo (Plataforma)", "lat": 10.9982, "lng": -74.8105, "order": 1},
            {"id": "a73_s2", "name": "Cll 76 con Cra 43 (Clínica La Merced)", "lat": 10.9905, "lng": -74.8145, "order": 2},
            {"id": "a73_s3", "name": "Cll 76 con Cra 38 (Universidad Metropolitana)", "lat": 10.9870, "lng": -74.8175, "order": 3},
            {"id": "a73_s4", "name": "Cra 38 con Cll 72 (C.C. Americano)", "lat": 10.9830, "lng": -74.8130, "order": 4},
            {"id": "a73_s5", "name": "Cra 38 con Cll 54 (Éxito San Francisco)", "lat": 10.9730, "lng": -74.8020, "order": 5},
            {"id": "a73_s6", "name": "Av. Murillo (Conexión Estación La Arenosa)", "lat": 10.9640, "lng": -74.7920, "order": 6},
            {"id": "a73_s7", "name": "Cra 43 con Cll 54 (Retorno Norte)", "lat": 10.9680, "lng": -74.7950, "order": 7}
        ],
        "bus_seeds": [
            {"bus_id": "TM-7301", "plate": "WPL-331", "path_index": 2, "driver_name": "Jhon Jairo Berdugo"},
            {"bus_id": "TM-7305", "plate": "WPL-350", "path_index": 5, "driver_name": "Marlon Gutiérrez"}
        ]
    },

    # 5. A7-4 Los Andes (Estación Joe Arroyo - Parque Los Andes - C.C. Único)
    "A7-4": {
        "id": "A7-4",
        "code": "A7-4",
        "name": "Los Andes - Betania",
        "type": "Alimentador",
        "color": "#EF4444",  # Red
        "description": "Atiende los sectores tradicionales de Los Andes, Betania y Las Mercedes conectando con la Estación Joe Arroyo y el C.C. Único.",
        "frequency_minutes": 8,
        "schedule": "05:00 AM - 10:00 PM",
        "path": [
            [10.9982, -74.8105],  # Estación Joe Arroyo
            [10.9940, -74.8135],  # Cll 76 con Cra 43B
            [10.9910, -74.8170],  # Cll 76 con Cra 39 (C.C. Único)
            [10.9880, -74.8205],  # Cll 76 con Cra 38A (Colegio Betania)
            [10.9840, -74.8180],  # Cll 79A con Cra 33 (Parque Las Mercedes)
            [10.9780, -74.8120],  # Cra 27 con Cll 64
            [10.9740, -74.8080],  # Cra 27 con Cll 61 (Parque Los Andes)
            [10.9690, -74.8020],  # Cra 24 con Cll 54 (Seguro Los Andes)
            [10.9645, -74.7970],  # Cra 27 con Cll 45 (Éxito Murillo)
            [10.9710, -74.8040],  # Cra 21B con Cll 53D
            [10.9820, -74.8140],  # Cra 21B con Cll 68C
            [10.9930, -74.8110],  # Cll 79 con Cra 42F
            [10.9982, -74.8105]   # Llegada Estación Joe Arroyo
        ],
        "stops": [
            {"id": "a74_s1", "name": "Estación Joe Arroyo (Plataforma)", "lat": 10.9982, "lng": -74.8105, "order": 1},
            {"id": "a74_s2", "name": "Cll 76 con Cra 39 (C.C. Único)", "lat": 10.9910, "lng": -74.8170, "order": 2},
            {"id": "a74_s3", "name": "Cll 76 con Cra 38A (Colegio Betania)", "lat": 10.9880, "lng": -74.8205, "order": 3},
            {"id": "a74_s4", "name": "Cll 79A con Cra 33 (Parque Las Mercedes)", "lat": 10.9840, "lng": -74.8180, "order": 4},
            {"id": "a74_s5", "name": "Cra 27 con Cll 61 (Parque Los Andes)", "lat": 10.9740, "lng": -74.8080, "order": 5},
            {"id": "a74_s6", "name": "Cra 24 con Cll 54 (Seguro Los Andes)", "lat": 10.9690, "lng": -74.8020, "order": 6},
            {"id": "a74_s7", "name": "Cra 27 con Cll 45 (Éxito Murillo)", "lat": 10.9645, "lng": -74.7970, "order": 7},
            {"id": "a74_s8", "name": "Cll 79 con Cra 42F (Litoral)", "lat": 10.9930, "lng": -74.8110, "order": 8}
        ],
        "bus_seeds": [
            {"bus_id": "TM-7401", "plate": "WPL-720", "path_index": 3, "driver_name": "Jesús David Salcedo"}
        ]
    },

    # 6. A1-2 Carrera Ocho (Estación La Ocho - Simón Bolívar - Las Palmas)
    "A1-2": {
        "id": "A1-2",
        "code": "A1-2",
        "name": "Carrera Ocho",
        "type": "Alimentador",
        "color": "#D97706",  # Ochre / Dark Amber
        "description": "Recorre el eje vial de la Carrera 8 conectando barrios Las Palmas, El Campito, La Alboraya con la Estación Troncal La Ocho.",
        "frequency_minutes": 6,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9490, -74.7910],  # Cra 8 con Cll 31 (Inicio)
            [10.9450, -74.7865],  # Cll 30 con Cra 4B (Panorama / Homecenter)
            [10.9495, -74.7915],  # Cra 8 con Cll 34 (Torres Las Palmas)
            [10.9540, -74.7960],  # Cra 8 con Cll 40
            [10.9585, -74.8005],  # Cra 8 con Cll 45 (Estación Troncal La Ocho)
            [10.9620, -74.8040],  # Cra 8 con Cll 49
            [10.9660, -74.8085],  # Cll 53 con Cra 8G
            [10.9695, -74.8120],  # Cll 56 con Cra 9D (Retorno)
            [10.9620, -74.8040],  # Cra 8 con Cll 49 Sur
            [10.9585, -74.8005],  # Cra 8 con Cll 45 Sur (Estación La Ocho)
            [10.9530, -74.7950],  # Cra 8 con Cll 37D
            [10.9490, -74.7910]   # Cierre en Cra 8 con Cll 31
        ],
        "stops": [
            {"id": "a12_s1", "name": "Cra 8 con Cll 31 (Punto Sur)", "lat": 10.9490, "lng": -74.7910, "order": 1},
            {"id": "a12_s2", "name": "Cll 30 con Cra 4B (C.C. Panorama)", "lat": 10.9450, "lng": -74.7865, "order": 2},
            {"id": "a12_s3", "name": "Cra 8 con Cll 34 (Torres de Las Palmas)", "lat": 10.9495, "lng": -74.7915, "order": 3},
            {"id": "a12_s4", "name": "Cra 8 con Cll 45 (Conexión Estación La Ocho)", "lat": 10.9585, "lng": -74.8005, "order": 4},
            {"id": "a12_s5", "name": "Cra 8 con Cll 49", "lat": 10.9620, "lng": -74.8040, "order": 5},
            {"id": "a12_s6", "name": "Cll 53 con Cra 8G (El Santuario)", "lat": 10.9660, "lng": -74.8085, "order": 6},
            {"id": "a12_s7", "name": "Cll 56 con Cra 9D (Retorno)", "lat": 10.9695, "lng": -74.8120, "order": 7}
        ],
        "bus_seeds": [
            {"bus_id": "TM-1201", "plate": "WPL-128", "path_index": 2, "driver_name": "Alvaro Cantillo"}
        ]
    },

    # 7. A3-1 Villa Katanga (Estación Pedro Ramayá - C.C. Plaza del Sol - Soledad)
    "A3-1": {
        "id": "A3-1",
        "code": "A3-1",
        "name": "Villa Katanga - Plaza del Sol",
        "type": "Alimentador",
        "color": "#059669",  # Emerald teal
        "description": "Comunica la Estación Troncal Pedro Ramayá con la Calle 30, el Centro Comercial Plaza del Sol y Villa Katanga en Soledad.",
        "frequency_minutes": 7,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9380, -74.7930],  # Cra 24 con Cll 63 (Estación Pedro Ramayá)
            [10.9335, -74.7890],  # Cra 24 con Cll 55B
            [10.9290, -74.7850],  # Cra 24 con Cll 48
            [10.9250, -74.7820],  # Cll 45 con Cra 26A
            [10.9210, -74.7760],  # Cra 30 con Cll 40
            [10.9165, -74.7715],  # Cra 30 con Cll 30 (C.C. Plaza del Sol)
            [10.9190, -74.7670],  # Cll 35 con Cra 30 (Villa Katanga)
            [10.9230, -74.7720],  # Cra 37 con Cll 40
            [10.9280, -74.7790],  # Cll 45 con Cra 27A
            [10.9340, -74.7880],  # Cra 24 retorno
            [10.9380, -74.7930]   # Llegada Estación Pedro Ramayá
        ],
        "stops": [
            {"id": "a31_s1", "name": "Estación Pedro Ramayá (Plataforma)", "lat": 10.9380, "lng": -74.7930, "order": 1},
            {"id": "a31_s2", "name": "Cra 24 con Cll 55B", "lat": 10.9335, "lng": -74.7890, "order": 2},
            {"id": "a31_s3", "name": "Cra 24 con Cll 48", "lat": 10.9290, "lng": -74.7850, "order": 3},
            {"id": "a31_s4", "name": "Cra 30 con Cll 40", "lat": 10.9210, "lng": -74.7760, "order": 4},
            {"id": "a31_s5", "name": "Cra 30 con Cll 30 (C.C. Plaza del Sol)", "lat": 10.9165, "lng": -74.7715, "order": 5},
            {"id": "a31_s6", "name": "Cll 35 con Cra 30 (Villa Katanga)", "lat": 10.9190, "lng": -74.7670, "order": 6},
            {"id": "a31_s7", "name": "Cll 45 con Cra 27A", "lat": 10.9280, "lng": -74.7790, "order": 7}
        ],
        "bus_seeds": [
            {"bus_id": "TM-3101", "plate": "WPL-240", "path_index": 3, "driver_name": "Julio Char"}
        ]
    },

    # 8. A2-1 Hipódromo (Estación Joaquín Barrios Polo - Metrocentro - Soledad)
    "A2-1": {
        "id": "A2-1",
        "code": "A2-1",
        "name": "Hipódromo - Metrocentro",
        "type": "Alimentador",
        "color": "#EA580C",  # Vibrant Orange
        "description": "Conecta la Estación Joaquín Barrios Polo (Metrocentro) por Av. Las Torres y Cll 30 con los barrios Hipódromo e ITIDA en Soledad.",
        "frequency_minutes": 6,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9490, -74.8020],  # Estación Joaquín Barrios Polo (Metrocentro)
            [10.9460, -74.8055],  # Cll 45D con Cra 1
            [10.9410, -74.8020],  # Av. Las Torres con Cll 45
            [10.9350, -74.7970],  # Av. Las Torres con Cll 54
            [10.9300, -74.7900],  # Av. Circunvalar con Av. Las Torres
            [10.9320, -74.7800],  # Cll 30 frente Colegio ITIDA
            [10.9360, -74.7730],  # Cra 30 con Cll 30 (SAO Hipódromo)
            [10.9410, -74.7710],  # Cll 18 con Cra 27 (Hipódromo Centro)
            [10.9440, -74.7750],  # Cra 19 con Cll 23
            [10.9380, -74.7810],  # Cll 30 retorno (Colegio INEM)
            [10.9330, -74.7920],  # Av. Las Torres retorno
            [10.9490, -74.8020]   # Llegada Estación Joaquín Barrios Polo
        ],
        "stops": [
            {"id": "a21_s1", "name": "Estación Joaquín Barrios Polo (Metrocentro)", "lat": 10.9490, "lng": -74.8020, "order": 1},
            {"id": "a21_s2", "name": "Cll 45D con Cra 1 (Metrocentro)", "lat": 10.9460, "lng": -74.8055, "order": 2},
            {"id": "a21_s3", "name": "Av. Las Torres con Cll 48", "lat": 10.9380, "lng": -74.8000, "order": 3},
            {"id": "a21_s4", "name": "Cll 30 (Colegio ITIDA)", "lat": 10.9320, "lng": -74.7800, "order": 4},
            {"id": "a21_s5", "name": "Cra 30 con Cll 30 (SAO Hipódromo)", "lat": 10.9360, "lng": -74.7730, "order": 5},
            {"id": "a21_s6", "name": "Cll 18 con Cra 27 (Sector Hipódromo)", "lat": 10.9410, "lng": -74.7710, "order": 6},
            {"id": "a21_s7", "name": "Cll 30 (Colegio INEM / Entrada Tucán)", "lat": 10.9380, "lng": -74.7810, "order": 7}
        ],
        "bus_seeds": [
            {"bus_id": "TM-2101", "plate": "WPL-842", "path_index": 2, "driver_name": "Jhon Jairo Berdugo"},
            {"bus_id": "TM-2105", "plate": "WPL-890", "path_index": 5, "driver_name": "Marlon Gutiérrez"}
        ]
    },

    # 9. A3-2 Soledad - Hipódromo (Portal de Soledad)
    "A3-2": {
        "id": "A3-2",
        "code": "A3-2",
        "name": "Soledad - Hipódromo",
        "type": "Alimentador",
        "color": "#D946EF",  # Fuchsia
        "description": "Conexión directa desde Portal de Soledad por Calle 30 hacia el barrio Hipódromo y centro de Soledad.",
        "frequency_minutes": 7,
        "schedule": "05:00 AM - 10:30 PM",
        "path": [
            [10.9254, -74.7788],  # Portal de Soledad
            [10.9280, -74.7750],  # Cll 30 con Cra 16
            [10.9315, -74.7720],  # Cll 30 con Cra 19
            [10.9360, -74.7695],  # Cra 19 con Cll 24
            [10.9412, -74.7725],  # Parque Hipódromo
            [10.9430, -74.7760],  # Cll 24 Soledad Centro
            [10.9385, -74.7810],  # Cra 15 Retorno
            [10.9320, -74.7800],  # Cll 30 aproximación
            [10.9254, -74.7788]   # Portal de Soledad
        ],
        "stops": [
            {"id": "a32_s1", "name": "Portal de Soledad (Cabecera)", "lat": 10.9254, "lng": -74.7788, "order": 1},
            {"id": "a32_s2", "name": "Cll 30 con Cra 19 (Olímpica)", "lat": 10.9315, "lng": -74.7720, "order": 2},
            {"id": "a32_s3", "name": "Parque Hipódromo", "lat": 10.9412, "lng": -74.7725, "order": 3},
            {"id": "a32_s4", "name": "Cll 24 Soledad Centro", "lat": 10.9430, "lng": -74.7760, "order": 4},
            {"id": "a32_s5", "name": "Cra 15 Retorno Portal", "lat": 10.9385, "lng": -74.7810, "order": 5}
        ],
        "bus_seeds": [
            {"bus_id": "TM-3201", "plate": "WPL-722", "path_index": 2, "driver_name": "Jhon Jairo Berdugo"}
        ]
    },

    # 10. A5-3 La Central - Soledad 2000 (Portal de Soledad)
    "A5-3": {
        "id": "A5-3",
        "code": "A5-3",
        "name": "La Central - Soledad 2000",
        "type": "Alimentador",
        "color": "#06B6D4",  # Cyan
        "description": "Recorrido de alta demanda conectando Portal de Soledad con Soledad 2000, Manuela Beltrán y La Central.",
        "frequency_minutes": 8,
        "schedule": "05:15 AM - 10:00 PM",
        "path": [
            [10.9254, -74.7788],  # Portal de Soledad
            [10.9210, -74.7830],  # Av. Murillo con Cra 14
            [10.9160, -74.7875],  # Entrada Soledad 2000
            [10.9110, -74.7920],  # Av. Las Torres Soledad
            [10.9080, -74.7960],  # Sector La Central Plaza
            [10.9125, -74.7990],  # Cra 15 Sur
            [10.9180, -74.7930],  # Retorno Manuela Beltrán
            [10.9220, -74.7850],  # Murillo aproximación
            [10.9254, -74.7788]   # Portal de Soledad
        ],
        "stops": [
            {"id": "a53_s1", "name": "Portal de Soledad (Cabecera)", "lat": 10.9254, "lng": -74.7788, "order": 1},
            {"id": "a53_s2", "name": "Av. Murillo con Cra 14", "lat": 10.9210, "lng": -74.7830, "order": 2},
            {"id": "a53_s3", "name": "Entrada Soledad 2000", "lat": 10.9160, "lng": -74.7875, "order": 3},
            {"id": "a53_s4", "name": "Sector La Central Plaza", "lat": 10.9080, "lng": -74.7960, "order": 4},
            {"id": "a53_s5", "name": "Retorno Manuela Beltrán", "lat": 10.9180, "lng": -74.7930, "order": 5}
        ],
        "bus_seeds": [
            {"bus_id": "TM-5301", "plate": "WPL-755", "path_index": 3, "driver_name": "Eder Bolaño"}
        ]
    }
}

# Estado mutable de buses
BUS_TRACKER_STATE: Dict[str, dict] = {}

# Registros Preoperacionales
PREOPERACIONALES_DB: List[PreoperacionalRecord] = [
    PreoperacionalRecord(
        id="PRE-901",
        conductor_id="usr-cond-01",
        conductor_nombre="Jhon Jairo Berdugo",
        bus_id="TM-3201",
        route_id="A3-2",
        created_at="2026-10-21 05:15:00",
        estado_aprobacion="Aprobado",
        detalles=PreoperacionalCreate(
            bus_id="TM-3201",
            route_id="A3-2",
            odometro_km=138400,
            frenos={"freno_servicio_ok": True, "freno_estacionamiento_ok": True, "presion_manometros_psi": 115},
            tecnico={"neumaticos_labrado_ok": True, "luces_altas_bajas_ok": True, "direccionales_freno_ok": True, "limpiaparabrisas_espejos_ok": True},
            pasajeros={"timbre_parada_ok": True, "puertas_neumaticas_ok": True, "validador_tarjetas_ok": True, "barras_sujecion_ok": True},
            seguridad={"extintor_vigente": True, "botiquin_primeros_auxilios": True, "martillos_fragmentadores": True, "kit_carretera_repuesto": True},
            fluidos={"nivel_aceite_motor_ok": True, "nivel_refrigerante_ok": True, "nivel_combustible_porcentaje": 90},
            observaciones="Vehículo en óptimas condiciones para inicio de jornada matutina."
        )
    )
]

# Incidentes en vía
INCIDENTES_DB: List[IncidenteRecord] = [
    IncidenteRecord(
        id="INC-204",
        conductor_id="usr-cond-01",
        conductor_nombre="Jhon Jairo Berdugo",
        bus_id="TM-3201",
        route_id="A3-2",
        tipo="Bloqueo en Vía / Congestión",
        prioridad="Media",
        ubicacion_referencia="Calle 30 frente al Hipódromo",
        descripcion="Congestión alta por reparaciones viales, retraso aproximado de 8 minutos en frecuencia.",
        estado="En Atención",
        created_at="2026-10-21 09:10:00",
        resolucion_notas="Despachador CCO autoriza desvío temporal por carrera 18."
    )
]

# Mensajes de regulación del CCO a conductores
REGULACION_CCO_MESSAGES: List[dict] = [
    {"id": "msg-1", "bus_id": "TM-8101", "sender": "Jefe de Ruta CCO", "text": "Mantener intervalo de 6 minutos respecto a unidad TM-8105 en Paraíso. Tráfico fluido en Vía 40.", "time": "09:30 AM"},
    {"id": "msg-2", "bus_id": "TM-9301", "sender": "Jefe de Ruta CCO", "text": "Precaución en intersección Villa Country por flujo comercial. Modular velocidad a 30 km/h.", "time": "09:45 AM"}
]

# Cargar trazados de calles reales calculados sobre la malla vial (OSRM / OpenStreetMap)
STREET_GEOMETRY_FILE = os.path.join(os.path.dirname(__file__), "routes_street_geometry.json")
if os.path.exists(STREET_GEOMETRY_FILE):
    try:
        with open(STREET_GEOMETRY_FILE, "r", encoding="utf-8") as f:
            street_geometries = json.load(f)
            for rid, real_path in street_geometries.items():
                if rid in MOCK_ROUTES and len(real_path) > 10:
                    MOCK_ROUTES[rid]["path"] = real_path
    except Exception as e:
        print(f"[Aviso] No se pudo cargar routes_street_geometry.json: {e}")

def init_tracker():
    global BUS_TRACKER_STATE
    for route_id, route_data in MOCK_ROUTES.items():
        path = route_data["path"]
        for seed in route_data["bus_seeds"]:
            bid = seed["bus_id"]
            BUS_TRACKER_STATE[bid] = {
                "route_id": route_id,
                "plate": seed["plate"],
                "path_idx": seed["path_index"],
                "sub_step": 0.0,
                "speed_kmh": 28.0,
                "occupancy": 65,
                "driver_name": seed.get("driver_name", "Conductor Oficial"),
                "status": "En Ruta",
                "in_shift": True,
                "manual_gps": False
            }

init_tracker()

def get_all_routes_summary() -> List[dict]:
    return [
        {
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "type": r["type"],
            "color": r["color"],
            "description": r["description"],
            "frequency_minutes": r["frequency_minutes"],
            "schedule": r["schedule"],
            "total_stops": len(r["stops"]),
            "active_buses": len(r["bus_seeds"])
        }
        for r in MOCK_ROUTES.values()
    ]

def step_bus_simulation(route_id: Optional[str] = None) -> List[BusLiveStatus]:
    results: List[BusLiveStatus] = []
    
    for bus_id, state in BUS_TRACKER_STATE.items():
        if route_id and state["route_id"] != route_id:
            continue
            
        route = MOCK_ROUTES[state["route_id"]]
        path = route["path"]
        stops = route["stops"]
        
        # Si el conductor no está forzando GPS manual, simular avance suave
        if not state.get("manual_gps", False):
            state["sub_step"] += 0.15 + (random.random() * 0.05)
            if state["sub_step"] >= 1.0:
                state["sub_step"] = 0.0
                state["path_idx"] = (state["path_idx"] + 1) % (len(path) - 1)
                state["occupancy"] = min(98, max(20, state["occupancy"] + random.randint(-5, 6)))
                state["speed_kmh"] = round(max(15.0, min(48.0, state["speed_kmh"] + random.uniform(-4, 4))), 1)

            idx = state["path_idx"]
            next_idx = (idx + 1) % len(path)
            p1 = path[idx]
            p2 = path[next_idx]

            t = state["sub_step"]
            lat = round(p1[0] + (p2[0] - p1[0]) * t, 6)
            lng = round(p1[1] + (p2[1] - p1[1]) * t, 6)

            d_lat = p2[0] - p1[0]
            d_lng = p2[1] - p1[1]
            heading = round((math.degrees(math.atan2(d_lng, d_lat)) + 360) % 360, 1)
            state["current_lat"] = lat
            state["current_lng"] = lng
            state["heading"] = heading
        else:
            lat = state["current_lat"]
            lng = state["current_lng"]
            heading = state.get("heading", 0.0)
            idx = state.get("path_idx", 0)

        nearest_stop = stops[idx % len(stops)]["name"]
        eta_min = max(1, int((len(path) - idx) * 1.8 - (state.get("sub_step", 0) * 2)))
        dist_m = int(eta_min * 420)

        # Estado textual
        operational_state = state.get("status", "En Ruta")
        if operational_state != "En Ruta":
            status_text = operational_state
        elif eta_min <= 2:
            status_text = "Cerca a tu paradero"
        elif eta_min > 12:
            status_text = "Demorado por congestión"
        else:
            status_text = "En camino"

        results.append(BusLiveStatus(
            bus_id=bus_id,
            plate=state["plate"],
            current_lat=lat,
            current_lng=lng,
            speed_kmh=state["speed_kmh"],
            next_stop=nearest_stop,
            eta_minutes=eta_min,
            distance_meters=dist_m,
            status=status_text,
            occupancy_percent=state["occupancy"],
            heading=heading,
            driver_name=state.get("driver_name", "Conductor Oficial")
        ))

    return results

def get_route_full_detail(route_id: str) -> Optional[RouteDetail]:
    if route_id not in MOCK_ROUTES:
        return None
    r = MOCK_ROUTES[route_id]
    live_buses = step_bus_simulation(route_id)
    return RouteDetail(
        id=r["id"],
        code=r["code"],
        name=r["name"],
        type=r["type"],
        color=r["color"],
        description=r["description"],
        frequency_minutes=r["frequency_minutes"],
        schedule=r["schedule"],
        path=r["path"],
        stops=[BusStop(**s) for s in r["stops"]],
        buses=live_buses
    )

def update_driver_gps(update: DriverGPSUpdate):
    if update.bus_id not in BUS_TRACKER_STATE:
        BUS_TRACKER_STATE[update.bus_id] = {
            "route_id": update.route_id,
            "plate": "WPL-722",
            "path_idx": 0,
            "sub_step": 0.0,
            "speed_kmh": update.speed_kmh,
            "occupancy": update.occupancy_percent or 50,
            "driver_name": "Conductor en Vivo",
            "status": "En Ruta",
            "in_shift": True,
            "manual_gps": True
        }
    BUS_TRACKER_STATE[update.bus_id]["route_id"] = update.route_id
    BUS_TRACKER_STATE[update.bus_id]["current_lat"] = update.lat
    BUS_TRACKER_STATE[update.bus_id]["current_lng"] = update.lng
    BUS_TRACKER_STATE[update.bus_id]["speed_kmh"] = update.speed_kmh
    BUS_TRACKER_STATE[update.bus_id]["heading"] = update.heading
    BUS_TRACKER_STATE[update.bus_id]["occupancy"] = update.occupancy_percent
    BUS_TRACKER_STATE[update.bus_id]["manual_gps"] = True

def update_driver_status(state_change: DriverStateChange):
    if state_change.bus_id not in BUS_TRACKER_STATE:
        BUS_TRACKER_STATE[state_change.bus_id] = {
            "route_id": state_change.route_id,
            "plate": "WPL-722",
            "path_idx": 0,
            "sub_step": 0.0,
            "speed_kmh": 0.0,
            "occupancy": 50,
            "driver_name": "Conductor en Vivo",
            "status": state_change.status.value,
            "in_shift": state_change.in_shift,
            "manual_gps": True
        }
    else:
        BUS_TRACKER_STATE[state_change.bus_id]["route_id"] = state_change.route_id
        BUS_TRACKER_STATE[state_change.bus_id]["status"] = state_change.status.value
        BUS_TRACKER_STATE[state_change.bus_id]["in_shift"] = state_change.in_shift
