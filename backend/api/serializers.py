import base64

from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.relations import PrimaryKeyRelatedField

from api.validators import username_validator
from foodgram import settings
from users.models import CustomUser, Subscription
from recipes.models import Favorite, ShoppingCart, Recipe, Tag, Ingredient, IngredientInRecipe


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]

            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)


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
        fields = ('email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar')
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
    """Serializer модели RecipeIngredient"""
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
    ingredients = RecipeIngredientSerializer(many=True, source='ingredients_in_recipe')
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = serializers.ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited', 'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and Favorite.objects.filter(user=user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and ShoppingCart.objects.filter(user=user, recipe=obj).exists()


class IngredientForRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = Ingredient
        fields = (
            'id',
            'amount'
        )


class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients = IngredientForRecipeSerializer(many=True)
    tags = PrimaryKeyRelatedField(queryset=Tag.objects.all(),
                                  many=True)
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(required=True, min_value=1)

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

    def validate_image(self, value):
        if not self.instance and not value:
            raise ValidationError('Image is required')
        return value

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
        return attrs

    def create(self, validated_data):
        # Получаем пользователя из context -> request (приходит из viewa)
        user = self.context['request'].user

        with transaction.atomic():
            # Создаем рецепт с базовыми полями
            recipe = Recipe.objects.create(
                author=user,
                name=validated_data['name'],
                image=validated_data['image'],
                text=validated_data['text'],
                cooking_time=validated_data['cooking_time']
            )

            # Прикрепляем тэги к созданному рецепту
            recipe.tags.set(validated_data['tags'])

            # Создаем ингредиенты в промежуточной таблице, чтобы установить кол-во
            for ingredient in validated_data['ingredients']:
                IngredientInRecipe.objects.create(
                    recipe=recipe,
                    ingredient=ingredient['id'],
                    amount=ingredient['amount']
                )

        # Возвращаем созданный объект
        return recipe


class RecipeUpdateSerializer(RecipeCreateSerializer):
    image = Base64ImageField(required=False)

    def update(self, instance, validated_data):
        with transaction.atomic():
            # Обновляем базовые поля рецепта
            instance.name = validated_data['name']
            instance.text = validated_data['text']
            instance.cooking_time = validated_data['cooking_time']
            if validated_data.get('image'):
                instance.image = validated_data['image']

            instance.tags.set(validated_data['tags'])

            instance.ingredients.clear()
            for ingredient in validated_data['ingredients']:
                IngredientInRecipe.objects.create(
                    recipe=instance,
                    ingredient=ingredient['id'],
                    amount=ingredient['amount']
                )

            instance.save()
        return instance


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class UserWithRecipesSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.BooleanField(default=True)
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(source='recipes.count', read_only=True)

    def get_recipes(self, obj):
        limit = self.context['request'].query_params.get('recipes_limit') or settings.REST_FRAMEWORK['PAGE_SIZE']
        recipes = obj.recipes.all()[:int(limit)]
        return RecipeMinifiedSerializer(recipes, many=True).data

    class Meta:
        model = CustomUser
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'recipes', 'recipes_count', 'avatar')


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
        if self.context['request'].method == 'POST':
            if author == self.context['request'].user:
                raise ValidationError('Вы не можете подписаться на самого себя')
            if Subscription.objects.filter(user=self.context['request'].user, author=author).exists():
                raise ValidationError('Вы уже подписаны на этого пользователя')
        else:
            if not Subscription.objects.filter(user=self.context['request'].user, author=author).exists():
                raise ValidationError('Вы еще не подписаны на этого пользователя')

        return attrs

    def create(self, validated_data):
        subscribe = Subscription.objects.create(
            user=self.context['request'].user,
            author_id=validated_data['author_id']
        )
        return subscribe.author


class ObjectWithRecipeUserCreateDeleteSerializer(serializers.ModelSerializer):
    recipe_id = serializers.IntegerField()

    class Meta:
        model = Recipe
        fields = (
            'recipe_id',
        )

    def validate(self, attrs):
        recipe = get_object_or_404(Recipe, id=attrs['recipe_id'])
        if self.context['request'].method == 'POST':
            if self.context['model'].objects.filter(user=self.context['request'].user, recipe=recipe).exists():
                raise ValidationError(f"Вы уже добавиляли этот рецепт в {self.context['model'].__name__}.")
        else:
            if not self.context['model'].objects.filter(user=self.context['request'].user, recipe=recipe).exists():
                raise ValidationError(f"Вы еще не добавиляли этот рецепт в {self.context['model'].__name__}.")

        return attrs

    def create(self, validated_data):
        obj = self.context['model'].objects.create(
            user=self.context['request'].user,
            recipe_id=validated_data['recipe_id']
        )
        return obj.recipe
