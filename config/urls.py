from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('dashboard:index')),
    path('auth/', include('apps.authentication.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('products/', include('apps.products.urls')),
    path('parties/', include('apps.parties.urls')),
    path('purchases/', include('apps.purchases.urls')),
    path('sales/', include('apps.sales.urls')),
    path('finance/', include('apps.finance.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('ginning/', include('apps.ginning.urls')),
    path('labour/', include('apps.labour.urls')),
    path('transport/', include('apps.transport.urls')),
    path('reports/', include('apps.reports.urls')),
    path('settings/', include('apps.settings_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
