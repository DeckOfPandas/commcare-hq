'''
This files defines ETL objects that all have a common "load" function.
Each object is meant for transferring one type of data to another type.
'''
import os

from django.db import connections
from django.conf import settings
from django.template import Context, engines

from corehq.warehouse.utils import django_batch_records
from corehq.sql_db.routers import db_for_read_write


class BaseETLMixin(object):

    @classmethod
    def load(cls, start_datetime, end_datetime):
        raise NotImplementedError


class CustomSQLETLMixin(BaseETLMixin):
    '''
    Mixin for transferring data from a SQL store to another SQL store using
    a custom SQL script.
    '''

    @classmethod
    def additional_sql_context(cls):
        '''
        Override this method to provide additional context
        vars to the SQL script
        '''
        return {}

    @classmethod
    def load(cls, start_datetime, end_datetime):
        from corehq.warehouse.models.shared import WarehouseTable
        '''
        Bulk loads records for a dim or fact table from
        their corresponding dependencies
        '''

        assert issubclass(cls, WarehouseTable)
        database = db_for_read_write(cls)
        with connections[database].cursor() as cursor:
            cursor.execute(cls._sql_query_template(cls.slug, start_datetime, end_datetime))

    @classmethod
    def _table_context(cls, start_datetime, end_datetime):
        '''
        Get a dict of slugs to table name mapping
        :returns: Dict of slug to table_name
        {
            <slug>: <table_name>,
            ...
        }
        '''
        from corehq.warehouse.models import get_cls_by_slug

        context = {cls.slug: cls._meta.db_table}
        for dep in cls.dependencies():
            dep_cls = get_cls_by_slug(dep)
            context[dep] = dep_cls._meta.db_table
        context['start_datetime'] = start_datetime.isoformat()
        context['end_datetime'] = end_datetime.isoformat()
        context.update(cls.additional_sql_context())
        return context

    @classmethod
    def _sql_query_template(cls, template_name, start_datetime, end_datetime):
        path = os.path.join(
            settings.BASE_DIR,
            'corehq',
            'warehouse',
            'transforms',
            'sql',
            '{}.sql'.format(template_name),
        )
        if not os.path.exists(path):
            raise NotImplementedError(
                'You must define {} in order to load data'.format(path)
            )

        return _render_template(path, cls._table_context(start_datetime, end_datetime))


class CouchToDjangoETLMixin(BaseETLMixin):
    '''
    Mixin for transferring docs from Couch to a Django model.
    '''

    @classmethod
    def field_mapping(cls):
        # Map source model fields to staging table fields
        # ( <source field>, <staging field> )
        raise NotImplementedError

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    def load(cls, start_datetime, end_datetime):
        from corehq.warehouse.models.shared import WarehouseTable

        assert issubclass(cls, WarehouseTable)
        record_iter = cls.record_iter(start_datetime, end_datetime)

        django_batch_records(cls, record_iter, cls.field_mapping())


def _render_template(path, context):
    with open(path) as f:
        template_string = f.read()

    template = engines['django'].from_string(template_string)
    return template.render(Context(context))
