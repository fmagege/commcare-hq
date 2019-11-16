# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-11-16 17:38
from django.db import migrations, models, transaction

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.hqmedia.models import ApplicationMediaMapping
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.django_migrations import skip_on_fresh_install
from dimagi.utils.couch.database import iter_docs


@skip_on_fresh_install
def _migrate_multimedia_map_for_all_builds(apps, schema_editor):
    app_ids = (get_doc_ids_by_class(Application)
               + get_doc_ids_by_class(LinkedApplication)
               + get_deleted_doc_ids_by_class(Application)
               + get_deleted_doc_ids_by_class(LinkedApplication))
    for doc in iter_docs(Application.get_db(), app_ids, chunksize=1):
        _migrate_multimedia_map(doc)


def _migrate_multimedia_map(doc):
    if not doc.get('multimedia_map'):
        return

    if ApplicationMediaMapping.objects.filter(domain=doc['domain'], app_id=doc['_id']).exists():
        # already migrated
        return

    with transaction.atomic():
        for path, item in doc['multimedia_map'].items():
            sql_item = ApplicationMediaMapping.objects.create(
                domain=doc['domain'],
                app_id=doc['_id'],
                path=path,
                multimedia_id=item['multimedia_id'],
                media_type=item['media_type'],
                version=item['version'],
                unique_id=item['unique_id'] or ApplicationMediaMapping.gen_unique_id(item['multimedia_id'], path),
            )
            sql_item.save()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationMediaMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=100)),
                ('app_id', models.CharField(max_length=255)),
                ('path', models.CharField(max_length=255)),
                ('multimedia_id', models.CharField(max_length=255)),
                ('media_type', models.CharField(max_length=255)),
                ('version', models.IntegerField(null=True)),
                ('unique_id', models.CharField(max_length=255)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='applicationmediamapping',
            unique_together=set([('domain', 'app_id', 'path')]),
        ),
        migrations.RunPython(_migrate_multimedia_map_for_all_builds,
            reverse_code=migrations.RunPython.noop,
            elidable=True),
    ]
