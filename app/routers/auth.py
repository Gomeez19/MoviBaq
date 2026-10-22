import os
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.responses import JSONResponse, RedirectResponse
from app.schemas.transmetro import UserLogin, UserRegister, UserRole
from typing import Dict, List, Callable, Optional
import uuid
from datetime import datetime, timedelta, timezone

# JWT
from jose import JWTError, jwt

# Bcrypt para hashing seguro de contraseñas
from passlib.context import CryptContext

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# ----- CONFIGURACIÓN JWT -----
SECRET_KEY = os.getenv("SECRET_KEY", "transmetro_barranquilla_secret_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"

# ----- BCRYPT CONTEXT -----
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Compatibilidad con usuarios semilla (texto plano legacy) y bcrypt
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback: comparación directa para passwords legacy del seed SQL
        return plain_password == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# Simulación de usuarios registrados con RBAC (4 Perfiles)
MOCK_USERS_DB: Dict[str, dict] = {
    # 1. Pasajero
    "pasajero@barranquilla.gov.co": {
        "id": "usr-pas-01",
        "fullname": "Carlos Mario Arteta",
        "email": "pasajero@barranquilla.gov.co",
        "password": "transmetro2026",
        "role": UserRole.PASAJERO.value,
        "assigned_bus": None,
        "assigned_route": None
    },
    # 2. Conductores de Operación
    "conductor@transmetro.gov.co": {
        "id": "usr-cond-01",
        "fullname": "Jhon Jairo Berdugo",
        "email": "conductor@transmetro.gov.co",
        "password": "conductor2026",
        "role": UserRole.CONDUCTOR.value,
        "assigned_bus": "TM-8101",
        "assigned_route": "A8-1"
    },
    "marlon.gutierrez@transmetro.gov.co": {
        "id": "usr-cond-02",
        "fullname": "Marlon Gutiérrez Mendoza",
        "email": "marlon.gutierrez@transmetro.gov.co",
        "password": "conductor2026",
        "role": UserRole.CONDUCTOR.value,
        "assigned_bus": "TM-8105",
        "assigned_route": "A8-1"
    },
    "eder.bolano@transmetro.gov.co": {
        "id": "usr-cond-03",
        "fullname": "Eder Bolaño Pacheco",
        "email": "eder.bolano@transmetro.gov.co",
        "password": "conductor2026",
        "role": UserRole.CONDUCTOR.value,
        "assigned_bus": "TM-8201",
        "assigned_route": "A8-2"
    },
    "alvaro.montero@transmetro.gov.co": {
        "id": "usr-cond-04",
        "fullname": "Álvaro Montero Cantillo",
        "email": "alvaro.montero@transmetro.gov.co",
        "password": "conductor2026",
        "role": UserRole.CONDUCTOR.value,
        "assigned_bus": "TM-9301",
        "assigned_route": "A9-3"
    },
    "wilson.palacio@transmetro.gov.co": {
        "id": "usr-cond-05",
        "fullname": "Wilson Palacio Salcedo",
        "email": "wilson.palacio@transmetro.gov.co",
        "password": "conductor2026",
        "role": UserRole.CONDUCTOR.value,
        "assigned_bus": "TM-9304",
        "assigned_route": "A9-3"
    },
    # 3. Jefe de Ruta / Despachador CCO
    "jeferuta@transmetro.gov.co": {
        "id": "usr-jefe-01",
        "fullname": "Ing. Brenda Carvajal (CCO)",
        "email": "jeferuta@transmetro.gov.co",
        "password": "jeferuta2026",
        "role": UserRole.JEFE_RUTA.value,
        "assigned_bus": None,
        "assigned_route": None
    },
    # 4. Administrador General
    "admin@barranquilla.gov.co": {
        "id": "usr-adm-01",
        "fullname": "Secretaría Distrital de Tránsito y Seguridad Vial",
        "email": "admin@barranquilla.gov.co",
        "password": "adminbarranquilla",
        "role": UserRole.ADMIN.value,
        "assigned_bus": None,
        "assigned_route": None
    }
}

def get_current_user_optional(request: Request) -> dict | None:
    """
    Extrae el usuario actual a partir de un token JWT almacenado en la cookie 'access_token'.
    Retorna None si no hay token o si es inválido/expirado.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    email = payload.get("sub")
    if not email:
        return None

    # Primero buscar en la BD de Neon
    try:
        from app.database import SessionLocal
        from app.models import Usuario
        if SessionLocal:
            db = SessionLocal()
            try:
                db_user = db.query(Usuario).filter(Usuario.email == email).first()
                if db_user:
                    user_data = {
                        "id": db_user.id,
                        "fullname": db_user.fullname,
                        "email": db_user.email,
                        "password": db_user.password_hash,
                        "role": db_user.role,
                        "assigned_bus": db_user.assigned_bus_id,
                        "assigned_route": db_user.assigned_route_id
                    }
                    MOCK_USERS_DB[db_user.email] = user_data
                    return user_data
            finally:
                db.close()
    except Exception as db_err:
        print(f"[JWT Auth BD Fallback]: {db_err}")

    # Fallback a MOCK_USERS_DB
    return MOCK_USERS_DB.get(email)

def require_role(allowed_roles: List[UserRole]) -> Callable:
    def role_checker(request: Request):
        user = get_current_user_optional(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión expirada o no iniciada. Por favor inicie sesión."
            )
        if user["role"] not in [r.value for r in allowed_roles] and user["role"] != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Se requiere rol {', '.join([r.value for r in allowed_roles])}."
            )
        return user
    return role_checker

@router.post("/login")
def login(payload: UserLogin, response: Response):
    user = None
    input_user = payload.username_or_email.lower().strip()
    
    # 1. Intentar consultar en Neon PostgreSQL
    try:
        from app.database import SessionLocal
        from app.models import Usuario
        if SessionLocal:
            db = SessionLocal()
            try:
                db_user = db.query(Usuario).filter(Usuario.email.ilike(input_user)).first()
                if db_user:
                    user = {
                        "id": db_user.id,
                        "fullname": db_user.fullname,
                        "email": db_user.email,
                        "password": db_user.password_hash,
                        "role": db_user.role,
                        "assigned_bus": db_user.assigned_bus_id,
                        "assigned_route": db_user.assigned_route_id
                    }
                    # Sincronizar en memoria local
                    MOCK_USERS_DB[db_user.email] = user
            finally:
                db.close()
    except Exception as db_err:
        print(f"[BD Neon Login Fallback]: {db_err}")

    # 2. Si no se encontró por BD, buscar en MOCK_USERS_DB
    if not user:
        for email, u in MOCK_USERS_DB.items():
            if email.lower() == input_user:
                user = u
                break

    # 3. Verificar existencia y contraseña (soporta bcrypt y texto plano legacy)
    if not user or not verify_password(payload.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas. Verifique su correo y contraseña."
        )

    # Generar token JWT
    access_token = create_access_token(
        data={
            "sub": user["email"],
            "role": user["role"],
            "fullname": user["fullname"],
            "user_id": user["id"]
        }
    )
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        secure=IS_PRODUCTION  # True en producción (HTTPS), False en desarrollo
    )

    # Redirección calculada según rol
    redirect_map = {
        UserRole.PASAJERO.value: "/mapa",
        UserRole.CONDUCTOR.value: "/conductor",
        UserRole.JEFE_RUTA.value: "/jefe-ruta",
        UserRole.ADMIN.value: "/admin"
    }

    return {
        "status": "success",
        "message": f"Bienvenido, {user['fullname']}",
        "token": access_token,
        "redirect_url": redirect_map.get(user["role"], "/mapa"),
        "user": {
            "id": user["id"],
            "fullname": user["fullname"],
            "email": user["email"],
            "role": user["role"],
            "assigned_bus": user.get("assigned_bus"),
            "assigned_route": user.get("assigned_route")
        }
    }

@router.post("/register")
def register(payload: UserRegister, response: Response):
    user_email = payload.email.lower().strip()

    # Validar que las contraseñas coincidan
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las contraseñas no coinciden. Por favor verifique."
        )

    # Validar longitud mínima
    if len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 6 caracteres."
        )

    # Hash seguro de la contraseña con bcrypt
    hashed_password = get_password_hash(payload.password)

    # Verificar existencia en BD Neon y guardar
    db_saved = False
    new_id = f"usr-{str(uuid.uuid4())[:8]}"
    
    try:
        from app.database import SessionLocal
        from app.models import Usuario
        if SessionLocal:
            db = SessionLocal()
            try:
                existing = db.query(Usuario).filter(Usuario.email == user_email).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Este correo electrónico ya se encuentra registrado en el sistema."
                    )
                
                db_user = Usuario(
                    id=new_id,
                    fullname=payload.fullname,
                    email=user_email,
                    password_hash=hashed_password,  # ← bcrypt hash
                    role=payload.role.value,
                    assigned_bus_id=None,
                    assigned_route_id=None
                )
                db.add(db_user)
                db.commit()
                db_saved = True
                print(f"[BD Neon] Usuario registrado con bcrypt hash: {user_email}")
            finally:
                db.close()
    except HTTPException:
        raise
    except Exception as db_err:
        print(f"[BD Neon Register Fallback]: {db_err}")

    # También verificar en MOCK si no se guardó en BD
    if not db_saved and user_email in MOCK_USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este correo electrónico ya se encuentra registrado."
        )

    new_user = {
        "id": new_id,
        "fullname": payload.fullname,
        "email": user_email,
        "password": hashed_password,  # ← bcrypt hash en memoria también
        "role": payload.role.value,
        "assigned_bus": None,
        "assigned_route": None
    }
    MOCK_USERS_DB[user_email] = new_user

    # Generar token JWT
    access_token = create_access_token(
        data={
            "sub": user_email,
            "role": payload.role.value,
            "fullname": payload.fullname,
            "user_id": new_id
        }
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        secure=IS_PRODUCTION  # True en producción (HTTPS), False en desarrollo
    )

    redirect_map = {
        UserRole.PASAJERO.value: "/mapa",
        UserRole.CONDUCTOR.value: "/conductor",
        UserRole.JEFE_RUTA.value: "/jefe-ruta",
        UserRole.ADMIN.value: "/admin"
    }

    return {
        "status": "success",
        "message": "Registro completado exitosamente",
        "token": access_token,
        "redirect_url": redirect_map.get(payload.role.value, "/mapa"),
        "user": {
            "id": new_id,
            "fullname": payload.fullname,
            "email": payload.email,
            "role": payload.role.value
        }
    }

@router.get("/me")
def get_me(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    return {
        "id": user["id"],
        "fullname": user["fullname"],
        "email": user["email"],
        "role": user["role"],
        "assigned_bus": user.get("assigned_bus"),
        "assigned_route": user.get("assigned_route")
    }

@router.post("/logout")
def logout(request: Request, response: Response):
    response.delete_cookie("access_token")
    return {"status": "success", "message": "Sesión finalizada"}
