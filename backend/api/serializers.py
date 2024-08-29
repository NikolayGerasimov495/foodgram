from django.db import transaction

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.relations import PrimaryKeyRelatedField

from api.fields import Base64ImageField
from api.validators import username_validator
from foodgram import settings
from recipes.models import (Favorite, Ingredient, IngredientInRecipe, Recipe,
                            ShoppingCart, Tag)
from users.models import CustomUser, Subscription


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')
        read_only_fields = ('id',)


class CustomUserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(validators=(username_validator,))
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'avatar')
        read_only_fields = ('id', 'is_subscribed')

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return user.user_subscriptions.filter(author=obj).exists()
        return False


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Ingredient


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name', required=False)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit', required=False)

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True, source='ingredients_in_recipe')
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = serializers.ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and Favorite.objects.filter(
            user=user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and ShoppingCart.objects.filter(
            user=user, recipe=obj).exists()


class IngredientForRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = Ingredient
        fields = (
            'id',
            'amount'
        )


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = IngredientForRecipeSerializer(many=True)
    tags = PrimaryKeyRelatedField(queryset=Tag.objects.all(),
                                  many=True)
    cooking_time = serializers.IntegerField(required=True, min_value=1)
    image = Base64ImageField(required=False)

    class Meta:
        model = Recipe
        fields = (
            'ingredients',
            'tags',
            'image',
            'name',
            'text',
            'cooking_time',
        )

    def validate(self, attrs):
        ingredients_values = []
        if not attrs.get('ingredients'):
            raise ValidationError('Пожалуйста установите ингредиенты')
        for item in attrs['ingredients']:
            ingredients_values.append(item.get('id'))
        if len(ingredients_values) != len(set(ingredients_values)):
            raise ValidationError('Ингредиенты должны быть уникальными')

        if not attrs.get('tags'):
            raise ValidationError('Пожалуйста установите тэги')
        if len(attrs['tags']) != len(set(attrs['tags'])):
            raise ValidationError('Тэги должны быть уникальными')

        if not attrs.get('image'):
            raise ValidationError('Image is required')

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            name=validated_data['name'],
            text=validated_data['text'],
            cooking_time=validated_data['cooking_time'],
            image=validated_data.get('image', None))
        recipe.tags.set(validated_data['tags'])

        self.set_ingredients_to_recipe(
            recipe=recipe,
            ingredients=validated_data['ingredients'])
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', [])
        tags_data = validated_data.pop('tags', [])

        instance = super().update(instance, validated_data)

        instance.ingredients.clear()
        self.set_ingredients_to_recipe(
            recipe=instance,
            ingredients=ingredients_data
        )

        instance.tags.set(tags_data)

        return instance

    @staticmethod
    def set_ingredients_to_recipe(recipe, ingredients):
        with transaction.atomic():
            ingredient_list = []

            recipe.ingredients.clear()
            for ingredient in ingredients:
                ingredient_list.append(
                    IngredientInRecipe(
                        recipe=recipe,
                        ingredient=ingredient['id'],
                        amount=ingredient['amount']
                    )
                )

            IngredientInRecipe.objects.bulk_create(ingredient_list)
            # recipe.save()

    def to_representation(self, instance):
        return RecipeSerializer(
            instance,
            context={'request': self.context['request']}).data


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class UserWithRecipesSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.BooleanField(default=True)
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True)

    def get_recipes(self, obj):
        limit = self.context['request'].query_params.get(
            'recipes_limit') or settings.REST_FRAMEWORK['PAGE_SIZE']
        recipes = obj.recipes.all()[:int(limit)]
        return RecipeMinifiedSerializer(recipes, many=True).data

    class Meta:
        model = CustomUser
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'recipes', 'recipes_count', 'avatar')


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = CustomUser
        fields = ('avatar',)


class SubscribeCreateDeleteSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField()

    class Meta:
        model = CustomUser
        fields = (
            'author_id',
        )

    def validate(self, attrs):
        author = get_object_or_404(CustomUser, id=attrs['author_id'])
        subscription_presence = (
            Subscription.objects.filter(
                user=self.context['request'].user,
                author=author).exists())
        if self.context['request'].method == 'POST':
            if author == self.context['request'].user:
                raise ValidationError(
                    'Вы не можете подписаться на самого себя')
            if subscription_presence:
                raise ValidationError('Вы уже подписаны на этого пользователя')
        else:
            if not subscription_presence:
                raise ValidationError(
                    'Вы еще не подписаны на этого пользователя')

        return attrs

    def create(self, validated_data):
        subscribe = Subscription.objects.create(
            user=self.context['request'].user,
            author_id=validated_data['author_id']
        )
        return subscribe.author


class ObjectWithRecipeUserCreateDeleteSerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'pk',
        )

    def validate(self, attrs):
        pk = self.context['request'].parser_context['kwargs']['pk']
        recipe = get_object_or_404(Recipe, id=pk)
        obj_model_presence = self.context['model'].objects.filter(
            user=self.context['request'].user, recipe=recipe).exists()
        if self.context['request'].method == 'POST':
            if obj_model_presence:
                raise ValidationError(
                    f"Вы уже добавиляли этот рецепт в "
                    f"{self.context['model'].__name__}.")
        else:
            if not obj_model_presence:
                raise ValidationError(
                    f"Вы еще не добавиляли этот рецепт в "
                    f"{self.context['model'].__name__}.")
        return attrs

    def create(self, validated_data):
        obj = self.context['model'].objects.create(
            user=self.context['request'].user,
            recipe_id=self.context['request'].parser_context['kwargs']['pk']
        )
        return obj.recipe

    def to_representation(self, instance):
        return RecipeMinifiedSerializer(instance).data
