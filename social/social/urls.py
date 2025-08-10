from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("secret-admin/", admin.site.urls),
    path("api/v1/soc/", include("network.urls")),
]

admin.site.index_title = "Social"
admin.site.site_title = "Social Admin"
admin.site.site_header = "Social Administration Panel"
