from django.db import models


class UsdJpy1M(models.Model):
    time = models.DateTimeField(verbose_name='time', primary_key=True, null=False, auto_now_add=True)
    open = models.FloatField(verbose_name='open')
    close = models.FloatField(verbose_name='close')
    high = models.FloatField(verbose_name='high')
    low = models.FloatField(verbose_name='low')
    volume = models.IntegerField(verbose_name='volume')

    class Meta:
        verbose_name_plural = 'UsdJpy1M'

    def __str__(self):
        return self.created_at


class UsdJpy5M(models.Model):
    time = models.DateTimeField(verbose_name='time', primary_key=True, null=False, auto_now_add=True)
    open = models.FloatField(verbose_name='open')
    close = models.FloatField(verbose_name='close')
    high = models.FloatField(verbose_name='high')
    low = models.FloatField(verbose_name='low')
    volume = models.IntegerField(verbose_name='volume')

    class Meta:
        verbose_name_plural = 'UsdJpy5M'

    def __str__(self):
        return self.created_at


class UsdJpy15M(models.Model):
    time = models.DateTimeField(verbose_name='time', primary_key=True, null=False, auto_now_add=True)
    open = models.FloatField(verbose_name='open')
    close = models.FloatField(verbose_name='close')
    high = models.FloatField(verbose_name='high')
    low = models.FloatField(verbose_name='low')
    volume = models.IntegerField(verbose_name='volume')

    class Meta:
        verbose_name_plural = 'UsdJpy15M'

    def __str__(self):
        return self.created_at