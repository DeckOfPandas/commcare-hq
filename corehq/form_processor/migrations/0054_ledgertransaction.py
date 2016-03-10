# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import corehq.form_processor.models
from corehq.sql_db.operations import HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0053_add_deletion_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='LedgerTransaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(max_length=255)),
                ('server_date', models.DateTimeField()),
                ('type', models.PositiveSmallIntegerField(choices=[(1, b'balance'), (2, b'transfer')])),
                ('case_id', models.CharField(default=None, max_length=255)),
                ('entry_id', models.CharField(default=None, max_length=100)),
                ('section_id', models.CharField(default=None, max_length=100)),
                ('user_defined_type', corehq.form_processor.models.TruncatingCharField(max_length=20, null=True, blank=True)),
                ('delta', models.IntegerField(default=0)),
                ('updated_balance', models.IntegerField(default=0)),
            ],
            options={
            },
            bases=(corehq.form_processor.models.DisabledDbMixin, models.Model),
        ),
        migrations.AlterField(
            model_name='ledgertransaction',
            name='case_id',
            field=models.CharField(default=None, max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgertransaction',
            name='entry_id',
            field=models.CharField(default=None, max_length=100, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgertransaction',
            name='section_id',
            field=models.CharField(default=None, max_length=100, db_index=True),
            preserve_default=True,
        ),
        # drop unused indexes
        HqRunSQL(
            "DROP INDEX IF EXISTS form_processor_ledgervalue_case_id_6787b84005e3c4e0_like",
            "SELECT 1"
        ),
        HqRunSQL(
            "DROP INDEX IF EXISTS form_processor_ledgervalue_entry_id_7ba5b60783fc16d1_like",
            "SELECT 1"
        ),
        HqRunSQL(
            "DROP INDEX IF EXISTS form_processor_ledgervalue_section_id_7e237eaaa0c800ea_like",
            "SELECT 1"
        )
    ]
