from rest_framework.routers import SimpleRouter

from .views import IgnoredJobViewSet

router = SimpleRouter()
router.register("ignored-job", IgnoredJobViewSet, basename="ignored-job")

urlpatterns = []

urlpatterns += router.urls
