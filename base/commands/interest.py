from django.core.management.base import BaseCommand
from base.save_market_data import calculate_interest  # Import your function

class Command(BaseCommand):
    help = 'calculating users investment interest'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("start calculating..."))
        calculate_interest()
        self.stdout.write(self.style.SUCCESS("Done calculating."))