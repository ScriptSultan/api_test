from django.contrib import admin

from api.models import User, Shop, Product, Category, Order, OrderItem, ProductInfo

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    pass


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.register(Product)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.register(ProductInfo)
class ShopAdmin(admin.ModelAdmin):
    pass

@admin.register(Category)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.register(OrderItem)
class ShopAdmin(admin.ModelAdmin):
    pass