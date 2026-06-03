"""
supabase_db.py — Clientes de Supabase compartidos para todo el portal.

Provee dos clientes:
- `supabase_anon`: Usa la publishable key. Respeta RLS. Usado para verificar JWTs de usuarios.
- `supabase_admin`: Usa la service_role key. Bypassa RLS. Usado para operaciones de admin y escritura confiable.
"""
import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def get_supabase_anon() -> Client:
    """Cliente con anon/publishable key — respeta Row Level Security."""
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_PUBLISHABLE_KEY en .env")
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)


def get_supabase_admin() -> Client:
    """Cliente con service_role key — bypassa RLS. Solo para uso interno del backend."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# Alias convenientes
supabase_anon: Client = None   # se inicializa en startup
supabase_admin: Client = None  # se inicializa en startup


def init_supabase():
    """Llamar desde el startup event de FastAPI para inicializar los clientes."""
    global supabase_anon, supabase_admin
    supabase_anon = get_supabase_anon()
    supabase_admin = get_supabase_admin()
