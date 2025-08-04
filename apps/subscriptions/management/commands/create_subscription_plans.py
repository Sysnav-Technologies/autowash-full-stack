from django.core.management.base import BaseCommand
from apps.subscriptions.models import SubscriptionPlan
from decimal import Decimal

class Command(BaseCommand):
    help = 'Create initial subscription plans'

    def handle(self, *args, **options):
        self.stdout.write('Creating subscription plans...')
        
        # Monthly Plan
        monthly_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='monthly-plan',
            defaults={
                'name': 'Monthly Plan',
                'plan_type': 'monthly',
                'description': 'Ideal for startups and small businesses looking to get started with essential IT services.',
                'price': Decimal('500.00'),
                'duration_months': 1,
                'features': [
                    'Network Monitoring',
                    'Helpdesk Support (Limited Hours)',
                    'Basic Cybersecurity Protection'
                ],
                'max_employees': 5,
                'max_customers': 100,
                'max_services': 10,
                'storage_limit': 1000,
                'support_level': 'Basic',
                'network_monitoring': True,
                'helpdesk_support': 'Limited Hours',
                'cybersecurity_level': 'Basic',
                'backup_recovery': False,
                'onsite_support': False,
                'is_active': True,
                'is_popular': False
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Monthly Plan'))
        
        # Semi-Annual Plan
        semi_annual_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='semi-annual-plan',
            defaults={
                'name': 'Semi-Annual Plan',
                'plan_type': 'semi_annual',
                'description': 'Perfect for growing businesses that require additional features and support.',
                'price': Decimal('1350.00'),
                'duration_months': 6,
                'features': [
                    '24/7 Network Monitoring',
                    'Dedicated Helpdesk Support',
                    'Advanced Cybersecurity Protection',
                    'Cloud Backup & Recovery'
                ],
                'max_employees': 15,
                'max_customers': 500,
                'max_services': 25,
                'storage_limit': 5000,
                'support_level': 'Dedicated',
                'network_monitoring': True,
                'helpdesk_support': '24/7 Dedicated Support',
                'cybersecurity_level': 'Advanced',
                'backup_recovery': True,
                'onsite_support': False,
                'is_active': True,
                'is_popular': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Semi-Annual Plan'))
        
        # Annual Plan
        annual_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='annual-plan',
            defaults={
                'name': 'Annual Plan',
                'plan_type': 'annual',
                'description': 'Tailored for larger enterprises with complex IT needs and stringent security.',
                'price': Decimal('5000.00'),
                'duration_months': 12,
                'features': [
                    'Customised Network Monitoring',
                    'Priority Helpdesk Support',
                    'Comprehensive Cybersecurity Suite',
                    'Disaster Recovery Planning & Testing',
                    'Onsite Support (as needed)'
                ],
                'max_employees': -1,  # Unlimited
                'max_customers': -1,  # Unlimited
                'max_services': -1,   # Unlimited
                'storage_limit': -1,  # Unlimited
                'support_level': 'Priority Enterprise',
                'network_monitoring': True,
                'helpdesk_support': 'Priority Support',
                'cybersecurity_level': 'Comprehensive Suite',
                'backup_recovery': True,
                'onsite_support': True,
                'is_active': True,
                'is_popular': False
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Annual Plan'))
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created all subscription plans!')
        )
