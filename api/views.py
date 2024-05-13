import json
import requests as web_request
from django.contrib.auth.password_validation import validate_password
from yaml import load as load_yaml, Loader

from django.contrib.auth import authenticate
from django.core.validators import URLValidator
from django.db.models import Sum, F
from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token

from api.models import Shop, Category, Contact, Product, ProductInfo, Order, OrderItem, Parameter, ProductParameter, \
    STATUS_SHOP, ConfirmEmailToken
from api.serializers import ShopSerializer, CategorySerializer, ContactSerializer, \
    ProductInfoSerializer, OrderSerializer, OrderItemSerializer, UserSerializer
from api.utils import send_order_status_email

from django.db import IntegrityError



class RegisterAccountView(APIView):
    """
    Класс для регистрации покупателей

    Methods:
        - post: Для регистрации пользователей

    Attributes:
        -None
    """

    # Регистрация методом POST

    def post(self, request, *args, **kwargs):
        """
            Создание нового пользователя.

            Args:
                request (Request): The Django request object.

            Returns:
                JsonResponse: The response indicating the status of the operation and any errors.
            """
        if {'first_name', 'last_name', 'email', 'password'}.issubset(request.data):

            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:

                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ConfirmAccountView(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
                Подтверждает почтовый адрес пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        # проверяем обязательные аргументы
        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class LoginAccountView(APIView):
    """
    Класс для авторизации пользователей
    """

    # Авторизация методом POST
    def post(self, request, *args, **kwargs):
        """
        Authenticate a user.

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if {'email', 'password'}.issubset(request.data):

            user = authenticate(request, username=request.data['email'], password=request.data['password'])

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
       Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
        Класс для просмотра продуктов.

        Methods:
        - get: Retrieve the product information based on the specified filters.

        Attributes:
        - None
    """
    def get(self, request, *args, **kwargs):
        queryset = ProductInfo.objects.filter(shop__status=True)

        shop_id = request.data.get('shop')
        product_id = request.data.get('product')

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        queryset = queryset.select_related(
            'shop', 'product__category').prefetch_related(
            'product_details__parameter').distinct()
        serializer = ProductInfoSerializer(queryset, many=True)
        return JsonResponse(serializer.data, safe=False)


class BasketView(APIView):
    """
    Класс для заполнение и изменения корзины

    Methods:
        - get: Просмотреть корзину
        - post: Добавить в корзину
        - put: Изменить количество
        - delete: Удалить товар

    Attributes:
        - None
    """

    def get(self, request, *args, **kwargs):
        """
        Метод просмотра корзины

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        basket = Order.objects.filter(
            user_id=request.user.id, status='basket').prefetch_related(
            'orderitem_order__product__products_info').annotate(
            total_sum=Sum(F('orderitem_order__quantity') * F('orderitem_order__product__products_info__price'))
        )

        seriralizer = OrderSerializer(basket, many=True)
        return JsonResponse(seriralizer.data, safe=False)

    def post(self, request, *args, **kwargs):
        """
        Метод для добавление товара в корзину

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """

        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        try:
            items_json = json.loads(request.body).get('items')
        except json.JSONDecodeError:
            return JsonResponse({'Status': False, 'Error': 'Invalid JSON format'}, status=400)

        if not items_json:
            return JsonResponse({'status': False, 'error': 'No item data provided'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            basket, _ = Order.objects.get_or_create(user=request.user, status='basket')
        except Order.MultipleObjectsReturned:
            return JsonResponse({'status': False, "error": 'Basket already exists'})
        except IntegrityError as error:
            return JsonResponse({'status': False, 'error': str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        objects_created = 0
        for item_data in items_json:
            item_data['order'] = basket.id
            serializer = OrderItemSerializer(data=item_data)
            if serializer.is_valid():
                serializer.save()
                objects_created += 1
            else:
                return JsonResponse({'status': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse({'status': True, 'objects_created': objects_created}, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        """
        Метод для изменения количества товара в корзине

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        items_json = json.loads(request.body).get('items')
        if not items_json:
            return JsonResponse({'status': False, 'error': 'No item data provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            basket, _ = Order.objects.get_or_create(user=request.user, status='basket')
        except IntegrityError as error:
            return JsonResponse({'status': False, 'error': str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        objects_update = 0
        for item_data in items_json:
            item_data['order_id'] = basket.id
            serializer = OrderItemSerializer(data=item_data)
            objects_update += OrderItem.objects.filter(
                order_id=basket.id, shop_id=item_data['shop'], product_id=item_data['product']).update(
                quantity=item_data['quantity'])

        return JsonResponse({'Status': True, 'Обновлено объектов': objects_update})

    def delete(self, request, *args, **kwargs):
        """
        Метод для удаления товара в корзину

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        items_json = json.loads(request.body).get('items')

        if not items_json:
            return JsonResponse({'status': False, 'error': 'No item data provided'}, status=status.HTTP_400_BAD_REQUEST)

        basket, _ = Order.objects.get_or_create(user_id=request.user.id, status='basket')

        objects_deleted = 0
        for item_data in items_json:
            item_data['order_id'] = basket.id
            serializer = OrderItemSerializer(data=item_data)
            objects_deleted += OrderItem.objects.filter(
                order_id=basket.id, shop_id=item_data['shop'], product_id=item_data['product']).delete()[0]

        return JsonResponse({'Status': True, 'Удалено объектов': objects_deleted})


class ContactView(APIView):
    """
        Класс для заполнение и изменения корзины

        Methods:
            - get: Просмотреть контакты
            - post: Добавить в контакты
            - patch: Изменить контакты
            - delete: Удалить контакты

         Attributes:
            - None
        """
    def get(self, request, *args, **kwargs):
        """
        Метод для просмотра контактов

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        contact = Contact.objects.filter(user=request.user)
        serializer = ContactSerializer(contact, many=True)
        print(contact)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request, *args, **kwargs):
        """
        Метод для добавления контактов

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        if {'city', 'street', 'house', 'phone'}.issubset(request.data):
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save(user=request.user)
                return JsonResponse({'success': True}, status=201)
            else:
                return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)
        else:
            return JsonResponse({'success': False, 'Error': 'missed args'}, status=403)

    def patch(self, request, *args, **kwargs):
        """
        Метод для изменения контактов

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        contact_count = Contact.objects.filter(user=request.user)

        for contact in contact_count:
            contact = get_object_or_404(Contact, user=request.user)
            contact_serializer = ContactSerializer(contact, data=request.data, partial=True)
            if contact_serializer.is_valid():
                contact_serializer.save()
                return JsonResponse({'Status': 'True'})

    def delete(self, request, *args, **kwargs):
        """
        Метод для удаления контактов

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        user = request.user
        contacts = Contact.objects.filter(user=user)

        if contacts.exists():
            contact = contacts.first()
            contact.delete()
            return JsonResponse({'Status': 'True'}, status=200)
        else:
            return JsonResponse({'Status': 'False', 'Error': 'No contacts found for the current user'}, status=404)


class PartherUpdate(APIView):
    """
    Класс для добавления товара в магазин

    Methods:
    - post: Обновление информации о партнере.

    Attributes:
    - None
    """

    def post(self, request, *args, **kwags):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': 'False', 'Error': 'Только для магазинов'})

        url = request.data.get('url')
        if url:
            try:
                validate_url = URLValidator()
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})

            content = web_request.get(url).content
            data = load_yaml(content, Loader=Loader)

            shop, _ = Shop.objects.get_or_create(name=data['name'], user_id=request.user.id)

            for category in data['categories']:
                categories, _ = Category.objects.get_or_create(name=category['name'], category_id=category['id'])
                categories.shops.add(shop.id)
                categories.save()
            ProductInfo.objects.filter(shop_id=shop.id).delete()

            for item in data['goods']:
                product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
                product_info = ProductInfo.objects.create(product_id=product.id,
                                                          model=item['model'],
                                                          name=item['name'],
                                                          price=item['price'],
                                                          price_rrc=item['price_rrc'],
                                                          quantity=item['quantity'],
                                                          shop_id=shop.id)
                product.save()
                for name, value in item['parameters'].items():
                    parameter, _ = Parameter.objects.get_or_create(name=name)
                    ProductParameter.objects.create(parameter=product_info.id,
                                                    quantity=product_info.quantity,
                                                    value=value)
                    parameter.save()
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartherState(APIView):
    """
    Класс для изменения статуса партнера

    Methods:
        - get: Просмотр статуса партнера
        - put: Изменение статуса

    Attributes:
    - None
    """

    def get(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': 'False', 'Error': 'Только для магазинов'})

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return JsonResponse(serializer.data, safe=False)

    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': 'False', 'Error': 'Только для магазинов'})

        state = request.data.get('state')
        if state in STATUS_SHOP:
            try:
                Shop.objects.filter(user_id=request.user.id).update(status=state)
                return JsonResponse({'Status': True})
            except ValueError:
                return JsonResponse({'Status': False, 'error': ValueError})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartherOrders(APIView):
    """
    Класс для просмотра заказов магазина

    Methods
        - get: Просмотреть заказы
    """
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': 'False', 'Error': 'Только для магазинов'})

        order = Order.objects.filter(orderitem_order__shop__user=request.user.id).exclude(
            status='basket').annotate(
            total_sum=Sum(F('orderitem_order__quantity') * F('orderitem_order__product__products_info__price'))
        )
        serializer = OrderSerializer(order, many=True)
        return JsonResponse(serializer.data, safe=False)


class OrderView(APIView):
    """
    Класс для заполнение и изменения заказа

    Methods:
        - get: Просмотреть заказы
        - post: Добавить в заказы
        - put: Убрать из заказа

     Attributes:
        - None
    """
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        orders = Order.objects.filter(user=request.user.id).exclude(status='basket').annotate(
            total_sum=Sum(F('orderitem_order__quantity') * F('orderitem_order__product__products_info__price')))

        serializer = OrderSerializer(orders, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        order_id = int(request.data.get('order'))
        contact = int(request.data.get('contact'))

        try:
            orders = Order.objects.filter(id=order_id)
        except ValueError:
            return JsonResponse({'Status': False, 'Description': 'Не верно передан Формат'})

        for order in orders:
            if order.status == 'order':
                return JsonResponse({'Status': False, 'Description': 'Заказ уже оформлен'})
            else:
                orders.update(status='order', contact_id=contact)
                send_order_status_email(user_id=order.user_id, status=True)  # Отправка СМС пользователю о формировании заказа
                return JsonResponse({'Status': True, 'Description': 'Заказ оформлен'})
        return JsonResponse({'Status': False, 'Description': 'Не верно передан заказ'})


    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': 'False', 'Error': 'Not Log in'}, status=403)

        order_id = request.data.get('order')

        try:
            orders = Order.objects.filter(id=order_id)
        except ValueError:
            return JsonResponse({'Status': False, 'Description': 'Не верно передан Формат'})

        for order in orders:
            if order.status == 'order':
                orders.update(status='basket')
                send_order_status_email(user_id=order.user_id)

                return JsonResponse({'Status': True, 'Description': 'Заказ отменен'})
            else:
                return JsonResponse({'Status': False, 'Description': 'Уже в корзине'})
        return JsonResponse({'Status': False, 'Description': 'Не верно передан заказ'})
