from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import User


@receiver(pre_delete, sender=User)
def anonymize_votes_before_user_delete(sender, instance, **kwargs):
    """Kullanici nasil silinirse silinsin (site, admin paneli, toplu silme, shell) oylari kisiyle
    baglantisiz kalir: user=NULL, voter_key="d:<uuid>". Aksi halde admin'den silmede voter_key
    "u:<id>" olarak kalirdi."""
    from polls.utils import anonymize_votes  # polls, accounts'a bagli; dongusel ice aktarimi onler

    anonymize_votes(instance)
