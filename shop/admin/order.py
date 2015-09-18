# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.conf.urls import patterns, url
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.forms import widgets
from django.http import HttpResponse
from django.template import RequestContext
from django.template.loader import select_template
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from fsm_admin.mixins import FSMTransitionMixin
from shop.models.order import OrderItemModel, OrderPayment
from shop.modifiers.pool import cart_modifiers_pool
from shop.rest import serializers


class OrderPaymentInline(admin.TabularInline):
    model = OrderPayment
    extra = 0
    fields = ('amount', 'transaction_id', 'payment_method', 'created_at',)
    readonly_fields = ('created_at',)

    def get_formset(self, request, obj=None, **kwargs):
        """
        Convert the field `payment_method` into a select box with all possible payment methods.
        """
        choices = [pm.get_choice() for pm in cart_modifiers_pool.get_payment_modifiers()]
        kwargs.update(widgets={'payment_method': widgets.Select(choices=choices)})
        formset = super(OrderPaymentInline, self).get_formset(request, obj, **kwargs)
        return formset


class OrderItemInline(admin.StackedInline):
    model = OrderItemModel
    extra = 0
    readonly_fields = ('product_identifier', 'product_name', 'unit_price', 'line_total', 'extra',)
    fields = (
        ('product_identifier', 'product_name',),
        ('quantity', 'unit_price', 'line_total',),
        'extra',
    )

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(OrderItemInline, self).get_formset(request, obj, **kwargs)
        return formset


class BaseOrderAdmin(FSMTransitionMixin, admin.ModelAdmin):
    list_display = ('id', 'customer', 'status_name', 'total', 'created_at',)
    list_filter = ('status', 'customer',)
    search_fields = ('id', 'customer__user__email', 'customer__user__lastname',)
    fsm_field = ('status',)
    date_hierarchy = 'created_at'
    inlines = (OrderItemInline, OrderPaymentInline,)
    readonly_fields = ('status_name', 'customer', 'total', 'subtotal', 'outstanding_amount',
        'created_at', 'updated_at', 'extra', 'stored_request',)
    fields = ('status_name', ('created_at', 'updated_at'), ('subtotal', 'total', 'outstanding_amount',),
        'customer', 'extra', 'stored_request',)

    def get_form(self, request, obj=None, **kwargs):
        # must add field `extra` on the fly.
        #Form = type('TextLinkForm', (TextLinkFormBase,), {'ProductModel': ProductModel, 'product': product_field})
        #kwargs.update(form=Form)
        return super(BaseOrderAdmin, self).get_form(request, obj, **kwargs)

    def outstanding_amount(self, obj):
        return obj.get_outstanding_amount()
    outstanding_amount.short_description = _("Outstanding amount")


class PrintOrderAdminMixin(object):
    """
    A customized OrderAdmin class shall inherit from this mixin class, to add
    methods for printing the delivery note and the invoice.
    """
    def __init__(self, *args, **kwargs):
        self.fields += ('print_out',)
        self.readonly_fields += ('print_out',)
        super(PrintOrderAdminMixin, self).__init__(*args, **kwargs)

    def get_urls(self):
        my_urls = patterns('',
            url(r'^(?P<pk>\d+)/print_delivery_note/$', self.admin_site.admin_view(self.render_delivery_note),
                name='print_delivery_note'),
            url(r'^(?P<pk>\d+)/print_invoice/$', self.admin_site.admin_view(self.render_invoice),
                name='print_invoice'),
        )
        return my_urls + super(PrintOrderAdminMixin, self).get_urls()

    def _render_letter(self, request, pk, template):
        order = self.get_object(request, pk)
        order_serializer = serializers.OrderDetailSerializer(order, context={'request': request})
        context = RequestContext(request, {
            'customer': serializers.CustomerSerializer(order.customer).data,
            'data': order_serializer.data,
            'order': order,
        })
        content = template.render(context)
        return HttpResponse(content)

    def render_delivery_note(self, request, pk=None):
        template = select_template([
            '{}/print/delivery-note.html'.format(settings.SHOP_APP_LABEL.lower()),
            'shop/print/delivery-note.html'
        ])
        return self._render_letter(request, pk, template)

    def render_invoice(self, request, pk=None):
        template = select_template([
            '{}/print/invoice.html'.format(settings.SHOP_APP_LABEL.lower()),
            'shop/print/invoice.html'
        ])
        return self._render_letter(request, pk, template)

    def print_out(self, obj):
        if obj.status == 'pick_goods':
            button = reverse('admin:print_delivery_note', args=(obj.id,)), _("Delivery Note")
        elif obj.status == 'pack_goods':
            button = reverse('admin:print_invoice', args=(obj.id,)), _("Invoice")
        else:
            button = None
        if button:
            return format_html(
                '<span class="object-tools"><a href="{0}" class="viewsitelink" target="_new">{1}</a></span>',
                *button)
        return ''
    print_out.short_description = _("Print out")
    print_out.allow_tags = True


class OrderAdmin(BaseOrderAdmin):
    """
    Admin class to be used with `shop.models.defauls.order`
    """
    search_fields = BaseOrderAdmin.search_fields + ('shipping_address_text', 'billing_address_text',)
    fields = BaseOrderAdmin.fields + (('shipping_address_text', 'billing_address_text',),)
