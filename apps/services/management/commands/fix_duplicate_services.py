from django.core.management.base import BaseCommand
from django.db.models import Count
from apps.services.models import Service


class Command(BaseCommand):
    help = 'Fix duplicate service names'

    def handle(self, *args, **options):
        # Find duplicates
        duplicates = Service.objects.values('name').annotate(
            name_count=Count('name')
        ).filter(name_count__gt=1)
        
        self.stdout.write(f"Found {len(duplicates)} duplicate service names")
        
        for duplicate in duplicates:
            name = duplicate['name']
            services = Service.objects.filter(name=name).order_by('id')
            
            self.stdout.write(f"Processing duplicate: {name} ({len(services)} instances)")
            
            # Keep the first one, rename the rest
            for i, service in enumerate(services[1:], start=2):
                new_name = f"{name} ({i})"
                self.stdout.write(f"  Renaming '{service.name}' to '{new_name}'")
                service.name = new_name
                service.save()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully fixed duplicate service names')
        )
