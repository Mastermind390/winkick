from django.core.management.base import BaseCommand
from base.save_market_data import evaluate_predictions  # Import your function

class Command(BaseCommand):
    help = 'evaluating predictions'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("checking predictions"))
        evaluate_predictions()
        self.stdout.write(self.style.SUCCESS("Done checking predicitons."))
# This command can be run using: