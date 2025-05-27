from django.contrib import admin
from django.urls import path, include, re_path
from base.views import FrontendAppView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('base.urls')),
    re_path(r'^.*$', FrontendAppView.as_view()),
]



