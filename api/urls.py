from api.views import ShopView, ContactView, CategoryView, LoginAccountView, ProductInfoView, \
    BasketView, OrderView, PartherOrders, ConfirmAccountView, RegisterAccountView, PartherState, PartherUpdate
from django.urls import path

urlpatterns = [
    path('api/v1/user/registrate/', RegisterAccountView.as_view(), name='registrate'),
    path('api/v1/user/registrate/confirm/', ConfirmAccountView.as_view(), name='user-register-confirm'),
    path('api/v1/user/shops/', ShopView.as_view(), name='shops'),
    path('api/v1/user/contact/', ContactView.as_view(), name='contact'),
    path('api/v1/user/login/', LoginAccountView.as_view(), name='login'),
    path('api/v1/user/categories/', CategoryView.as_view(), name='category'),
    path('api/v1/user/product/', ProductInfoView.as_view(), name='product_to_info'),
    path('api/v1/user/basket/', BasketView.as_view(), name='basket'),
    path('api/v1/user/orders/', OrderView.as_view(), name='orders'),
    path('api/v1/shop/orders/', PartherOrders.as_view(), name='shop-orders'),
    path('api/v1/shop/state/', PartherState.as_view(), name='shop-state'),
    path('api/v1/shop/goods/', PartherUpdate.as_view(), name='shop-goods')
]