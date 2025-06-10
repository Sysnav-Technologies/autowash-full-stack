from django.core.management.base import BaseCommand
from apps.employees.models import Department, Position

class Command(BaseCommand):
    help = 'Create default positions for the business'

    def handle(self, *args, **kwargs):
        # Create or get departments
        departments = {
            'Administration': {
                'description': 'Administrative and support staff',
                'positions': [
                    {'title': 'Office Administrator', 'min_salary': 30000, 'max_salary': 50000},
                    {'title': 'Receptionist', 'min_salary': 25000, 'max_salary': 40000},
                    {'title': 'HR Officer', 'min_salary': 40000, 'max_salary': 70000},
                ]
            },
            'Finance': {
                'description': 'Financial operations and accounting',
                'positions': [
                    {'title': 'Finance Manager', 'min_salary': 70000, 'max_salary': 120000},
                    {'title': 'Accountant', 'min_salary': 50000, 'max_salary': 90000},
                    {'title': 'Accounts Assistant', 'min_salary': 30000, 'max_salary': 50000},
                ]
            },
            'Sales': {
                'description': 'Sales and customer acquisition',
                'positions': [
                    {'title': 'Sales Manager', 'min_salary': 60000, 'max_salary': 120000},
                    {'title': 'Sales Representative', 'min_salary': 30000, 'max_salary': 70000},
                    {'title': 'Customer Service', 'min_salary': 25000, 'max_salary': 45000},
                ]
            },
            'IT': {
                'description': 'Information technology services',
                'positions': [
                    {'title': 'IT Manager', 'min_salary': 80000, 'max_salary': 140000},
                    {'title': 'Systems Administrator', 'min_salary': 50000, 'max_salary': 90000},
                    {'title': 'IT Support', 'min_salary': 35000, 'max_salary': 60000},
                ]
            },
            'Operations': {
                'description': 'Business operations and logistics',
                'positions': [
                    {'title': 'Operations Supervisor', 'min_salary': 45000, 'max_salary': 75000},
                    {'title': 'Logistics Coordinator', 'min_salary': 35000, 'max_salary': 60000},
                    {'title': 'Warehouse Staff', 'min_salary': 25000, 'max_salary': 40000},
                ]
            },
            'Marketing': {
                'description': 'Marketing and communications',
                'positions': [
                    {'title': 'Marketing Manager', 'min_salary': 65000, 'max_salary': 110000},
                    {'title': 'Digital Marketing Specialist', 'min_salary': 45000, 'max_salary': 80000},
                    {'title': 'Graphic Designer', 'min_salary': 35000, 'max_salary': 65000},
                ]
            },
        }

        created_count = 0
        
        for dept_name, dept_data in departments.items():
            # Get or create department
            department, created = Department.objects.get_or_create(
                name=dept_name,
                defaults={'description': dept_data['description'], 'is_active': True}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created department: {dept_name}'))
            
            # Create positions for this department
            for position_data in dept_data['positions']:
                position, created = Position.objects.get_or_create(
                    title=position_data['title'],
                    department=department,
                    defaults={
                        'min_salary': position_data['min_salary'],
                        'max_salary': position_data['max_salary'],
                        'is_active': True
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Created position: {position_data["title"]} in {dept_name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Position already exists: {position_data["title"]} in {dept_name}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} positions across {len(departments)} departments'))