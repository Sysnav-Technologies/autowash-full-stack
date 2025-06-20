from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import get_tenant_model, schema_context, get_public_schema_name
from apps.payments.models import PaymentMethod
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create default payment methods for all tenants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-slug',
            type=str,
            help='Create payment methods for specific tenant only (optional)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing payment methods',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )
    
    def handle(self, *args, **options):
        tenant_slug = options.get('tenant_slug')
        overwrite = options.get('overwrite', False)
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Default payment methods configuration
        default_payment_methods = [
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
                'processing_fee_percentage': 0.00,
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
                'description': 'Payment via credit or debit card',
                'is_active': True,
                'is_online': True,
                'requires_verification': True,
                'processing_fee_percentage': 0.00,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 1.00,
                'maximum_amount': 1000000.00,
                'daily_limit': None,
                'icon': 'fas fa-credit-card',
                'color': '#007bff',
                'display_order': 3,
            },
            {
                'name': 'Bank Transfer',
                'method_type': 'bank_transfer',
                'description': 'Direct bank transfer payment',
                'is_active': True,
                'is_online': False,
                'requires_verification': True,
                'processing_fee_percentage': 0.00,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 100.00,
                'maximum_amount': 10000000.00,
                'daily_limit': None,
                'icon': 'fas fa-university',
                'color': '#6c757d',
                'display_order': 4,
            },
            {
                'name': 'Mobile Money (Other)',
                'method_type': 'mobile_money',
                'description': 'Other mobile money services (Airtel Money, T-Kash, etc.)',
                'is_active': False,  # Disabled by default
                'is_online': True,
                'requires_verification': True,
                'processing_fee_percentage': 0.00,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 1.00,
                'maximum_amount': 50000.00,
                'daily_limit': 150000.00,
                'icon': 'fas fa-mobile',
                'color': '#ffc107',
                'display_order': 5,
            },
            {
                'name': 'Cheque',
                'method_type': 'cheque',
                'description': 'Payment by cheque',
                'is_active': False,  # Disabled by default
                'is_online': False,
                'requires_verification': True,
                'processing_fee_percentage': 0.00,
                'fixed_processing_fee': 0.00,
                'minimum_amount': 1000.00,
                'maximum_amount': 10000000.00,
                'daily_limit': None,
                'icon': 'fas fa-file-invoice-dollar',
                'color': '#dc3545',
                'display_order': 6,
            },
        ]
        
        # Get tenant model
        TenantModel = get_tenant_model()
        
        if tenant_slug:
            # Process specific tenant
            try:
                tenant = TenantModel.objects.get(slug=tenant_slug, is_active=True)
                tenants = [tenant]
                self.stdout.write(f"Processing tenant: {tenant.name}")
            except TenantModel.DoesNotExist:
                raise CommandError(f"Tenant with slug '{tenant_slug}' not found or inactive")
        else:
            # Process all active tenants (excluding public schema)
            tenants = TenantModel.objects.filter(
                is_active=True
            ).exclude(
                schema_name=get_public_schema_name()
            )
            self.stdout.write(f"Processing {tenants.count()} active tenants...")
        
        success_count = 0
        error_count = 0
        
        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    self.stdout.write(f"\n--- Processing {tenant.name} ({tenant.slug}) ---")
                    
                    if dry_run:
                        # Check what exists
                        existing_methods = PaymentMethod.objects.all()
                        self.stdout.write(f"Existing payment methods: {existing_methods.count()}")
                        for method in existing_methods:
                            self.stdout.write(f"  - {method.name} ({method.method_type})")
                        
                        self.stdout.write(f"Would create {len(default_payment_methods)} payment methods")
                        continue
                    
                    with transaction.atomic():
                        created_count = 0
                        updated_count = 0
                        skipped_count = 0
                        
                        for method_data in default_payment_methods:
                            method_name = method_data['name']
                            method_type = method_data['method_type']
                            
                            # Check if method already exists
                            existing_method = PaymentMethod.objects.filter(
                                method_type=method_type
                            ).first()
                            
                            if existing_method:
                                if overwrite:
                                    # Update existing method
                                    for key, value in method_data.items():
                                        setattr(existing_method, key, value)
                                    existing_method.save()
                                    updated_count += 1
                                    self.stdout.write(
                                        self.style.SUCCESS(f"  ✓ Updated: {method_name}")
                                    )
                                else:
                                    skipped_count += 1
                                    self.stdout.write(
                                        self.style.WARNING(f"  - Skipped: {method_name} (already exists)")
                                    )
                            else:
                                # Create new method
                                PaymentMethod.objects.create(**method_data)
                                created_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"  ✓ Created: {method_name}")
                                )
                        
                        self.stdout.write(
                            f"Summary for {tenant.name}: "
                            f"Created: {created_count}, "
                            f"Updated: {updated_count}, "
                            f"Skipped: {skipped_count}"
                        )
                        
                        success_count += 1
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Error processing {tenant.name}: {str(e)}")
                )
                logger.error(f"Error creating payment methods for tenant {tenant.slug}: {str(e)}")
                continue
        
        # Final summary
        self.stdout.write("\n" + "="*50)
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN COMPLETED - No changes were made")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Payment methods creation completed!\n"
                    f"Successful tenants: {success_count}\n"
                    f"Failed tenants: {error_count}"
                )
            )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"There were {error_count} errors. Check logs for details."
                )
            )

    def create_payment_gateway_configs(self, tenant):
        """Optional: Create default payment gateway configurations"""
        from apps.payments.models import PaymentGateway
        
        # This is optional - you can add default gateway configs here
        # For now, we'll skip this as it requires API credentials
        pass