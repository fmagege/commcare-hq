# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-01-30 09:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0165_merge_20200130_0930'),
    ]

    operations = [
        migrations.AddField(
            model_name='aggregatemigrationforms',
            name='migration_date',
            field=models.DateTimeField(help_text='Migration Date', null=True),
        ),
    ]