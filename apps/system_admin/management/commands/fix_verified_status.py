"""
Management command to fix verification status for approved businesses
This fixes businesses that were approved before the is_verified flag was properly set
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.core.tenant_models import Tenant
from apps.accounts.models import BusinessVerification


class Command(BaseCommand):
    help = 'Fix verification status for approved businesses'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )
        parser.add_argument(
            '--business-id',
            type=int,
            help='Fix specific business ID only',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        business_id = options.get('business_id')
        
        self.stdout.write(f"{'DRY RUN: ' if dry_run else ''}Fixing verification status for approved businesses...")
        self.stdout.write("-" * 80)
        
        # Get approved businesses that are not marked as verified
        if business_id:
            businesses = Tenant.objects.filter(id=business_id, is_approved=True)
        else:
            businesses = Tenant.objects.filter(is_approved=True, is_verified=False)
        
        if not businesses.exists():
            self.stdout.write("No businesses need fixing.")
            return
        
        fixed_count = 0
        
        for business in businesses:
            self.stdout.write(f"Processing: {business.name}")
            
            if not dry_run:
                try:
                    with transaction.atomic():
                        # Set is_verified = True
                        business.is_verified = True
                        business.save()
                        
                        # Update or create BusinessVerification record
                        try:
                            verification = business.verification
                            if verification.status != 'verified':
                                verification.status = 'verified'
                                verification.verified_at = timezone.now()
                                verification.save()
                                self.stdout.write(f"  ✓ Updated BusinessVerification status to 'verified'")
                        except BusinessVerification.DoesNotExist:
                            # Create verification record
                            BusinessVerification.objects.create(
                                business=business,
                                status='verified',
                                verified_at=timezone.now(),
                                notes='Business verification fixed by management command'
                            )
                            self.stdout.write(f"  ✓ Created BusinessVerification record")
                        
                        self.stdout.write(f"  ✓ Set is_verified = True")
                        fixed_count += 1
                        
                except Exception as e:
                    self.stdout.write(f"  ✗ Error: {str(e)}")
            else:
                self.stdout.write(f"  → Would set is_verified = True")
                try:
                    verification = business.verification
                    if verification.status != 'verified':
                        self.stdout.write(f"  → Would update BusinessVerification status to 'verified'")
                except BusinessVerification.DoesNotExist:
                    self.stdout.write(f"  → Would create BusinessVerification record")
                fixed_count += 1
        
        self.stdout.write("-" * 80)
        if dry_run:
            self.stdout.write(f"DRY RUN: Would fix {fixed_count} businesses")
        else:
            self.stdout.write(f"Successfully fixed {fixed_count} businesses")
