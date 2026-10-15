from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core import db_security


class Command(BaseCommand):
    help = (
        "Supabase public semasini sertlestirir: anon/authenticated yetkilerini kaldirir ve "
        "tum tablolarda RLS'i acar. Idempotenttir; migrate ve createcachetable sonrasinda "
        "her deploy'da calistirilir. SQLite'ta bir sey yapmaz."
    )

    def handle(self, *args, **options):
        if not db_security.is_postgres(connection):
            self.stdout.write("PostgreSQL kullanılmıyor; secure_db atlandı.")
            return

        with connection.cursor() as cursor:
            roles = db_security.revoke_api_access(cursor)
            tables = db_security.enable_rls_on_all_tables(cursor, connection.ops.quote_name)
            missing = db_security.tables_without_rls(cursor)

        if roles:
            self.stdout.write(f"Yetkiler kaldırıldı: {', '.join(roles)}")
        else:
            self.stdout.write("anon/authenticated rolleri bulunamadı (Supabase dışı veritabanı); yetki adımı atlandı.")
        self.stdout.write(f"RLS açıldı: {len(tables)} tablo")

        if missing:
            raise CommandError(f"RLS kapalı kalan tablolar: {', '.join(missing)}")
        self.stdout.write(self.style.SUCCESS("secure_db tamam: public şemasındaki tüm tablolarda RLS açık."))
