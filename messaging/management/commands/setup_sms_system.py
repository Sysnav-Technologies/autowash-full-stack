from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from decimal import Decimal
from messaging.models import SMSProvider


class Command(BaseCommand):
    help = 'Complete SMS system setup for cPanel deployment'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-migrate',
            action='store_true',
            help='Skip running migrations (if already done)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of all data',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.HTTP_INFO('🚀 Starting SMS system deployment setup...')
        )
        
        try:
            # Step 1: Run migrations if needed
            if not options['skip_migrate']:
                self.stdout.write('📦 Running database migrations...')
                call_command('migrate', verbosity=0)
                self.stdout.write('✅ Migrations completed')
            
            # Step 2: Create SMS providers
            self.stdout.write('🔧 Setting up SMS providers...')
            call_command('populate_sms_providers', force=options['force'])
            
            # Step 3: Collect static files for production
            self.stdout.write('📂 Collecting static files...')
            call_command('collectstatic', interactive=False, verbosity=0)
            self.stdout.write('✅ Static files collected')
            
            # Step 4: Create superuser guidance
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.SUCCESS('🎉 SMS System Setup Complete!')
            )
            self.stdout.write('='*60)
            self.stdout.write(
                'Next steps for cPanel deployment:'
            )
            self.stdout.write(
                '1. Create superuser: python manage.py createsuperuser'
            )
            self.stdout.write(
                '2. Access admin: https://yourdomain.com/admin/'
            )
            self.stdout.write(
                '3. Configure SMS for tenants: https://yourdomain.com/system-admin/sms/'
            )
            self.stdout.write(
                '4. Test SMS functionality with a tenant'
            )
            self.stdout.write('='*60)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Setup failed: {str(e)}')
            )
            raise