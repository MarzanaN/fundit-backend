from django.contrib import admin
from django.urls import path, include
from base.views import FrontendAppView  
from django.conf import settings
from django.conf.urls.static import static
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('base.urls')),  
    path('', FrontendAppView.as_view()),  
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=os.path.join(settings.BASE_DIR, 'fundit_backend', 'build', 'static')
    )
