from django.core.management.base import BaseCommand
from base.save_market_data import save_market_data  # Import your function

class Command(BaseCommand):
    help = 'Fetch and save market data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Saving market data..."))
        save_market_data()
        self.stdout.write(self.style.SUCCESS("Done saving market data."))
# This command can be run using: