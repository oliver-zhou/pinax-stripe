from rest_framework import serializers

from .models import (
                      Plan,
                      Coupon,
                      EventProcessingException,
                      Event,
                      Transfer,
                      TransferChargeFee,
                      Customer,
                      Card,
                      # BitcoinReceiver,
                      Subscription,
                      Invoice,
                      InvoiceItem,
                      Charge,
                      )


class PlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan


class CouponSerializer(serializers.ModelSerializer):

    class Meta:
        model = Coupon


class EventProcessingExceptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = EventProcessingException


class EventSerializer(serializers.ModelSerializer):
    # event_processing_exception = EventProcessingExceptionSerializer(read_only=True, many=True)

    class Meta:
        model = Event


class TransferSerializer(serializers.ModelSerializer):

    class Meta:
        model = Transfer


class TransferChargeFeeSerializer(serializers.ModelSerializer):

    class Meta:
        model = TransferChargeFee


class CardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Card


class SubscriptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subscription


class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer


class ChargeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Charge


class InvoiceItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = InvoiceItem


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    charges = ChargeSerializer(many=True, read_only=True)
    class Meta:
        model = Invoice
