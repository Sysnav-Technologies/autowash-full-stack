from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings


class Command(BaseCommand):
    help = 'Set up Google OAuth social application for django-allauth'

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=str,
            help='Google OAuth Client ID',
            required=True
        )
        parser.add_argument(
            '--client-secret',
            type=str,
            help='Google OAuth Client Secret',
            required=True
        )
        parser.add_argument(
            '--domain',
            type=str,
            default='localhost:8000',
            help='Domain for the site (default: localhost:8000)'
        )

    def handle(self, *args, **options):
        client_id = options['client_id']
        client_secret = options['client_secret']
        domain = options['domain']

        # Get or create the site
        try:
            site = Site.objects.get(id=settings.SITE_ID)
            site.domain = domain
            site.name = f'Autowash ({domain})'
            site.save()
            self.stdout.write(
                self.style.SUCCESS(f'Updated site: {site.name} ({site.domain})')
            )
        except Site.DoesNotExist:
            site = Site.objects.create(
                id=settings.SITE_ID,
                domain=domain,
                name=f'Autowash ({domain})'
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created site: {site.name} ({site.domain})')
            )

        # Create or update Google social app
        social_app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google OAuth',
                'client_id': client_id,
                'secret': client_secret,
            }
        )

        if not created:
            social_app.client_id = client_id
            social_app.secret = client_secret
            social_app.save()
            self.stdout.write(
                self.style.SUCCESS('Updated existing Google OAuth application')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Created new Google OAuth application')
            )

        # Associate the app with the site
        social_app.sites.add(site)
        social_app.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Google OAuth setup complete!\n'
                f'Client ID: {client_id}\n'
                f'Site: {site.domain}\n'
                f'Remember to add the following redirect URI to your Google Console:\n'
                f'http://{domain}/accounts/google/login/callback/ (for development)\n'
                f'https://{domain}/accounts/google/login/callback/ (for production)'
            )
        )
