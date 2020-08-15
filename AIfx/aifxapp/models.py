from django.db import models

import omitempty


class UsdJpy1M(models.Model):
    time = models.DateTimeField('time', primary_key=True, null=False)
    open = models.FloatField('open')
    close = models.FloatField('close')
    high = models.FloatField('high')
    low = models.FloatField('low')
    volume = models.IntegerField('volume')

    class Meta:
        ordering = ['-time']
        db_table = 'UsdJpy1M'

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
        ordering = ['-time']
        db_table = 'UsdJpy5M'

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
        ordering = ['-time']
        db_table = 'UsdJpy15M'

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


class SignalEvent(models.Model):
    time = models.DateTimeField(primary_key=True, null=False)
    product_code = models.CharField(max_length=50)
    side = models.CharField(max_length=50)
    price = models.FloatField()
    units = models.IntegerField()

    class Meta:
        db_table = 'signal_event'

    def __str__(self):
        return str(self.product_code)

    @property
    def value(self):
        dict_values = omitempty({
            'time': self.time,
            'product_code': self.product_code,
            'side': self.side,
            'price': self.price,
            'units': self.units,
        })
        if not dict_values:
            return None
        return dict_values