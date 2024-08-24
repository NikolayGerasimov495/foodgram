from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

from users.models import CustomUser

User = get_user_model()


class Recipe(models.Model):
    """Модель Рецепта."""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipes',
                               verbose_name='Автор рецепта')
    name = models.TextField('Название', max_length=256)
    image = models.ImageField('Ссылка на картинку на сайте', upload_to='recipes/images/', blank=True)
    text = models.TextField('Описание')
    ingredients = models.ManyToManyField('Ingredient', through='IngredientInRecipe', verbose_name='Список ингредиентов')
    tags = models.ManyToManyField('Tag', related_name='recipes', verbose_name='Список тегов')
    cooking_time = models.PositiveIntegerField('Время приготовления (в минутах)', default=1, validators=[
        MinValueValidator(1, 'Время готовки минимум одна минута')
    ])

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Модель тега."""
    name = models.CharField('Название', max_length=32, unique=True)
    slug = models.SlugField('Уникальный слаг', max_length=32, unique=True, null=True)

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Модель ингредиентов."""
    name = models.CharField(max_length=128, unique=True)
    measurement_unit = models.CharField(max_length=64)

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}'


class IngredientInRecipe(models.Model):
    """Модель связи рецепт-ингредиент."""
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name='Рецепт', max_length=128,
                               related_name='ingredients_in_recipe')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, verbose_name='Ингредиент', max_length=64,
                                   related_name='ingredients_in_recipe')
    amount = models.PositiveIntegerField('Количество', default=1, validators=[
        MinValueValidator(1, 'Должно быть минимум один')])

    class Meta:
        verbose_name = 'Рецепт/Ингредиент'
        verbose_name_plural = 'Рецепты/Ингредиенты'

    def __str__(self):
        return f'{self.recipe}/{self.ingredient}/{self.amount}'


class Favorite(models.Model):
    """Модель избранное"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name='Рецепт')

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные'

    def __str__(self):
        return f'{self.user}/{self.recipe}'


class ShoppingCart(models.Model):
    """Модель корзины покупок."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name='Рецепт')

    class Meta:
        verbose_name = 'Корзина покупок'

    def __str__(self):
        return f'{self.user}/{self.recipe}'
