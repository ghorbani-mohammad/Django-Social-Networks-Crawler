from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("secret-admin/", admin.site.urls),
    path("api/v1/soc/", include("network.urls")),
    path("api/v1/linkedin/", include("linkedin.urls")),
    path("api/v1/user/", include("user.urls")),
    path("api/v1/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

admin.site.index_title = "Social"
admin.site.site_title = "Social Admin"
admin.site.site_header = "Social Administration Panel"
