# Generated by Django 3.0.3 on 2020-08-14 17:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aifxapp', '0009_signalevent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signalevent',
            name='time',
            field=models.TimeField(primary_key=True, serialize=False),
        ),
    ]