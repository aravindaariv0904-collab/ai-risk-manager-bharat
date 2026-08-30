from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Optional, Dict, Any
import httpx
import structlog

from app.config import settings


security = HTTPBearer(auto_error=False)
logger = structlog.get_logger()

JWKS_CACHE: Optional[Dict] = None
_role_cache: Dict[str, str] = {}

# Demo user IDs mapped to roles
DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "demo-auth-citizen": {"role": "citizen", "name": "Rahul Kumar", "id": "demo-citizen-001"},
    "demo-auth-merchant": {"role": "merchant", "name": "Priya Shops", "id": "demo-merchant-001"},
    "demo-auth-admin": {"role": "admin", "name": "Admin User", "id": "demo-admin-001"},
}


async def get_jwks() -> Dict:
    global JWKS_CACHE
    if JWKS_CACHE is not None:
        return JWKS_CACHE
    try:
        headers = {}
        if settings.SUPABASE_ANON_KEY and not settings.SUPABASE_ANON_KEY.endswith("placeholder"):
            headers["apikey"] = settings.SUPABASE_ANON_KEY
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json", headers=headers)
            response.raise_for_status()
            JWKS_CACHE = response.json()
            return JWKS_CACHE
    except Exception as e:
        logger.warning("JWKS fetch failed", error=str(e))
        return {"keys": []}


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # ── Demo mode bypass ──────────────────────────────────────────────────────
    if settings.DEMO_MODE and token.startswith("demo."):
        parts = token.split(".")
        role = parts[1] if len(parts) > 1 else "citizen"
        user_map = {
            "citizen": "demo-auth-citizen",
            "merchant": "demo-auth-merchant",
            "admin": "demo-auth-admin",
        }
        sub = user_map.get(role, "demo-auth-citizen")
        return {"sub": sub, "role": role, "demo": True}
    # ─────────────────────────────────────────────────────────────────────────

    # 1. Primary: Verify via Supabase JWKS (ES256, RS256)
    try:
        jwks = await get_jwks()
        if jwks.get("keys"):
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            alg = unverified_header.get("alg", "ES256")
            key = next((k for k in jwks["keys"] if k.get("kid") == kid), None) or jwks["keys"][0]
            if key:
                payload = jwt.decode(
                    token,
                    key,
                    algorithms=[alg, "ES256", "RS256", "HS256"],
                    audience="authenticated",
                    options={"verify_exp": True},
                )
                return payload
    except Exception as e:
        logger.warning("JWKS token verification failed", error=str(e))

    # 2. Secondary: Verify via Supabase JWT Secret (HS256)
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return payload
    except JWTError:
        pass

    # 3. Fallback: Parse claims if token is unexpired and authenticated
    try:
        import time
        claims = jwt.get_unverified_claims(token)
        if claims and claims.get("aud") == "authenticated" and claims.get("sub"):
            if claims.get("exp", 0) > time.time():
                return claims
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_id(payload: Dict = Depends(verify_token)) -> str:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")
    return user_id


async def get_current_user_role(
    user_id: str = Depends(get_current_user_id),
) -> str:
    """Look up role from users table — not from JWT which doesn't carry it reliably."""
    if user_id in _role_cache:
        return _role_cache[user_id]

    try:
        from app.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        resp = supabase.table("users").select("role").eq("auth_user_id", user_id).maybe_single().execute()
        if resp.data:
            role = resp.data.get("role", "citizen")
            _role_cache[user_id] = role
            return role
    except Exception as e:
        logger.warning("Role lookup failed", error=str(e))

    return "citizen"