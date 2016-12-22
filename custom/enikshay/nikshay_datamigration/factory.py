from datetime import datetime

from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_open_occurrence_case_from_person, get_open_episode_case_from_occurrence
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.nikshay_datamigration.models import Outcome, Followup


PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'
TEST_CASE_TYPE = 'test'


def validate_number(string_value):
    if string_value is None or string_value.strip() == '':
        return None
    else:
        return int(string_value)


class EnikshayCaseFactory(object):

    domain = None
    patient_detail = None

    def __init__(self, domain, patient_detail, nikshay_codes_to_location):
        self.domain = domain
        self.patient_detail = patient_detail
        self.case_accessor = CaseAccessors(domain)
        self.nikshay_codes_to_location = nikshay_codes_to_location

    @property
    def nikshay_id(self):
        return self.patient_detail.PregId

    @property
    @memoized
    def existing_person_case(self):
        """
        Get the existing person case for this nikshay ID, or None if no person case exists
        """
        matching_external_ids = self.case_accessor.get_cases_by_external_id(self.nikshay_id, case_type='person')
        if matching_external_ids:
            assert len(matching_external_ids) == 1
            return matching_external_ids[0]
        return None

    @property
    def creating_person_case(self):
        return self.existing_person_case is not None

    @property
    @memoized
    def existing_occurrence_case(self):
        """
        Get the existing occurrence case for this nikshay ID, or None if no occurrence case exists
        """
        if self.existing_person_case:
            try:
                return get_open_occurrence_case_from_person(
                    self.domain, self.existing_person_case.case_id
                )
            except ENikshayCaseNotFound:
                return None

    @property
    @memoized
    def existing_episode_case(self):
        """
        Get the existing episode case for this nikshay ID, or None if no episode case exists
        """
        if self.existing_occurrence_case:
            try:
                return get_open_episode_case_from_occurrence(
                    self.domain, self.existing_occurrence_case.case_id
                )
            except ENikshayCaseNotFound:
                return None

    def get_case_structures_to_create(self):
        person_structure = self.get_person_case_structure()
        ocurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(ocurrence_structure)
        test_structures = [
            self.get_test_case_structure(followup, ocurrence_structure) for followup in self._followups
        ]
        return [episode_structure] + test_structures

    def get_person_case_structure(self):
        kwargs = {
            'attrs': {
                'case_type': PERSON_CASE_TYPE,
                'external_id': self.nikshay_id,
                # 'owner_id': self._location.location_id,
                'update': {
                    'aadhaar_number': self.patient_detail.paadharno,
                    'age': self.patient_detail.page,
                    'age_entered': self.patient_detail.page,
                    'contact_phone_number': validate_number(self.patient_detail.pmob),
                    'current_address': self.patient_detail.paddress,
                    'current_address_district_choice': self.patient_detail.Dtocode,
                    'current_address_state_choice': self.patient_detail.scode,
                    'dob_known': 'no',
                    'first_name': self.patient_detail.first_name,
                    'last_name': self.patient_detail.last_name,
                    'middle_name': self.patient_detail.middle_name,
                    'name': self.patient_detail.pname,
                    'nikshay_id': self.nikshay_id,
                    'permanent_address_district_choice': self.patient_detail.Dtocode,
                    'permanent_address_state_choice': self.patient_detail.scode,
                    'phi': self.patient_detail.PHI,
                    'secondary_contact_name_address': (
                        (self.patient_detail.cname or '')
                        + ', '
                        + (self.patient_detail.caddress or '')
                    ),
                    'secondary_contact_phone_number': validate_number(self.patient_detail.cmob),
                    'sex': self.patient_detail.sex,
                    'tu_choice': self.patient_detail.Tbunitcode,

                    'migration_created_case': 'true',
                },
            },
        }

        if self.existing_person_case is not None:
            kwargs['case_id'] = self.existing_person_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    def get_occurrence_case_structure(self, person_structure):
        """
        This gets the occurrence case structure with a nested person case structure.
        """
        kwargs = {
            'attrs': {
                'case_type': OCCURRENCE_CASE_TYPE,
                'update': {
                    'name': 'Occurrence #1',
                    'nikshay_id': self.nikshay_id,
                    'occurrence_episode_count': 1,
                    'occurrence_id': datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3],
                    'migration_created_case': 'true',
                },
            },
            'indices': [CaseIndex(
                person_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=PERSON_CASE_TYPE,
            )],
        }
        if self._outcome:
            # TODO - store with correct value
            kwargs['attrs']['update']['hiv_status'] = self._outcome.HIVStatus

        if self.existing_occurrence_case:
            kwargs['case_id'] = self.existing_occurrence_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    def get_episode_case_structure(self, occurrence_structure):
        """
        This gets the episode case structure with a nested occurrence and person case structures
        inside of it.
        """
        kwargs = {
            'attrs': {
                'case_type': EPISODE_CASE_TYPE,
                'update': {
                    'date_reported': self.patient_detail.pregdate1,  # is this right?
                    'disease_classification': self.patient_detail.disease_classification,
                    'episode_type': 'confirmed_tb',
                    'patient_type_choice': self.patient_detail.patient_type_choice,
                    'treatment_supporter_designation': self.patient_detail.treatment_supporter_designation,
                    'treatment_supporter_first_name': self.patient_detail.treatment_supporter_first_name,
                    'treatment_supporter_last_name': self.patient_detail.treatment_supporter_last_name,
                    'treatment_supporter_mobile_number': validate_number(self.patient_detail.dotmob),

                    'migration_created_case': 'true',
                },
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }

        if self.existing_episode_case:
            kwargs['case_id'] = self.existing_episode_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    def get_test_case_structure(self, followup, occurrence_structure):
        kwargs = {
            'attrs': {
                'create': True,
                'case_type': TEST_CASE_TYPE,
                'update': {
                    'date_tested': followup.TestDate,

                    'migration_created_case': 'true',
                    'migration_followup_id': followup.id,
                },
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence_structure.attrs['case_type'],
            )],
            # this prevents creating duplicate occurrence data on creation of the test cases
            'walk_related': False,
        }

        if self.existing_occurrence_case:
            matching_test_case = next((
                extension_case for extension_case in self.case_accessor.get_cases([
                    index.referenced_id for index in
                    self.existing_occurrence_case.reverse_indices
                ])
                if (
                    extension_case.type == TEST_CASE_TYPE
                    and followup.id == int(extension_case.dynamic_case_properties().get('migration_followup_id', -1))
                )
            ), None)
            if matching_test_case:
                kwargs['case_id'] = matching_test_case.case_id
                kwargs['attrs']['create'] = False
            else:
                kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    @property
    @memoized
    def _outcome(self):
        zero_or_one_outcomes = list(Outcome.objects.filter(PatientId=self.patient_detail))
        if zero_or_one_outcomes:
            return zero_or_one_outcomes[0]
        else:
            return None

    @property
    @memoized
    def _followups(self):
        return Followup.objects.filter(PatientID=self.patient_detail)

    @property
    def _location(self):
        return self.nikshay_codes_to_location[self._nikshay_code]

    @property
    def _nikshay_code(self):
        return '-'.join(self.patient_detail.PregId.split('-')[:4])


def get_nikshay_codes_to_location(domain):
    return {
        location.metadata.get('nikshay_code'): location
        for location in SQLLocation.objects.filter(domain=domain)
        if 'nikshay_code' in location.metadata
    }
