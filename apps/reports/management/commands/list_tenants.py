from django.core.management.base import BaseCommand
from apps.core.tenant_models import Tenant


class Command(BaseCommand):
    help = 'List all available tenants'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Available Tenants:'))
        
        tenants = Tenant.objects.filter(is_active=True)
        
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No active tenants found'))
            return
        
        for tenant in tenants:
            self.stdout.write(f'  - {tenant.name} (slug: {tenant.slug})')
        
        self.stdout.write(f'\nTotal: {tenants.count()} active tenants')
