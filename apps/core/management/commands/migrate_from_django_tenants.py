"""
Script to migrate from django-tenants to MySQL multi-tenant architecture
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connections
from django.contrib.auth.models import User
from apps.core.tenant_models import Tenant
import json


class Command(BaseCommand):
    help = 'Migrate from django-tenants to MySQL multi-tenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
        parser.add_argument(
            '--backup-file',
            type=str,
            help='JSON file to backup old tenant data',
            default='tenant_migration_backup.json'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        backup_file = options['backup_file']
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )
        
        self.stdout.write("Starting migration from django-tenants to MySQL...")
        
        # Step 1: Backup existing tenant data
        tenant_data = self.backup_tenant_data(backup_file)
        
        # Step 2: Create new Tenant objects
        self.create_new_tenants(tenant_data)
        
        self.stdout.write(
            self.style.SUCCESS("Migration completed successfully!")
        )

    def backup_tenant_data(self, backup_file):
        """Backup existing tenant data from django-tenants"""
        self.stdout.write("Backing up existing tenant data...")
        
        tenant_data = []
        
        try:
            # Try to import the old Business model
            from apps.accounts.models_old import Business as OldBusiness
            
            for business in OldBusiness.objects.all():
                data = {
                    'id': str(business.id),
                    'name': business.name,
                    'slug': business.slug,
                    'description': getattr(business, 'description', ''),
                    'business_type': getattr(business, 'business_type', 'car_wash'),
                    'registration_number': getattr(business, 'registration_number', ''),
                    'tax_number': getattr(business, 'tax_number', ''),
                    'phone': getattr(business, 'phone', ''),
                    'email': getattr(business, 'email', ''),
                    'website': getattr(business, 'website', ''),
                    'address_line_1': getattr(business, 'address_line_1', ''),
                    'address_line_2': getattr(business, 'address_line_2', ''),
                    'city': getattr(business, 'city', ''),
                    'state': getattr(business, 'state', ''),
                    'postal_code': getattr(business, 'postal_code', ''),
                    'country': getattr(business, 'country', 'KE'),
                    'opening_time': str(getattr(business, 'opening_time', '08:00')),
                    'closing_time': str(getattr(business, 'closing_time', '18:00')),
                    'timezone': getattr(business, 'timezone', 'Africa/Nairobi'),
                    'currency': getattr(business, 'currency', 'KES'),
                    'language': getattr(business, 'language', 'en'),
                    'is_active': getattr(business, 'is_active', True),
                    'is_verified': getattr(business, 'is_verified', False),
                    'owner_id': business.owner.id if hasattr(business, 'owner') else None,
                    'max_employees': getattr(business, 'max_employees', 5),
                    'max_customers': getattr(business, 'max_customers', 100),
                    'created_at': business.created_at.isoformat() if hasattr(business, 'created_at') else None,
                    'updated_at': business.updated_at.isoformat() if hasattr(business, 'updated_at') else None,
                }
                
                # Get domains
                domains = []
                if hasattr(business, 'domains'):
                    for domain in business.domains.all():
                        domains.append({
                            'domain': domain.domain,
                            'is_primary': domain.is_primary,
                        })
                data['domains'] = domains
                
                tenant_data.append(data)
            
            # Save backup
            if not self.dry_run:
                with open(backup_file, 'w') as f:
                    json.dump(tenant_data, f, indent=2)
                
                self.stdout.write(f"Backup saved to {backup_file}")
            
            self.stdout.write(f"Found {len(tenant_data)} tenants to migrate")
            
        except ImportError:
            self.stdout.write(
                self.style.WARNING("Could not import old Business model - skipping backup")
            )
            
        return tenant_data

    def create_new_tenants(self, tenant_data):
        """Create new Tenant objects from backup data"""
        self.stdout.write("Creating new Tenant objects...")
        
        created_count = 0
        
        for data in tenant_data:
            if self.dry_run:
                self.stdout.write(f"Would create tenant: {data['name']}")
                continue
            
            try:
                with transaction.atomic():
                    # Get owner
                    owner = None
                    if data['owner_id']:
                        try:
                            owner = User.objects.get(id=data['owner_id'])
                        except User.DoesNotExist:
                            self.stdout.write(
                                f"Warning: Owner {data['owner_id']} not found for {data['name']}"
                            )
                    
                    # Create tenant
                    tenant = Tenant(
                        name=data['name'],
                        slug=data['slug'],
                        description=data['description'],
                        business_type=data['business_type'],
                        registration_number=data['registration_number'],
                        tax_number=data['tax_number'],
                        phone=data['phone'],
                        email=data['email'],
                        website=data['website'],
                        address_line_1=data['address_line_1'],
                        address_line_2=data['address_line_2'],
                        city=data['city'],
                        state=data['state'],
                        postal_code=data['postal_code'],
                        country=data['country'],
                        opening_time=data['opening_time'],
                        closing_time=data['closing_time'],
                        timezone=data['timezone'],
                        currency=data['currency'],
                        language=data['language'],
                        is_active=data['is_active'],
                        is_verified=data['is_verified'],
                        max_employees=data['max_employees'],
                        max_customers=data['max_customers'],
                        owner=owner,
                        subdomain=data['slug'],  # Use slug as subdomain
                        database_user=f"user_{data['slug'].replace('-', '_')}"[:16],
                        database_password='change_me_' + data['slug'][:8],  # Temporary password
                    )
                    
                    tenant.save()
                    created_count += 1
                    
                    self.stdout.write(f"✓ Created tenant: {tenant.name}")
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error creating tenant {data['name']}: {str(e)}")
                )
        
        self.stdout.write(f"Created {created_count} new tenants")
