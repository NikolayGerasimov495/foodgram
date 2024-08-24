# from enum import Enum

from django.contrib.auth.models import AbstractUser
from django.db import models

# class ROLES(Enum):
#     """Перечисление для разграничения прав доступа пользователей."""
#     user = 'user'
#     admin = 'admin'


class CustomUser(AbstractUser):
    """Собственная модель пользователя для реализации ТЗ."""
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ('username', 'first_name', 'last_name')

    email = models.EmailField('Адрес электронной почты', max_length=254, unique=True, blank=False,
                              error_messages={'unique': 'Данный адрес уже используется'})
    username = models.CharField('Уникальный юзернейм', max_length=150, unique=True, blank=False,
                                error_messages={'unique': 'Пользователь с таким именем уже существует'})
    first_name = models.CharField('Имя', max_length=150, blank=False)
    last_name = models.CharField('Фамилия', max_length=150, blank=False)
    avatar = models.ImageField('Ссылка на аватар', blank=True, null=True)
    # role = models.CharField(max_length=9, choices=((role.value, role.name) for role in ROLES), default=ROLES.user.value)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('username',)

    def __str__(self):
        return self.username


class Subscription(models.Model):
    """Модель подписок."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Подписчик',
                             related_name='user_subscriptions')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Автор',
                               related_name='author_subscriptions')

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def __str__(self):
        return f'{self.user}/{self.author}'
