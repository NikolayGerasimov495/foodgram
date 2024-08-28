import io

from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser import views as joser_views
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly,
                                        SAFE_METHODS
                                        )
from rest_framework.response import Response
from rest_framework import permissions

from api.mixins import CreateDestroyObjectMixin
from api.permissions import IsAuthor
from api.serializers import (AvatarSerializer, CustomUserSerializer,
                             IngredientSerializer,
                             ObjectWithRecipeUserCreateDeleteSerializer,
                             RecipeCreateUpdateSerializer,
                             RecipeMinifiedSerializer,
                             RecipeSerializer,
                             SubscribeCreateDeleteSerializer, TagSerializer,
                             UserWithRecipesSerializer)
from recipes.models import Favorite, Ingredient, Recipe, ShoppingCart, Tag
from users.models import CustomUser, Subscription


class CustomUserViewSet(joser_views.UserViewSet):
    serializer_class = CustomUserSerializer

    def get_queryset(self):
        return CustomUser.objects.all()

    @action(detail=False,
            methods=['GET'],
            permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = CustomUserSerializer(
            request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['put'], url_path='me/avatar',
            permission_classes=(IsAuthenticated,))
    def avatar(self, request):
        user = request.user
        serilazer = AvatarSerializer(data=request.data)
        serilazer.is_valid(raise_exception=True)
        user.avatar = serilazer.validated_data['avatar']
        user.save()
        return Response({'avatar': user.avatar.url}, status=status.HTTP_200_OK)

    @avatar.mapping.delete
    def delete_avatar(self, request):
        user = request.user
        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    filter_backends = [DjangoFilterBackend]
    permission_classes = (IsAuthor, IsAuthenticatedOrReadOnly)

    def get_queryset(self):
        queryset = self.queryset
        is_favorited = self.request.query_params.get('is_favorited')
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart')
        author = self.request.query_params.get('author')
        tags = self.request.query_params.getlist('tags')

        if is_favorited is not None and self.request.user.is_authenticated:
            queryset = queryset.filter(favorite__user=self.request.user)
        if (is_in_shopping_cart is not None
                and self.request.user.is_authenticated):
            queryset = queryset.filter(shoppingcart__user=self.request.user)
        if author is not None:
            queryset = queryset.filter(author__id=author)
        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()

        return queryset

    @action(methods=["GET"], detail=True, url_path="get-link")
    def get_link(self, request, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        short_link = f"{request.scheme}://{request.get_host()}/s/d3{recipe.id}"
        return Response({"short-link": short_link})

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method in SAFE_METHODS:
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    http_method_names = ['get']


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    http_method_names = ['get']

    def get_queryset(self):
        queryset = self.queryset
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class ShoppingCartViewSet(viewsets.ModelViewSet):
    queryset = ShoppingCart.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = ObjectWithRecipeUserCreateDeleteSerializer

    def get_serializer_context(self):
        return {'request': self.request, 'model': ShoppingCart}

    def destroy(self, request, pk):
        # TODO
        # Я думаю, что метод destroy не является лишним.
        # В запросе нам передается pk рецепта, а не записи из таблицы
        # ShoppingCart.
        # Это значит, что используя стандартную логику ModelViewSet, он будет
        # пытаться получить объект из таблицы
        # ShoppingCart, а значит мы получим неверный результат.
        # И также нам все равно понадобятся кастомные валидации, поэтому нужно
        # будет расширять стандартное поведение
        # ModelViewSet.

        # Комментарий по методу create(), я выполнил, но думаю, что это тоже
        # не самая лучшая реализация в данном случае.
        # Так как мы работаем с промежуточной таблицей, а параметр маршрута
        # является id-ом рецепта.
        # TODO
        serializer = ObjectWithRecipeUserCreateDeleteSerializer(
            data={'recipe_id': pk},
            context={'request': request, 'model': ShoppingCart}
        )
        serializer.is_valid(raise_exception=True)

        ShoppingCart.objects.get(user=request.user, recipe_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request):
        recipes_id = ShoppingCart.objects.filter(
            user=request.user).values_list('recipe__pk', flat=True)
        recipes = (Recipe.objects.filter(
            id__in=recipes_id
        ).annotate(quantity=Sum(
            'ingredients__ingredients_in_recipe__amount', filter=Q
            (
                ingredients__ingredients_in_recipe__recipe_id__in=recipes_id
            ))).distinct().values_list(
            'quantity', 'ingredients_in_recipe__ingredient__name',
            'ingredients_in_recipe__ingredient__measurement_unit')
        )
        result = ''
        for i in range(len(recipes)):
            result += (f'|{recipes[i][1]}| --- '
                       f'|{recipes[i][2]}| --- '
                       f'|{recipes[i][0]}|\n')
        text = io.BytesIO()
        with io.TextIOWrapper(text, encoding="utf-8", write_through=True) as f:
            f.write(result)
            response = HttpResponse(text.getvalue(), content_type="text/plain")
            response[
                "Content-Disposition"
            ] = "attachment; filename=shopping_list.txt"
            return response


class FavoriteViewSet(CreateDestroyObjectMixin, viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    permission_classes = (IsAuthenticated,)

    def create(self, request, pk):
        return self.create_object(
            input_serializer=ObjectWithRecipeUserCreateDeleteSerializer,
            serializer_data={'recipe_id': pk},
            serializer_context={'request': request, 'model': Favorite},
            output_serializer=RecipeMinifiedSerializer
        )

    def destroy(self, request, pk):
        return self.destroy_object(
            input_serializer=ObjectWithRecipeUserCreateDeleteSerializer,
            serializer_data={'recipe_id': pk},
            serializer_context={'request': request, 'model': Favorite},
            model=Favorite,
            extra_data={'user': request.user}
        )


class SubscriptionViewSet(CreateDestroyObjectMixin, viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)

    @action(methods=["GET"], detail=False)
    def subscriptions(self, request, *args, **kwargs):
        subscribes = Subscription.objects.filter(
            user=request.user).values_list('author_id', flat=True)
        self.queryset = CustomUser.objects.prefetch_related('recipes').filter(
            id__in=subscribes)
        self.serializer_class = UserWithRecipesSerializer
        return super().list(request, args, kwargs)

    @action(detail=True, methods=['post'])
    def subscribe(self, request, pk=None):
        return self.create_object(
            input_serializer=SubscribeCreateDeleteSerializer,
            serializer_data={'author_id': pk},
            serializer_context={'request': request},
            output_serializer=UserWithRecipesSerializer,
            output_serializer_context={'request': request}
        )

    @action(methods=['DELETE'], detail=True)
    def unsubscribe(self, request, pk=None):
        return self.destroy_object(
            input_serializer=SubscribeCreateDeleteSerializer,
            serializer_data={'author_id': pk},
            serializer_context={'request': request},
            model=Subscription,
            extra_data={'user': request.user}
        )
