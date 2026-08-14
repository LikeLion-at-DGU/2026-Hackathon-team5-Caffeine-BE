from rest_framework.routers import SimpleRouter
from .views import BusinessViewSet

router = SimpleRouter()
router.register("", BusinessViewSet, basename="business")

urlpatterns = router.urls