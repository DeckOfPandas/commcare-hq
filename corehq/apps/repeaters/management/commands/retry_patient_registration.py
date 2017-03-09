import json

from django.core.management import BaseCommand

from corehq.apps.repeaters.dbaccessors import get_paged_repeat_records
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('logfile')

    def handle(self, logfile, **options):
        with open(logfile, "w") as f:
            register_patient_records = get_paged_repeat_records("enikshay-test", None, None, repeater_id="dc73c3da43d42acd964d80b287926833")
            already_exists_records = [
                x for x in register_patient_records if
                x.state == "CANCELLED" and 'beneficiary_id already exists' in (x.failure_reason or "")
            ]
            print "{} 'already exists' repeat records".format(len(already_exists_records))

            for record in already_exists_records:
                case = CaseAccessors("enikshay-test").get_case(record.payload_id)
                try:
                    payload = json.loads(record.get_payload())
                except Exception as e:
                    continue

                logline = "{}\t{}\t{}\t".format(
                    record._id,
                    payload.get('beneficiary_id', 'None'),
                    case.case_id
                )

                if case.get_dynamic_case_properties().get("dots_99_registered", False) == "true":
                    logline += "case says dots_99_registered already"
                else:
                    # record.fire()
                    if record.succeeded:
                        logline += "SUCCESS"
                    else:
                        logline += record.failure_reason

                print logline
                f.write(logline + "\n")
