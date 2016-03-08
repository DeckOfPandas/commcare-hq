from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.tanzania.reminders import LOSS_ADJUST_CONFIRM, SOH_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class ILSLossesAdjustmentsTest(ILSTestScript):

    def setUp(self):
        super(ILSLossesAdjustmentsTest, self).setUp()

    def test_losses_adjustments(self):
        sohs = {
            'id': 400,
            'dp': 569,
            'ip': 678
        }
        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < {0}
        """.format(unicode(SOH_CONFIRM))
        self.run_script(script)

        self.assertEqual(StockState.objects.count(), 3)
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

        script = """
            5551234 > um id -3 dp -5 ip 13
            5551234 < {0}
        """.format(unicode(LOSS_ADJUST_CONFIRM))
        self.run_script(script)

        self.assertEqual(StockState.objects.count(), 3)

        self.assertEqual(StockState.objects.get(sql_product__code="id").stock_on_hand, 397)
        self.assertEqual(StockState.objects.get(sql_product__code="dp").stock_on_hand, 564)
        self.assertEqual(StockState.objects.get(sql_product__code="ip").stock_on_hand, 691)

    def test_losses_adjustments_la_word(self):
        sohs = {
            'id': 400,
            'dp': 569,
            'ip': 678
        }

        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < {0}
        """.format(unicode(SOH_CONFIRM))
        self.run_script(script)

        self.assertEqual(StockState.objects.count(), 3)
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

        script = """
            5551234 > la id -3 dp -5 ip 13
            5551234 < {0}
        """.format(unicode(LOSS_ADJUST_CONFIRM))
        self.run_script(script)

        self.assertEqual(StockState.objects.count(), 3)

        self.assertEqual(StockState.objects.get(sql_product__code="id").stock_on_hand, 397)
        self.assertEqual(StockState.objects.get(sql_product__code="dp").stock_on_hand, 564)
        self.assertEqual(StockState.objects.get(sql_product__code="ip").stock_on_hand, 691)
