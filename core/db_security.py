"""Supabase `public` semasini Data API'ye karsi sertlestiren SQL yardimcilari.

Uygulama veritabanina yalnizca Django uzerinden, tablo sahibi rolle baglanir. Supabase'in `anon` ve
`authenticated` rolleri hicbir tabloya/diziye/fonksiyona erisememeli ve tum tablolarda RLS acik
olmali (politika yok: tablo sahibi etkilenmez, diger roller hicbir satir goremez).
Yalnizca PostgreSQL'de calisir; bu roller yoksa (yerel/duz Postgres) ilgili adimlar atlanir.
"""

API_ROLES = ("anon", "authenticated")


def is_postgres(connection):
    return connection.vendor == "postgresql"


def existing_api_roles(cursor):
    cursor.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", [list(API_ROLES)])
    found = {row[0] for row in cursor.fetchall()}
    return [role for role in API_ROLES if role in found]


def revoke_statements(role):
    # `role` yalnizca API_ROLES sabitinden gelir (kullanici girdisi degil).
    if role not in API_ROLES:
        raise ValueError(role)
    return [
        f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}",
        f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES FROM {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM {role}",
    ]


def revoke_api_access(cursor):
    """anon/authenticated yetkilerini kaldirir (idempotent). Islenen rolleri dondurur."""
    roles = existing_api_roles(cursor)
    for role in roles:
        for statement in revoke_statements(role):
            cursor.execute(statement)
    return roles


def public_tables(cursor):
    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    return [row[0] for row in cursor.fetchall()]


def enable_rls_on_all_tables(cursor, quote_name):
    """public semasindaki tum tablolarda RLS'i acar (idempotent). Tablo adlarini dondurur."""
    tables = public_tables(cursor)
    for table in tables:
        cursor.execute(f"ALTER TABLE public.{quote_name(table)} ENABLE ROW LEVEL SECURITY")
    return tables


def tables_without_rls(cursor):
    cursor.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
        ORDER BY c.relname
        """
    )
    return [row[0] for row in cursor.fetchall()]
