# Generated by Django 3.0.7 on 2020-07-24 15:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aifxapp', '0005_auto_20200724_1512'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usdjpy15m',
            name='time',
            field=models.DateTimeField(primary_key=True, serialize=False, verbose_name='time'),
        ),
        migrations.AlterField(
            model_name='usdjpy1m',
            name='time',
            field=models.DateTimeField(primary_key=True, serialize=False, verbose_name='time'),
        ),
        migrations.AlterField(
            model_name='usdjpy5m',
            name='time',
            field=models.DateTimeField(primary_key=True, serialize=False, verbose_name='time'),
        ),
    ]
