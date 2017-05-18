import mock
import datetime
from django.test import TestCase

from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField, \
    FixtureDataItem, FieldList, FixtureItemField
from corehq.form_processor.tests.utils import FormProcessorTestUtils

from casexml.apps.case.mock import CaseFactory
from corehq.apps.users.models import CommCareUser
from corehq.apps.userreports.tasks import rebuild_indicators

from custom.enikshay.const import (
    DOSE_MISSED,
    DOSE_TAKEN_INDICATORS as DTIndicators,
    DOSE_UNKNOWN,
    DAILY_SCHEDULE_FIXTURE_NAME,
    SCHEDULE_ID_FIXTURE,
    HISTORICAL_CLOSURE_REASON,
)
from custom.enikshay.data_store import AdherenceDatastore
from custom.enikshay.tasks import EpisodeAdherenceUpdater, EpisodeUpdate
from custom.enikshay.tests.utils import (
    get_person_case_structure,
    get_adherence_case_structure,
    get_occurrence_case_structure,
    get_episode_case_structure
)


class TestAdherenceUpdater(TestCase):
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )

    @classmethod
    def setUpClass(cls):
        super(TestAdherenceUpdater, cls).setUpClass()
        cls._call_center_domain_mock.start()
        cls.domain = 'enikshay'
        cls.user = CommCareUser.create(
            cls.domain,
            "jon-snow@user",
            "123",
        )
        cls.setupFixtureData()
        cls.data_store = AdherenceDatastore(cls.domain)

    def setUp(self):
        super(TestAdherenceUpdater, self).setUp()
        self.factory = CaseFactory(domain=self.domain)
        self.person_id = u"person"
        self.occurrence_id = u"occurrence"
        self.episode_id = u"episode"
        self.case_updater = EpisodeAdherenceUpdater(self.domain)

    @classmethod
    def setupFixtureData(cls):
        cls.fixture_data = {
            'schedule1': '7',
            'schedule2': '14',
            'schedule3': '21',
        }
        cls.data_type = FixtureDataType(
            domain=cls.domain,
            tag=DAILY_SCHEDULE_FIXTURE_NAME,
            name=DAILY_SCHEDULE_FIXTURE_NAME,
            fields=[
                FixtureTypeField(
                    field_name=SCHEDULE_ID_FIXTURE,
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="doses_per_week",
                    properties=[]
                ),
            ],
            item_attributes=[],
        )
        cls.data_type.save()
        cls.data_items = []
        for _id, value in cls.fixture_data.iteritems():
            data_item = FixtureDataItem(
                domain=cls.domain,
                data_type_id=cls.data_type.get_id,
                fields={
                    SCHEDULE_ID_FIXTURE: FieldList(
                        field_list=[
                            FixtureItemField(
                                field_value=_id,
                            )
                        ]
                    ),
                    "doses_per_week": FieldList(
                        field_list=[
                            FixtureItemField(
                                field_value=value,
                            )
                        ]
                    )
                },
                item_attributes={},
            )
            data_item.save()
            cls.data_items.append(data_item)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.data_type.delete()
        for data_item in cls.data_items:
            data_item.delete()
        cls.data_store.adapter.drop_table()
        super(TestAdherenceUpdater, cls).tearDownClass()
        cls._call_center_domain_mock.stop()

    def tearDown(self):
        self.data_store.adapter.clear_table()
        FormProcessorTestUtils.delete_all_cases()

    def _create_episode_case(self, adherence_schedule_date_start, adherence_schedule_id):
        person = get_person_case_structure(
            self.person_id,
            self.user.user_id,
        )

        occurrence = get_occurrence_case_structure(
            self.occurrence_id,
            person
        )

        episode_structure = get_episode_case_structure(
            self.episode_id,
            occurrence,
            extra_update={
                'adherence_schedule_date_start': adherence_schedule_date_start,
                'adherence_schedule_id': adherence_schedule_id
            }
        )
        cases = {case.case_id: case for case in self.factory.create_or_update_cases([episode_structure])}
        return cases[self.episode_id]

    def _create_adherence_cases(self, adherence_cases):
        self.factory.create_or_update_cases([
            get_adherence_case_structure(
                "adherence{}".format(i),
                self.episode_id,
                adherence_date,
                extra_update={
                    "name": adherence_date,
                    "adherence_value": adherence_value,
                }
            )
            for (i, (adherence_date, adherence_value)) in enumerate(adherence_cases)
        ])

    def assert_update(self, input, output):
        update = self.calculate_adherence_update(input)
        self.assertDictEqual(
            update.update_json()['update'],
            output
        )

    def calculate_adherence_update(self, input):
        self.case_updater.purge_date = input[0]
        # setup episode and adherence cases
        adherence_schedule_date_start, adherence_schedule_id = input[1]
        adherence_cases = input[2]
        episode = self._create_episode_case(adherence_schedule_date_start, adherence_schedule_id)
        self._create_adherence_cases(adherence_cases)

        rebuild_indicators(self.data_store.datasource._id)
        self.data_store.adapter.refresh_table()

        return EpisodeUpdate(episode, self.case_updater)

    def test_adherence_schedule_date_start_late(self):
        #   Sample test case
        #   [
        #       (
        #           purge_date,
        #           (adherence_schedule_date_start, adherence_schedule_id),
        #           [
        #               (adherence_date, adherence_value),
        #               (adherence_date, adherence_value),
        #               ...
        #           ],
        #           {
        #               'aggregated_score_date_calculated': value
        #               'expected_doses_taken': value
        #               'aggregated_score_count_taken': value
        #           }
        #       ),
        #       ...
        #   ]

        self.assert_update(
            (
                datetime.date(2016, 1, 15),
                (datetime.date(2016, 1, 17), 'schedule1'),
                []
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 16),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                # 1 day before should be adherence_schedule_date_start,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 16),
                'adherence_total_doses_taken': 0
            }
        )

    def test_no_adherence_schedule_date_start(self):
        # if adherence_schedule_date_start then don't update
        self.assert_update(
            (
                datetime.date(2016, 1, 17),
                (None, 'schedule1'),
                []
            ),
            {
            }
        )

    def test_no_adherence_cases(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                # if no adherence_cases for the episode
                []
            ),
            {
                # 1 day before adherence_schedule_date_start
                'aggregated_score_date_calculated': datetime.date(2016, 1, 9),
                # set to zero
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_total_doses_taken': 0,
                # 1 day before should be adherence_schedule_date_start
                'adherence_latest_date_recorded': datetime.date(2016, 1, 9),
            }
        )

    def test_adherence_date_less_than_purge_date(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                # if adherence_date less than purge_date
                [(datetime.date(2016, 1, 15), DTIndicators[0])]
            ),
            {
                # set to latest adherence_date
                'aggregated_score_date_calculated': datetime.date(2016, 1, 15),
                # co-efficient (aggregated_score_date_calculated - adherence_schedule_date_start)
                'expected_doses_taken': int((5.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 15),
                'adherence_total_doses_taken': 1
            }
        )

    def test_adherence_date_greater_than_purge_date(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                # if adherence_date is less than adherence_schedule_date_start
                [(datetime.date(2016, 1, 22), DTIndicators[0])]
            ),
            {
                # should be purge_date
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                # co-efficient (aggregated_score_date_calculated - adherence_schedule_date_start)
                'expected_doses_taken': int((10.0 / 7) * int(self.fixture_data['schedule1'])),
                # no doses taken before aggregated_score_date_calculated
                'aggregated_score_count_taken': 0,
                # latest adherence taken date
                'adherence_latest_date_recorded': datetime.date(2016, 1, 22),
                # no doses taken before aggregated_score_date_calculated
                'adherence_total_doses_taken': 1
            }
        )

    def test_multiple_adherence_cases_all_greater(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    # same day, different time
                    (datetime.date(2016, 1, 21), DTIndicators[0]),
                    (datetime.date(2016, 1, 21), DOSE_UNKNOWN),
                    (datetime.date(2016, 1, 22), DTIndicators[0]),
                    (datetime.date(2016, 1, 24), DTIndicators[0]),
                ]
            ),
            {   # should be purge_date
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                # co-efficient (aggregated_score_date_calculated - adherence_schedule_date_start)
                'expected_doses_taken': int((10.0 / 7) * int(self.fixture_data['schedule1'])),
                # no dose taken before aggregated_score_date_calculated
                'aggregated_score_count_taken': 0,
                # latest recorded
                'adherence_latest_date_recorded': datetime.date(2016, 1, 24),
                # total 3 taken, unknown is not counted
                'adherence_total_doses_taken': 3
            }
        )

    def test_multiple_adherence_cases_all_less(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    # same day, different time. Set hours different so that case-id becomes different
                    (datetime.date(2016, 1, 11), DTIndicators[0]),
                    (datetime.date(2016, 1, 11), DOSE_UNKNOWN),
                    (datetime.date(2016, 1, 12), DTIndicators[0]),
                    (datetime.date(2016, 1, 14), DOSE_UNKNOWN),
                ]
            ),
            {   # set to latest adherence_date, exclude 14th because its unknown
                'aggregated_score_date_calculated': datetime.date(2016, 1, 12),
                'expected_doses_taken': int((2.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 12),
                'adherence_total_doses_taken': 2
            }
        )

    def test_unknown_adherence_data_less_and_greater(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 11), DTIndicators[0]),
                    (datetime.date(2016, 1, 12), DTIndicators[0]),
                    (datetime.date(2016, 1, 14), DOSE_UNKNOWN),
                    (datetime.date(2016, 1, 21), DOSE_UNKNOWN)
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 12),
                'expected_doses_taken': int((2.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 12),
                'adherence_total_doses_taken': 2
            }
        )

    def test_missed_adherence_dose(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 11), DTIndicators[0]),
                    (datetime.date(2016, 1, 12), DTIndicators[0]),
                    (datetime.date(2016, 1, 14), DOSE_UNKNOWN),
                    (datetime.date(2016, 1, 21), DOSE_MISSED)  # dose missed
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                'expected_doses_taken': int((10.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 21),
                'adherence_total_doses_taken': 2
            }
        )

    def test_two_doses_on_same_day(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    # same day, different time
                    (datetime.date(2016, 1, 11), DTIndicators[0]),
                    (datetime.date(2016, 1, 11), DTIndicators[0]),
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 11),
                'expected_doses_taken': int((1.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 11),
                'adherence_total_doses_taken': 1
            }
        )

    def test_two_doses_on_same_day_different_values(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 11), DTIndicators[0]),
                    (datetime.date(2016, 1, 11), DTIndicators[2]),
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 11),
                'expected_doses_taken': int((1.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 11),
                'adherence_total_doses_taken': 1
            }
        )

    def test_dose_unknown_less(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 11), DOSE_UNKNOWN),
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 9),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 9),
                'adherence_total_doses_taken': 0
            }
        )

    def test_dose_missed_less(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 11), DOSE_MISSED),
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 11),
                'expected_doses_taken': int((1.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 11),
                'adherence_total_doses_taken': 0
            }
        )

    def test_dose_unknown_greater(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 22), DOSE_UNKNOWN),
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 9),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 9),
                'adherence_total_doses_taken': 0
            }
        )

    def test_dose_missed_greater(self):
        self.assert_update(
            (
                datetime.date(2016, 1, 20),
                (datetime.date(2016, 1, 10), 'schedule1'),
                [
                    (datetime.date(2016, 1, 22), DOSE_MISSED),
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                'expected_doses_taken': int((10.0 / 7) * int(self.fixture_data['schedule1'])),
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 22),
                'adherence_total_doses_taken': 0
            }
        )

    def test_count_taken_by_day(self):
        episode_update = self.calculate_adherence_update((
            datetime.date(2016, 1, 20),
            (datetime.date(2016, 1, 10), 'schedule1'),
            []
        ))

        def dose_taken_by_day(cases):
            # cases a list of tuples
            # (case_id, adherence_date, modified_on, adherence_value, source, closed, closure_reason)
            return episode_update.calculate_doses_taken_by_day(
                [
                    {
                        'adherence_source': source,
                        'adherence_date': str(dose_date),  # the code expects string format
                        'adherence_value': dose_value,
                        'closed': closed,
                        'adherence_closure_reason': closure_reason,
                        'modified_on': modified_on,
                    }
                    for (_, dose_date, modified_on, dose_value, source, closed, closure_reason) in cases
                ]
            )

        ## test enikshay only source, open cases
        # not-taken - latest_modified_on case says no dose taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 21), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
                ('some_id', datetime.date(2016, 1, 21), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 21): False}
        )
        # taken - latest_modified_on case says dose taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 22), datetime.date(2016, 2, 22),
                 DTIndicators[0], 'enikshay', False, None),
                ('some_id', datetime.date(2016, 1, 22), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 22): True}
        )

        ## test enikshay only source, closed/closure_reason cases
        # not taken - as 1st case is not relevant because closed, closure_reason. 2nd case says no dose taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 23), datetime.date(2016, 2, 22),
                 DTIndicators[0], 'enikshay', True, None),
                ('some_id', datetime.date(2016, 1, 23), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 23): False}
        )
        # taken - as 1st case is not relevant because closed, closure_reason. 2nd case says dose taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 24), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'enikshay', True, None),
                ('some_id', datetime.date(2016, 1, 24), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 24): True}
        )
        # not taken - as 1st case is relevent case with latest_modified_on and says dose not taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 25), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'enikshay', True, HISTORICAL_CLOSURE_REASON),
                ('some_id', datetime.date(2016, 1, 25), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 25): False}
        )
        # taken - as 1st case is relevent case with latest_modified_on and says dose is taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 26), datetime.date(2016, 2, 22),
                 DTIndicators[0], 'enikshay', True, HISTORICAL_CLOSURE_REASON),
                ('some_id', datetime.date(2016, 1, 26), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 26): True}
        )

        ## test non-enikshay source only cases
        # not taken - non-enikshay source, so consider latest_modified_on
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 27), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'non-enikshay', True, 'a'),
                ('some_id', datetime.date(2016, 1, 27), datetime.date(2016, 2, 21),
                 DTIndicators[0], '99dots', False, None),
            ]),
            {datetime.date(2016, 1, 27): False}
        )
        # taken - non-enikshay source, so consider latest_modified_on
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 28), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 28), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, '99', False, None),
            ]),
            {datetime.date(2016, 1, 28): True}
        )

        ## test mix of enikshay, non-enikshay sources
        # taken - as enikshay source case says taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 29), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 29), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 29): True}
        )
        # not taken - as enikshay source case says not taken
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 1), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 1), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ]),
            {datetime.date(2016, 1, 1): False}
        )
        # not taken - as the only enikshay source case is closed without valid-reason
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 2), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 2), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', True, None),
            ]),
            {datetime.date(2016, 1, 2): False}
        )
        # taken - as the only enikshay source case is closed with right closure_reason
        self.assertDictEqual(
            dose_taken_by_day([
                ('some_id', datetime.date(2016, 1, 3), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 3), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', True, HISTORICAL_CLOSURE_REASON),
            ]),
            {datetime.date(2016, 1, 3): True}
        )
