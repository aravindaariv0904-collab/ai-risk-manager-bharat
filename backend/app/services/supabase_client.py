from app.config import settings


_supabase_admin = None
_supabase_anon = None


def get_supabase_admin():
    global _supabase_admin
    if _supabase_admin is None:
        from supabase import create_client
        _supabase_admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_admin


def get_supabase_anon():
    global _supabase_anon
    if _supabase_anon is None:
        from supabase import create_client
        _supabase_anon = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _supabase_anon