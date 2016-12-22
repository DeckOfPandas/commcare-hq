from corehq.apps.reminders.models import SurveyKeyword
from corehq.apps.sms.models import Keyword, MigrationStatus
from dimagi.utils.couch.database import iter_docs_with_retry
from django.core.management.base import BaseCommand
from optparse import make_option


class Command(BaseCommand):
    args = ""
    help = ("Syncs all keywords stored in Couch to Postgres")
    option_list = BaseCommand.option_list + (
        make_option("--balance-only",
                    action="store_true",
                    dest="balance_only",
                    default=False,
                    help="Include this option to only run the balancing step."),
    )

    def get_couch_ids(self):
        result = SurveyKeyword.view(
            'reminders/survey_keywords',
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result]

    def get_couch_count(self):
        result = SurveyKeyword.view(
            'reminders/survey_keywords',
            include_docs=False,
            reduce=True,
        ).all()
        if result:
            return result[0]['value']
        return 0

    def get_sql_count(self):
        return Keyword.objects.count()

    def migrate(self, log_file):
        count = 0
        ids = self.get_couch_ids()
        total_count = len(ids)
        for doc in iter_docs_with_retry(SurveyKeyword.get_db(), ids):
            try:
                couch_obj = SurveyKeyword.wrap(doc)
                couch_obj._migration_do_sync()
            except Exception as e:
                log_file.write('Could not sync SurveyKeyword %s: %s\n' % (doc['_id'], e))

            count += 1
            if (count % 1000) == 0:
                print 'Processed %s / %s documents' % (count, total_count)

    def balance(self, log_file):
        sql_count = self.get_sql_count()
        couch_count = self.get_couch_count()

        log_file.write("%s / %s keywords migrated\n" % (sql_count, couch_count))
        if couch_count != sql_count:
            log_file.write("***ERROR: Counts do not match. Please investigate before continuing.\n")

    def handle(self, *args, **options):
        with open('keyword_migration.log', 'w') as f:
            if not options['balance_only']:
                self.migrate(f)
                MigrationStatus.set_migration_completed(MigrationStatus.MIGRATION_KEYWORDS)
            self.balance(f)
