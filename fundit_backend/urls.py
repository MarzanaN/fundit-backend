from django.contrib import admin
from django.urls import path, re_path, include
from base.views import FrontendAppView
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('base.urls')),

    # Catch-all for frontend SPA - only for non-static and non-API paths
    re_path(r'^(?!static/|api/|admin/).*$', FrontendAppView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=str(Path(settings.REACT_BUILD_DIR) / 'static')
    )
