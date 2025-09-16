from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "ai"

router = DefaultRouter()
router.register(r"cover-letters", views.CoverLetterViewSet, basename="cover-letter")

urlpatterns = [
    path("", include(router.urls)),
]
