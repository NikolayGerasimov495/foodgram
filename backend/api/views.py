import os

from api.permissions import IsAuthor
from api.serializers import (AvatarSerializer, CustomUserSerializer,
                             IngredientSerializer,
                             ObjectWithRecipeUserCreateDeleteSerializer,
                             RecipeCreateSerializer, RecipeMinifiedSerializer,
                             RecipeSerializer, RecipeUpdateSerializer,
                             SubscribeCreateDeleteSerializer, TagSerializer,
                             UserWithRecipesSerializer)
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser import views as joser_views
from recipes.models import Favorite, Ingredient, Recipe, ShoppingCart, Tag
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response
from users.models import CustomUser, Subscription


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

    def create(self, request, *args, **kwargs):
        serializer = RecipeCreateSerializer(data=request.data, context={
            'request': request
        })
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        return Response(
            RecipeSerializer(recipe, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        # self.permission_classes = (IsAuthor, )
        self.check_object_permissions(request, recipe)
        serializer = RecipeUpdateSerializer(data=request.data, instance=recipe)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        return Response(
            RecipeSerializer(recipe, context={'request': request}).data
        )

    @action(methods=["GET"], detail=True, url_path="get-link")
    def get_link(self, request, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        short_link = f"{request.scheme}://{request.get_host()}/s/d3{recipe.id}"
        return Response({"short-link": short_link})


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
            queryset = queryset.filter(name__icontains=name)
        return queryset


class ShoppingCartViewSet(viewsets.ModelViewSet):
    queryset = ShoppingCart.objects.all()
    permission_classes = [IsAuthenticated]

    def create(self, request, pk):
        serializer = ObjectWithRecipeUserCreateDeleteSerializer(
            data={'recipe_id': pk},
            context={'request': request, 'model': ShoppingCart}
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        return Response(
            RecipeMinifiedSerializer(recipe).data,
            status=status.HTTP_201_CREATED
        )

    def destroy(self, request, pk):
        serializer = ObjectWithRecipeUserCreateDeleteSerializer(
            data={'recipe_id': pk},
            context={'request': request, 'model': ShoppingCart}
        )
        serializer.is_valid(raise_exception=True)

        ShoppingCart.objects.get(user=request.user, recipe_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request):
        user = request.user
        shopping_cart = ShoppingCart.objects.filter(user=user)
        if not shopping_cart.exists():
            return Response({'detail': 'Ваш список покупок пуст'},
                            status=status.HTTP_404_NOT_FOUND)

        ingredients = {}
        for item in shopping_cart:
            for ingredient in item.recipe.ingredients.all():
                if ingredient.name in ingredients:
                    ingredients[ingredient.name]['amount'] \
                        += item.recipe.ingredients_in_recipe.get(
                        ingredient=ingredient).amount
                else:
                    ingredients[ingredient.name] = {
                        'amount': item.recipe.ingredients_in_recipe.get(
                            ingredient=ingredient).amount,
                        'unit': ingredient.measurement_unit
                    }

        shopping_list = '\n'.join([f'{name} - {item["amount"]} {item["unit"]}'
                                   for name, item in ingredients.items()])
        file_path = os.path.join(settings.MEDIA_ROOT, 'shopping_list.txt')
        with open(file_path, 'w') as f:
            f.write(shopping_list)

        response = FileResponse(open(file_path, 'rb'),
                                content_type='text/plain')
        response['Content-Disposition'] = ('attachment; '
                                           'filename="shopping_list.txt"')
        return response


class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    permission_classes = [IsAuthenticated]

    def create(self, request, pk):
        serializer = ObjectWithRecipeUserCreateDeleteSerializer(
            data={'recipe_id': pk},
            context={'request': request, 'model': Favorite}
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        return Response(
            RecipeMinifiedSerializer(recipe).data,
            status=status.HTTP_201_CREATED
        )

    def destroy(self, request, pk):
        serializer = ObjectWithRecipeUserCreateDeleteSerializer(
            data={'recipe_id': pk},
            context={'request': request, 'model': Favorite}
        )
        serializer.is_valid(raise_exception=True)

        Favorite.objects.get(user=request.user, recipe_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomUserViewSet(joser_views.UserViewSet):
    serializer_class = CustomUserSerializer

    def get_queryset(self):
        return CustomUser.objects.all()

    @action(detail=False, methods=['get'])
    def me(self, request):
        self.permission_classes = (IsAuthenticated,)
        self.check_permissions(request)
        serializer = CustomUserSerializer(
            request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['put'], permission_classes=[IsAuthenticated])
    def avatar(self, request):
        # проверка ограничений
        user = request.user
        self.permission_classes = [IsAuthenticated]
        self.check_permissions(request)
        # валидация данных
        serilazer = AvatarSerializer(data=request.data)
        serilazer.is_valid(raise_exception=True)
        # бизнес-логика
        user.avatar = serilazer.validated_data['avatar']
        user.save()
        # подготовка ответа
        return Response({'avatar': user.avatar.url}, status=status.HTTP_200_OK)

    @avatar.mapping.delete
    def delete_avatar(self, request):
        user = request.user
        self.permission_classes = [IsAuthenticated]
        self.check_permissions(request)

        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    @action(methods=["GET"], detail=False)
    def subscriptions(self, request, *args, **kwargs):
        my_subscribes = Subscription.objects.filter(
            user=request.user).values_list('author_id', flat=True)
        self.queryset = CustomUser.objects.prefetch_related('recipes').filter(
            id__in=my_subscribes)
        self.serializer_class = UserWithRecipesSerializer
        return super().list(request, args, kwargs)

    @action(detail=True, methods=['post'])
    def subscribe(self, request, pk=None):
        serializer = SubscribeCreateDeleteSerializer(
            data={'author_id': pk},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        author = serializer.save()
        return Response(
            UserWithRecipesSerializer(author,
                                      context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=['DELETE'], detail=True)
    def unsubscribe(self, request, pk=None):
        serializer = SubscribeCreateDeleteSerializer(
            data={'author_id': pk},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        Subscription.objects.get(user=request.user, author_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
