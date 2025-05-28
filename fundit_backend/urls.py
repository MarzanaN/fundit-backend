from django.contrib import admin
from django.urls import path, include
from base.views import FrontendAppView
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path

REACT_BUILD_DIR = Path(settings.REACT_BUILD_DIR)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('base.urls')),
    path('', FrontendAppView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=str(REACT_BUILD_DIR / 'static')
    )
