import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from app.routers import auth, transmetro, conductor, jefe_ruta, admin
from app.routers.auth import get_current_user_optional, require_role
from app.schemas.transmetro import UserRole

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="MoviBAQ - Portal Transmetro en Vivo (RBAC Multi-Rol)",
    description="Sistema de monitoreo en tiempo real de Transmetro Barranquilla con perfiles para Pasajero, Conductor, Jefe de Ruta y Administrador.",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos y Templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Routers API
app.include_router(auth.router)
app.include_router(transmetro.router)
app.include_router(conductor.router)
app.include_router(jefe_ruta.router)
app.include_router(admin.router)

# ----------------- VISTAS WEB (FRONTEND JINJA2) -----------------

@app.get("/", response_class=HTMLResponse, summary="Página Principal Informativa")
def home_view(request: Request):
    user = get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "user": user,
            "title": "MoviBAQ | Portal Oficial Transmetro Barranquilla"
        }
    )

@app.get("/mapa", response_class=HTMLResponse, summary="Vista Ciudadana (Mapa en Vivo)")
def mapa_view(request: Request):
    user = get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "title": "Transmetro en Vivo | Mapa Satelital MoviBAQ"
        }
    )

@app.get("/login", response_class=HTMLResponse, summary="Acceso Unificado RBAC")
def login_view(request: Request):
    user = get_current_user_optional(request)
    if user:
        role = user.get("role", "pasajero")
        if role == UserRole.CONDUCTOR.value:
            return RedirectResponse(url="/conductor")
        elif role == UserRole.JEFE_RUTA.value:
            return RedirectResponse(url="/jefe-ruta")
        elif role == UserRole.ADMIN.value:
            return RedirectResponse(url="/admin")
        return RedirectResponse(url="/")
        
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Ingreso Ciudadano y Operativo - Transmetro Barranquilla"
        }
    )

@app.get("/conductor", response_class=HTMLResponse, summary="Portal Móvil de Conductor")
def conductor_view(request: Request):
    user = get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] not in [UserRole.CONDUCTOR.value, UserRole.ADMIN.value]:
        return RedirectResponse(url="/")
        
    return templates.TemplateResponse(
        request=request,
        name="conductor_dashboard.html",
        context={
            "user": user,
            "title": "Portal de Conductor | Transmetro Barranquilla"
        }
    )

@app.get("/jefe-ruta", response_class=HTMLResponse, summary="Centro de Control de Operación (CCO)")
def jefe_ruta_view(request: Request):
    user = get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] not in [UserRole.JEFE_RUTA.value, UserRole.ADMIN.value]:
        return RedirectResponse(url="/")
        
    return templates.TemplateResponse(
        request=request,
        name="jefe_ruta_dashboard.html",
        context={
            "user": user,
            "title": "Centro de Control CCO | Transmetro Barranquilla"
        }
    )

@app.get("/admin", response_class=HTMLResponse, summary="Administración General Transmetro")
def admin_view(request: Request):
    user = get_current_user_optional(request)
    if not user or user["role"] != UserRole.ADMIN.value:
        return RedirectResponse(url="/login")
        
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "user": user,
            "title": "Administración del Sistema | Transmetro Barranquilla"
        }
    )
