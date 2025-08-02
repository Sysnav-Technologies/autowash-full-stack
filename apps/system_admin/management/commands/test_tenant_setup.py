from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.core.tenant_models import Tenant
from apps.system_admin.views import setup_tenant_after_approval


class Command(BaseCommand):
    help = 'Test the tenant setup functionality'
    
    def add_arguments(self, parser):
        parser.add_argument('business_id', type=str, help='Business ID to test setup for')
    
    def handle(self, *args, **options):
        business_id = options['business_id']
        
        try:
            business = Tenant.objects.get(id=business_id)
            self.stdout.write(f"Testing tenant setup for: {business.name}")
            
            # Get a superuser to act as the approving admin
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                self.stdout.write(self.style.ERROR('No superuser found. Please create one first.'))
                return
            
            self.stdout.write(f"Using admin user: {admin_user.username}")
            
            # Test the setup
            success = setup_tenant_after_approval(business, admin_user)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Tenant setup successful for {business.name}'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Tenant setup failed for {business.name}'))
                
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Business with ID {business_id} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
