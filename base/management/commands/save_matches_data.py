from django.core.management.base import BaseCommand
from base.utils.scrape import save_match_to_db  # Import your function

class Command(BaseCommand):
    help = 'Fetch and save matches data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Saving matches data..."))
        save_match_to_db()
        self.stdout.write(self.style.SUCCESS("Done saving matches data."))
# This command can be run using: