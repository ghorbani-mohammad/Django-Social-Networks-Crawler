from rest_framework.routers import SimpleRouter

from .views import IgnoredJobViewSet, JobViewSet

router = SimpleRouter()
router.register("job", JobViewSet, basename="job")
router.register("ignored-job", IgnoredJobViewSet, basename="ignored-job")

urlpatterns = []

urlpatterns += router.urls
