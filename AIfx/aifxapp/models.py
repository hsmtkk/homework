from django.db import models


class UsdJpy1M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    class Meta:
        db_table = "UsdJpy1M"

    def __str__(self):
        return str(self.time)

    @property
    def value(self):
        return {
            'time': self.time,
            'open': self.open,
            'close': self.close,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
        }


class UsdJpy5M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    class Meta:
        db_table = "UsdJpy5M"

    def __str__(self):
        return str(self.time)

    @property
    def value(self):
        return {
            'time': self.time,
            'open': self.open,
            'close': self.close,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
        }


class UsdJpy15M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    class Meta:
        db_table = "UsdJpy15M"

    def __str__(self):
        return str(self.time)

    @property
    def value(self):
        return {
            'time': self.time,
            'open': self.open,
            'close': self.close,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
        }