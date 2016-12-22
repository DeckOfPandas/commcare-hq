from django.db import models


class PatientDetail(models.Model):
    PregId = models.CharField(max_length=255, primary_key=True)
    scode = models.CharField(max_length=255, null=True)
    Dtocode = models.CharField(max_length=255, null=True)
    Tbunitcode = models.IntegerField()
    pname = models.CharField(max_length=255)
    pgender = models.CharField(
        max_length=255,
        choices=(
            ('F', 'F'),
            ('M', 'M'),
            ('T', 'T'),
        ),
    )
    page = models.CharField(max_length=255)
    poccupation = models.CharField(max_length=255)
    paadharno = models.BigIntegerField(null=True)
    paddress = models.CharField(max_length=255)
    pmob = models.CharField(max_length=255, null=True)  # validate numerical in factory
    plandline = models.CharField(max_length=255, null=True)
    ptbyr = models.CharField(max_length=255, null=True)  # dates, but not clean
    cname = models.CharField(max_length=255, null=True)
    caddress = models.CharField(max_length=255, null=True)
    cmob = models.CharField(max_length=255, null=True)  # validate numerical in factory
    clandline = models.CharField(max_length=255, null=True)
    cvisitedby = models.CharField(max_length=255, null=True)
    dcpulmunory = models.CharField(
        max_length=255,
        choices=(
            ('y', 'y'),
            ('Y', 'Y'),
            ('N', 'N'),
            ('P', 'P'),
        ),
    )
    dcexpulmunory = models.CharField(max_length=255)
    dcpulmunorydet = models.CharField(max_length=255, null=True)
    dotname = models.CharField(max_length=255, null=True)
    dotdesignation = models.CharField(max_length=255, null=True)
    dotmob = models.CharField(max_length=255, null=True)  # validate numerical in factory
    dotlandline = models.CharField(max_length=255, null=True)
    dotpType = models.CharField(max_length=255)
    dotcenter = models.CharField(max_length=255, null=True)
    PHI = models.IntegerField()
    dotmoname = models.CharField(max_length=255, null=True)
    dotmosdone = models.CharField(max_length=255)
    atbtreatment = models.CharField(
        max_length=255,
        choices=(
            ('Y', 'Y'),
            ('N', 'N'),
        ),
        null=True,
    )
    atbduration = models.CharField(max_length=255, null=True)  # some int, some # months poorly formatted
    atbsource = models.CharField(
        max_length=255,
        choices=(
            ('G', 'G'),
            ('N', 'N'),
            ('O', 'O'),
            ('P', 'P'),
        ),
        null=True,
    )
    atbregimen = models.CharField(max_length=255, null=True)
    atbyr = models.CharField(max_length=255, null=True)
    Ptype = models.CharField(max_length=255)
    pcategory = models.CharField(max_length=255)
    regBy = models.CharField(max_length=255)
    regDate = models.CharField(max_length=255)
    isRntcp = models.CharField(max_length=255)
    dotprovider_id = models.CharField(max_length=255)
    pregdate1 = models.DateField()
    cvisitedDate1 = models.CharField(max_length=255)
    InitiationDate1 = models.CharField(max_length=255)  # datetimes, look like they're all midnight
    dotmosignDate1 = models.CharField(max_length=255)

    @property
    def first_name(self):
        return self._list_of_names[0]

    @property
    def middle_name(self):
        return ' '.join(self._list_of_names[1:-1])

    @property
    def last_name(self):
        return self._list_of_names[-1]

    @property
    def _list_of_names(self):
        return self.pname.split(' ')

    @property
    def sex(self):
        return {
            'F': 'female',
            'M': 'male',
            'T': 'transgender'
        }[self.pgender]

    @property
    def disease_classification(self):
        pulmonary = 'pulmonary'
        extra_pulmonary = 'extra_pulmonary'
        return {
            'y': pulmonary,
            'Y': pulmonary,
            'P': pulmonary,
            'N': extra_pulmonary,
        }[self.dcpulmunory]

    @property
    def patient_type_choice(self):
        return {
            '1': 'new',
            '2': 'recurrent',
            '3': 'other_previously_treated',  # TODO - confirm
            '4': 'treatment_after_failure',
            '5': 'other_previously_treated',  # TODO - confirm
            '6': 'treatment_after_lfu',
            '7': 'transfer_in',
        }[self.Ptype]

    @property
    def treatment_supporter_designation(self):
        return {
            '1': 'health_worker',
            '2': 'tbhv',
            '3': 'asha_or_other_phi_hw',
            '4': 'aww',
            '5': 'ngo_volunteer',
            '6': 'private_medical_pracitioner',
            '7': 'other_community_volunteer',
        }[self.dotpType]

    @property
    def treatment_supporter_first_name(self):
        return ' '.join(self.dotname.split(' ')[:-1]) if len(self._list_of_dot_names) > 1 else ''

    @property
    def treatment_supporter_last_name(self):
        return self.dotname.split(' ')[-1]

    @property
    def _list_of_dot_names(self):
        return self.dotname.split(' ') if self.dotname else ['']


