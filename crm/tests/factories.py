from decimal import Decimal

from crm.models import Customer, Order, OrderItem


def make_customer(**kwargs):
    defaults = {"name": "Nguyễn Văn Test", "email": "test@example.com", "phone": "0900000000"}
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_order(customer, status=Order.Status.COMPLETED, items=(("Sản phẩm A", 2, 100000),)):
    order = Order.objects.create(customer=customer, status=status)
    for name, quantity, price in items:
        OrderItem.objects.create(order=order, product_name=name, quantity=quantity, unit_price=Decimal(price))
    return order
