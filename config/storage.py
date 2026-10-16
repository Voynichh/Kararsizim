from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Dosya adlarina icerik ozeti (hash) ekler: main.css -> main.<12 hane>.css.

    Boylece her deploy'da degisen dosya yeni bir adla gelir, tarayici/CDN eski CSS-JS'i tutmaz ve
    dosyalar "immutable" (1 yil) onbelleklenebilir.

    Bagisleyici: Django'nun `manifest_strict=False` ayari yalnizca "dosya var ama manifestte yok"
    durumunu affeder; dosya STATIC_ROOT'ta hic yoksa (collectstatic calismamis ortam, testler, manifest
    calisma ortamina tasinmamis) yine ValueError verir ve TUM sayfalari cokertirdi. Burada bu durumda
    hash'siz adrese dusulur; orijinal dosyalar collectstatic ciktisinda zaten bulunur.
    """

    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name
