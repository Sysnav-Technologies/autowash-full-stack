from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from messaging.models import SMSProvider


class Command(BaseCommand):
    help = 'Populate SMS providers for deployment (when migrations are gitignored)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of providers even if they exist',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Starting SMS provider population...')
        
        try:
            with transaction.atomic():
                self.create_sms_providers(force=options['force'])
                self.stdout.write(
                    self.style.SUCCESS('✅ SMS providers populated successfully!')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error populating SMS providers: {str(e)}')
            )
            raise
    
    def create_sms_providers(self, force=False):
        """Create initial SMS providers"""
        providers = [
            {
                'name': 'Host Pinnacle WhatsApp',
                'provider_type': 'host_pinnacle',
                'is_active': True,
                'is_default': False,
                'api_endpoint': 'https://api.hostpinnacle.co.ke',
                'rate_per_sms': Decimal('0.50'),
            },
            {
                'name': 'Africa\'s Talking SMS',
                'provider_type': 'africas_talking',
                'is_active': True,
                'is_default': False,
                'api_endpoint': 'https://api.africastalking.com',
                'rate_per_sms': Decimal('0.30'),
            },
            {
                'name': 'Twilio SMS',
                'provider_type': 'twilio',
                'is_active': True,
                'is_default': False,
                'api_endpoint': 'https://api.twilio.com',
                'rate_per_sms': Decimal('0.80'),
            },
            {
                'name': 'Autowash Default SMS',
                'provider_type': 'default',
                'is_active': True,
                'is_default': True,
                'api_endpoint': '',
                'rate_per_sms': Decimal('0.00'),
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for provider_data in providers:
            provider, created = SMSProvider.objects.get_or_create(
                provider_type=provider_data['provider_type'],
                defaults=provider_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'  ✅ Created: {provider.name}')
            elif force:
                # Update existing provider with new data
                for key, value in provider_data.items():
                    if key != 'provider_type':  # Don't update the lookup key
                        setattr(provider, key, value)
                provider.save()
                updated_count += 1
                self.stdout.write(f'  🔄 Updated: {provider.name}')
            else:
                self.stdout.write(f'  ⏭️  Exists: {provider.name}')
        
        if created_count > 0:
            self.stdout.write(f'Created {created_count} new SMS providers')
        if updated_count > 0:
            self.stdout.write(f'Updated {updated_count} existing SMS providers')
        if created_count == 0 and updated_count == 0:
            self.stdout.write('All SMS providers already exist (use --force to update)')