from django.db import migrations

from core.db_security import is_postgres, revoke_api_access


def revoke_access(apps, schema_editor):
    # Yalnizca PostgreSQL'de ve Supabase rolleri (anon/authenticated) varsa calisir.
    if not is_postgres(schema_editor.connection):
        return
    with schema_editor.connection.cursor() as cursor:
        revoke_api_access(cursor)


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(revoke_access, migrations.RunPython.noop),
    ]
