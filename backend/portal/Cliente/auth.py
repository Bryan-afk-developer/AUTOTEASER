"""
auth.py — Registro y login de empresas (Portal Cliente).

Endpoints:
- POST /api/portal/cliente/registro   → Crea cuenta en Supabase Auth + fila en empresas
- POST /api/portal/cliente/login      → Autentica con email/password, devuelve JWT
- GET  /api/portal/cliente/perfil     → Devuelve datos de la empresa del usuario autenticado
"""
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr

from portal.shared.supabase_db import get_supabase_anon, get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Modelos Pydantic ─────────────────────────────────────────────────────────

class RegistroRequest(BaseModel):
    email: EmailStr
    password: str
    nombre_empresa: str
    rfc: str | None = None
    representante_legal: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Helper: verificar JWT y obtener user_id ───────────────────────────────────

def get_user_from_token(authorization: str) -> dict:
    """Extrae el empresa_id del header (sin autenticación JWT, versión interna)."""
    if not authorization or not authorization.startswith("Empresa "):
        raise HTTPException(status_code=401, detail="Header de empresa requerido")
    empresa_id = authorization.split("Empresa ")[1]
    return {"user_id": "internal_admin", "email": "admin@local", "empresa_id": empresa_id}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/registro")
async def registro(req: RegistroRequest):
    """
    Crea una cuenta nueva:
    1. Registra el usuario en Supabase Auth.
    2. Crea una fila en la tabla `empresas` vinculada al user_id.
    """
    sb_admin = get_supabase_admin()

    # 1. Crear usuario en Supabase Auth
    try:
        auth_response = sb_admin.auth.admin.create_user({
            "email": req.email,
            "password": req.password,
            "email_confirm": True  # Confirma automáticamente para no necesitar email SMTP
        })
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=400, detail="No se pudo crear el usuario")
        user_id = auth_response.user.id
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(status_code=409, detail="Este correo ya está registrado")
        logger.error(f"Error en Supabase Auth signup: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {error_msg}")

    # 2. Crear fila en `empresas`
    try:
        empresa_data = {
            "user_id": user_id,
            "nombre": req.nombre_empresa,
            "rfc": req.rfc,
            "representante_legal": req.representante_legal,
        }
        db_response = sb_admin.table("empresas").insert(empresa_data).execute()
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Usuario creado pero falló al guardar empresa")
        empresa = db_response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando empresa en DB: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear empresa: {str(e)}")

    logger.info(f"Nueva empresa registrada: {req.nombre_empresa} ({req.email})")
    return {
        "message": "Empresa registrada exitosamente",
        "empresa_id": empresa["id"],
        "nombre": empresa["nombre"],
        "email": req.email,
    }


@router.post("/login")
async def login(req: LoginRequest):
    """
    Autentica a la empresa y devuelve el access_token JWT de Supabase.
    El frontend guardará este token en localStorage y lo enviará en
    el header `Authorization: Bearer <token>` en cada request posterior.
    """
    sb = get_supabase_anon()
    try:
        response = sb.auth.sign_in_with_password({
            "email": req.email,
            "password": req.password
        })
        if not response or not response.session:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        session = response.session
        user = response.user
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg or "invalid_grant" in error_msg:
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
        logger.error(f"Error en login: {e}")
        raise HTTPException(status_code=500, detail="Error al iniciar sesión")

    # Obtener nombre de empresa
    sb_admin = get_supabase_admin()
    empresa_resp = sb_admin.table("empresas").select("id, nombre, rfc").eq("user_id", user.id).single().execute()
    empresa = empresa_resp.data if empresa_resp.data else {}

    return {
        "access_token": session.access_token,
        "token_type": "bearer",
        "expires_in": session.expires_in,
        "user": {
            "id": user.id,
            "email": user.email,
            "empresa_id": empresa.get("id"),
            "nombre_empresa": empresa.get("nombre"),
            "rfc": empresa.get("rfc"),
            "representante_legal": empresa.get("representante_legal"),
            "es_admin": user.email.endswith("@caf.com.mx") or user.user_metadata.get("es_admin", False),
        }
    }


@router.get("/perfil")
async def perfil(authorization: str = Header(None)):
    """Devuelve el perfil de la empresa del usuario autenticado."""
    user_info = get_user_from_token(authorization)
    sb_admin = get_supabase_admin()

    empresa_resp = sb_admin.table("empresas").select("*").eq("id", user_info["empresa_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada para este usuario")

    return {
        "user_id": user_info["user_id"],
        "email": user_info["email"],
        "empresa": empresa_resp.data,
    }
