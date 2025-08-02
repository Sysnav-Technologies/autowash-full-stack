from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connections
from apps.core.tenant_models import Tenant
from apps.payments.models import PaymentMethod
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create default payment methods for all tenants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-slug',
            type=str,
            help='Specific tenant slug to create payment methods for',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of payment methods (delete existing)',
        )
    
    def get_default_payment_methods(self):
        """Return default payment methods data"""
        return [
            {
                'name': 'Cash Payment',
                'method_type': 'cash',
                'description': 'Cash payment at point of service',
                'is_active': True,
                'is_online': False,
                'requires_verification': False,
                'processing_fee_percentage': 0.00,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 1.00,
                'maximum_amount': 100000.00,
                'daily_limit': None,
                'icon': 'fas fa-money-bill-wave',
                'color': '#28a745',
                'display_order': 1,
            },
            {
                'name': 'M-Pesa',
                'method_type': 'mpesa',
                'description': 'Mobile money payment via M-Pesa',
                'is_active': True,
                'is_online': True,
                'requires_verification': True,
                'processing_fee_percentage': 1.5,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 1.00,
                'maximum_amount': 70000.00,
                'daily_limit': 300000.00,
                'icon': 'fas fa-mobile-alt',
                'color': '#00a651',
                'display_order': 2,
            },
            {
                'name': 'Credit/Debit Card',
                'method_type': 'card',
                'description': 'Visa, MasterCard, and other cards',
                'is_active': True,
                'is_online': True,
                'requires_verification': True,
                'processing_fee_percentage': 2.9,
                'fixed_processing_fee': 30.00,
                'minimum_amount': 1.00,
                'maximum_amount': 500000.00,
                'daily_limit': None,
                'icon': 'fas fa-credit-card',
                'color': '#007bff',
                'display_order': 3,
            },
            {
                'name': 'Bank Transfer',
                'method_type': 'bank_transfer',
                'description': 'Direct bank transfer',
                'is_active': True,
                'is_online': False,
                'requires_verification': True,
                'processing_fee_percentage': 0.00,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 100.00,
                'maximum_amount': 1000000.00,
                'daily_limit': None,
                'icon': 'fas fa-university',
                'color': '#6c757d',
                'display_order': 4,
            },
        ]

    def create_payment_methods_for_tenant(self, tenant, force=False):
        """Create payment methods for a specific tenant"""
        db_alias = tenant.get_database_name()
        
        if force:
            # Delete existing payment methods
            PaymentMethod.objects.using(db_alias).all().delete()
            self.stdout.write(f"Deleted existing payment methods for tenant: {tenant.schema_name}")
        
        created_count = 0
        for method_data in self.get_default_payment_methods():
            # Check if payment method already exists
            if not PaymentMethod.objects.using(db_alias).filter(
                method_type=method_data['method_type']
            ).exists():
                PaymentMethod.objects.using(db_alias).create(**method_data)
                created_count += 1
                
        return created_count

    def handle(self, *args, **options):
        tenant_slug = options.get('tenant_slug')
        force = options.get('force', False)
        
        try:
            if tenant_slug:
                # Create for specific tenant
                try:
                    tenant = Tenant.objects.get(schema_name=tenant_slug)
                    
                    with transaction.atomic():
                        created_count = self.create_payment_methods_for_tenant(tenant, force)
                        
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully created {created_count} payment methods for tenant: {tenant.schema_name}'
                        )
                    )
                except Tenant.DoesNotExist:
                    raise CommandError(f'Tenant with slug "{tenant_slug}" does not exist')
            else:
                # Create for all tenants
                tenants = Tenant.objects.all()
                total_created = 0
                
                for tenant in tenants:
                    try:
                        with transaction.atomic():
                            created_count = self.create_payment_methods_for_tenant(tenant, force)
                            total_created += created_count
                            
                        self.stdout.write(f'Created {created_count} payment methods for tenant: {tenant.schema_name}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Failed to create payment methods for tenant {tenant.schema_name}: {str(e)}')
                        )
                        
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created {total_created} payment methods across all tenants')
                )
                
        except Exception as e:
            logger.error(f"Error creating payment methods: {str(e)}")
            raise CommandError(f'Error creating payment methods: {str(e)}')