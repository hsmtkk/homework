from django.db import models


class UsdJpy1M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    def __str__(self):
        return str(self.time)


class UsdJpy5M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    def __str__(self):
        return str(self.time)


class UsdJpy15M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    def __str__(self):
        return str(self.time)