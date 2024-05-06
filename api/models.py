from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django_rest_passwordreset.tokens import get_token_generator


TYPE_CHOICES = (
        ('phone', 'Телефон'),
        ('email', 'Электронная почта'),
        ('address', 'Адрес'),
    )

STATUS_SHOP = ('yes', 1, 0, 'no', 'True', 'False', True, False)
USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель')
)


class UserManager(BaseUserManager):
    """
    Миксин для управления пользователями
    """
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Стандартная модель пользователей
    """
    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = 'email'
    email = models.EmailField(('email address'), unique=True)
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        ('username'),
        max_length=150,
        help_text=('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[username_validator],
        error_messages={
            'unique': ("A user with that username already exists."),
        },
    )
    is_active = models.BooleanField(
        ('active'),
        default=False,
        help_text=(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    type = models.CharField(verbose_name='Тип пользователя', choices=USER_TYPE_CHOICES, max_length=5, default='buyer')
    groups = models.ManyToManyField(Group, related_name='api_user_groups')
    user_permissions = models.ManyToManyField(Permission, related_name='api_user_permissions')

    @property
    def token(self):
        """
        Позволяет получить токен пользователя путем вызова user.token, вместо
        user._generate_jwt_token(). Декоратор @property выше делает это
        возможным. token называется "динамическим свойством".
        """
        return self._generate_jwt_token()

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)


class ConfirmEmailToken(models.Model):
    objects = models.manager.Manager()

    class Meta:
        verbose_name = 'Токен подтверждения Email'
        verbose_name_plural = 'Токены подтверждения Email'

    @staticmethod
    def generate_key():
        """ generates a pseudo random code using os.urandom and binascii.hexlify """
        return get_token_generator().generate_token()

    user = models.ForeignKey(
        User,
        related_name='confirm_email_tokens',
        on_delete=models.CASCADE,
        verbose_name=("The User which is associated to this password reset token")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=("When was this token generated")
    )

    # Key field, though it is not the primary key of the model
    key = models.CharField(
        ("Key"),
        max_length=64,
        db_index=True,
        unique=True
    )

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return "Password reset token for user {user}".format(user=self.user)


class Shop(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название', unique=True)
    url = models.URLField(unique=True, blank=True, verbose_name='Ссылка')
    user = models.OneToOneField(User, verbose_name='Пользователь',
                                blank=True, null=True,
                                on_delete=models.CASCADE)
    status = models.BooleanField(verbose_name='Статус магазина', default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('-name',)


class Category(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название')
    shops = models.ManyToManyField(Shop, related_name='categories', verbose_name='Категория')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категории'
        verbose_name_plural = "Список категорий"
        ordering = ('-name',)


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=100, verbose_name='Название')

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = "Список продуктов"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, related_name='products_info', on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, related_name='shops_info', on_delete=models.CASCADE)
    name = models.CharField(max_length=100, verbose_name='Название', blank=True)
    model = models.CharField(max_length=100, verbose_name='Название', blank=True)
    quantity = models.PositiveIntegerField(verbose_name='Количество', blank=True)
    price = models.PositiveIntegerField(verbose_name='Цена', blank=True)
    price_rrc = models.PositiveIntegerField(verbose_name='Розничная цена', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Информация о продукте'


class Parameter(models.Model):
    name = models.CharField(max_length=100, verbose_name='Параметр')

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, related_name='product_details', on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, related_name='parameter_details', on_delete=models.CASCADE)
    value = models.PositiveIntegerField()

    class Meta:
        verbose_name = 'Параметры продукта'

    def __str__(self):
        return f'{self.product_info} {self.parameter}'


class Contact(models.Model):
    type_contact = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Тип контакта')
    user = models.OneToOneField (User, related_name='contact_user', on_delete=models.CASCADE)
    city = models.CharField(max_length=50, verbose_name='Город', blank=True)
    street = models.CharField(max_length=100, verbose_name='Улица', blank=True)
    house = models.CharField(max_length=15, verbose_name='Дом', blank=True)
    structure = models.CharField(max_length=15, verbose_name='Корпус', blank=True)
    building = models.CharField(max_length=15, verbose_name='Строение', blank=True)
    apartment = models.CharField(max_length=15, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон', blank=True)

    def __str__(self):
        return self.type_contact

    class Meta:
        verbose_name = 'Контакты'
        verbose_name_plural = "Список контактов"


class Order(models.Model):
    user = models.ForeignKey(User, related_name='orders', on_delete=models.CASCADE)
    dt = models.DateTimeField(auto_now_add=True)
    status = models.CharField(verbose_name="Статус", max_length=50, blank=True)
    contact = models.ForeignKey(Contact, verbose_name='Контакт', blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.status

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказов"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='orderitem_order', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='orderitem_product', on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, related_name='orderitem_shop', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.product}'

    class Meta:
        verbose_name = 'Информация о заказе'