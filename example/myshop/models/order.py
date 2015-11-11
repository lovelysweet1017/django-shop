# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from decimal import Decimal
from shop.models.order import BaseOrderItem
from shop.models.cart import CartItemModel
from .product import Product


class OrderItem(BaseOrderItem):
    def populate_from_cart_item(self, cart_item, request):
        super(OrderItem, self).populate_from_cart_item(cart_item, request)
        # the product code and price must be fetched from the product's markedness
        try:
            product = cart_item.product.get_product_markedness(cart_item.extra)
            self.product_code = product.product_code
            self._unit_price = Decimal(product.unit_price)
        except Product.DoesNotExist as e:
            raise CartItemModel.DoesNotExist(e)
