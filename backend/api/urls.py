from django.urls import include, path
from rest_framework import routers

from api.views import (CustomUserViewSet, FavoriteViewSet, IngredientViewSet,
                       RecipeViewSet, ShoppingCartViewSet, SubscriptionViewSet,
                       TagViewSet)

app_name = 'api'

router = routers.DefaultRouter()

router.register(r'users', CustomUserViewSet, basename='users')
router.register(r'tags', TagViewSet, basename='tags')
router.register(r'recipes', RecipeViewSet, basename='recipes')
router.register(r'ingredients', IngredientViewSet, basename='ingredients')

urlpatterns = [
    path('users/subscriptions/', SubscriptionViewSet.as_view({
        'get': 'subscriptions',
    }), name='user_subscriptions'),
    path('users/<int:pk>/subscribe/', SubscriptionViewSet.as_view({
        'post': 'subscribe',
        'delete': 'unsubscribe'
    }), name='user_subscribe'),
    path('recipes/<int:pk>/favorite/', FavoriteViewSet.as_view(
        {'post': 'create', 'delete': 'destroy'}), name='recipe-favorite'),
    path('recipes/<int:pk>/shopping_cart/', ShoppingCartViewSet.as_view(
        {'post': 'create', 'delete': 'destroy'}), name='recipe-shopping-cart'),
    path('recipes/download_shopping_cart/', ShoppingCartViewSet.as_view(
        {'get': 'download_shopping_cart'}), name='download_shopping_cart'),

    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
]
