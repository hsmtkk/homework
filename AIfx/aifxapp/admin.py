from django.contrib import admin
from .models import UsdJpy1M, UsdJpy5M, UsdJpy15M
# Register your models here.

admin.site.register(UsdJpy1M)
admin.site.register(UsdJpy5M)
admin.site.register(UsdJpy15M)