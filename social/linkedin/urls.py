from rest_framework.routers import SimpleRouter

from .views import FavoriteJobViewSet, IgnoredJobViewSet, JobViewSet

router = SimpleRouter()
router.register("job", JobViewSet, basename="job")
router.register("ignored-job", IgnoredJobViewSet, basename="ignored-job")
router.register("favorites", FavoriteJobViewSet, basename="favorites")

urlpatterns = router.urls
