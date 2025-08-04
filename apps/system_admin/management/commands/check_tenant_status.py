from django.core.management.base import BaseCommand
from apps.core.tenant_models import Tenant


class Command(BaseCommand):
    help = 'Check the database status of all tenants'
    
    def handle(self, *args, **options):
        tenants = Tenant.objects.filter(is_approved=True)
        
        self.stdout.write(f"Checking database status for {tenants.count()} approved businesses:")
        self.stdout.write("-" * 80)
        
        for business in tenants:
            try:
                db_exists = business.tenant_database_exists()
                status = "✓ Active" if db_exists else "✗ Missing"
                self.stdout.write(f"{business.name:<30} | {status}")
            except Exception as e:
                self.stdout.write(f"{business.name:<30} | Error: {str(e)}")
        
        self.stdout.write("-" * 80)
        self.stdout.write("Status check complete.")
