# -*- coding: utf-8 -*-
# Generated by Django 1.11.14 on 2018-08-03 20:25
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0058_new_agg_ccs_columns'),
    ]

    operations = [
        HqRunSQL(
            # This migration is not reversible because blobs created
            # since the migration will no longer be accessible after
            # reversing because the old blob db would use the wrong path
            """
            UPDATE icds_reports_icdsfile
            SET blob_id = 'icds_blobdb/' || blob_id
            WHERE blob_id NOT LIKE 'icds_blobdb/%'
            """
        ),
    ]
