from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from base.models import CustomUser


class Command(BaseCommand):
    help = 'Deletes guest users older than 24 hours'

    def handle(self, *args, **kwargs):
        cutoff = now() - timedelta(hours=12)
        guests_to_delete = CustomUser.objects.filter(is_guest=True, date_joined__lt=cutoff)
        deleted_count = guests_to_delete.count()
        guests_to_delete.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} guest users older than 24 hours."))
