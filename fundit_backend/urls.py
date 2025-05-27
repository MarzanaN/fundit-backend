from django.contrib import admin
from django.urls import path, include
from base.views import FrontendAppView  # Import this here

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('base.urls')),  # API routes
    path('', FrontendAppView.as_view()),  # ✅ Serve React index.html here
]


