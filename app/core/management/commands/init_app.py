from allauth.socialaccount.models import SocialApp
from billing.models import init_subscription
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Init database'

    def handle(self, *args, **options):
        # Step 1 - Site
        site_count = Site.objects.count()
        if site_count != 1:
            self.stdout.write(
                self.style.ERROR(f'Could not configure the site, found {site_count} objects. Only one is expected'),
            )
        else:
            site = Site.objects.get(id=1)
            if site.domain != settings.SITE_DOMAIN or site.name != settings.SITE_DOMAIN:
                site.domain = settings.SITE_DOMAIN
                site.name = settings.SITE_DOMAIN
                site.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'The setting for the Site is complete.',
                    ),
                )
            # Step 2 - SocialApp
            app, created = SocialApp.objects.get_or_create(
                provider='vk',
                name='VK',
                client_id=settings.VK_OAUTH_ID,
                secret=settings.VK_OAUTH_SECRET,
            )
            if app.sites.count() == 0:
                app.sites.add(site)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'VK SocialApp setup is complete.',
                    ),
                )
        # Step 3 - Subscription
        init_subscription()
