# Generated by Django 3.0.3 on 2020-08-14 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aifxapp', '0008_auto_20200812_1104'),
    ]

    operations = [
        migrations.CreateModel(
            name='SignalEvent',
            fields=[
                ('time', models.DateTimeField(primary_key=True, serialize=False)),
                ('product_code', models.CharField(max_length=50)),
                ('side', models.CharField(max_length=50)),
                ('price', models.FloatField()),
                ('units', models.IntegerField()),
            ],
            options={
                'db_table': 'signal_event',
            },
        ),
    ]