class Outcome(models.Model):
    PatientId = models.OneToOneField(PatientDetail, primary_key=True)
    Outcome = models.CharField(
        max_length=255,
        choices=(
            ('NULL', 'NULL'),
            ('0', '0'),
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4'),
            ('5', '5'),
            ('6', '6'),
            ('7', '7'),
        )
    )
    OutcomeDate = models.CharField(max_length=255, null=True)  # somethings DD/MM/YYYY, sometimes DD-MM-YYYY
    MO = models.CharField(max_length=255, null=True)  # doctor's name
    XrayEPTests = models.CharField(
        max_length=255,
        choices=(
            ('NULL', 'NULL'),
        ),
    )
    MORemark = models.CharField(max_length=255, null=True)  # doctor's notes
    HIVStatus = models.CharField(
        max_length=255,
        choices=(
            ('NULL', 'NULL'),
            ('Pos', 'Pos'),
            ('Neg', 'Neg'),
            ('Unknown', 'Unknown'),
        ),
        null=True,
    )
    HIVTestDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    CPTDeliverDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    ARTCentreDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    InitiatedOnART = models.IntegerField(
        choices=(
            (0, 0),
            (1, 1),
        ),
        null=True,
    )
    InitiatedDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    userName = models.CharField(max_length=255)
    loginDate = models.DateTimeField()
    OutcomeDate1 = models.CharField(max_length=255)  # datetimes and NULL


class Followup(models.Model):
    id = models.AutoField(primary_key=True)
    PatientID = models.ForeignKey(PatientDetail)
    IntervalId = models.CharField(max_length=255)
    TestDate = models.CharField(max_length=255, null=True)
    DMC = models.CharField(max_length=255)
    LabNo = models.CharField(max_length=255, null=True)
    SmearResult = models.CharField(max_length=255)
    PatientWeight = models.CharField(max_length=255)
    DmcStoCode = models.CharField(max_length=255)
    DmcDtoCode = models.CharField(max_length=255)
    DmcTbuCode = models.CharField(max_length=255)
    RegBy = models.CharField(max_length=255)
    regdate = models.CharField(max_length=255)


# class Household(models.Model):
#     PatientID = models.ForeignKey(APatientDetail)  # have to move to end of excel CSV
#     Name = models.CharField(max_length=255, null=True)
#     Dosage = models.CharField(max_length=255, null=True)
#     Weight = models.CharField(max_length=255, null=True)
#     M1 = models.CharField(max_length=255, null=True)
#     M2 = models.CharField(max_length=255, null=True)
#     M3 = models.CharField(max_length=255, null=True)
#     M4 = models.CharField(max_length=255, null=True)
#     M5 = models.CharField(max_length=255, null=True)
#     M6 = models.CharField(max_length=255, null=True)
