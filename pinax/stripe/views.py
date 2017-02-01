import json

from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.encoding import smart_str
from django.views.generic import TemplateView, DetailView, View, FormView, ListView
from django.views.generic.edit import FormMixin
from django.views.decorators.csrf import csrf_exempt

import stripe

from .actions import events, exceptions, customers, subscriptions, sources
from .conf import settings
from .forms import PlanForm, PaymentMethodForm
from .mixins import LoginRequiredMixin, CustomerMixin, PaymentsContextMixin
from .models import (
                     Invoice,
                     Card,
                     Subscription,
                     Customer,
                     Plan,
                     )
from .serializers import (
                          InvoiceSerializer,
                          CardSerializer,
                          SubscriptionSerializer,
                          CustomerSerializer,
                          PlanSerializer,
                          )

from rest_framework.decorators import detail_route, list_route
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.utils.encoding import smart_str

from django.db.models import Q


class StripeView(APIView):
    """ Generic API StripeView """
    permission_classes = (IsAuthenticated, )

    def get_current_subscription(self):
        try:
            return self.request.user.customer.subscriptions
        except Subscription.DoesNotExist:
            return None

    def get_customer(self):
        try:
            return self.request.user.customer
        except ObjectDoesNotExist:
            return Customer.create(self.request.user)


class InvoiceListView(StripeView, generics.ListAPIView, CustomerMixin):
    '''DRF APIView List Invoices'''
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        customer = self.get_customer()
        return customer.invoices.all()


class PaymentMethodView(StripeView, generics.RetrieveUpdateDestroyAPIView, CustomerMixin):
    '''Combine PaymentMethod List, Create, Delete, and Update Views'''
    queryset = Card.objects.all()
    serializer_class = CardSerializer

    # ListView
    def get_queryset(self):
        customer = self.get_customer()
        return customer.cards.all()

    # CreateView
    def create_card(self, stripe_token):
        # Messed up, but so is the default.
        customer = self.get_customer()
        print("Stripe Token {}".format(stripe_token))
        sources.create_card(customer, token=stripe_token)

    def post(self, request, *args, **kwargs):
        try:
            self.create_card(request.data.get("stripeToken"))
            return Response(
                            status=status.HTTP_201_CREATED,
                            )
        except stripe.CardError as e:
            return Response(self.get_context_data(errors=smart_str(e)))

    # DeleteView
    def delete_card(self, stripe_id):
        sources.delete_card(self.customer, stripe_id)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.delete_card(self.object.stripe_id)
            return Response(
                            status=status.HTTP_200_OK,
                            )
        except stripe.CardError as e:
            return Response(self.get_context_data(errors=smart_str(e)))

    # UpdateView
    def update_card(self, exp_month, exp_year):
        sources.update_card(self.customer, self.object.stripe_id, exp_month=exp_month, exp_year=exp_year)

    def form_valid(self, form):
        '''Check Valditiy of Update

        TODO : Not actually validated that we're checking validity properly right now'''
        try:
            self.update_card(form.cleaned_data["expMonth"], form.cleaned_data["expYear"])
            return Response(
                            status=status.HTTP_200_OK,
                            )
        except stripe.CardError as e:
            return Response(self.get_context_data(errors=smart_str(e)))

    def patch(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form(form_class=self.form_class)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class PaymentMethodListView(StripeView, generics.ListAPIView, CustomerMixin):
    '''DRF APIView List Invoices'''
    queryset = Card.objects.all()
    serializer_class = CardSerializer

    def get_queryset(self):
        customer = self.get_customer()
        return customer.cards.all()


class PaymentMethodCreateView(StripeView, generics.CreateAPIView, CustomerMixin, PaymentsContextMixin):
    '''DRF APIView Create Payment Method (Card)'''
    queryset = Card.objects.all()
    serializer_class = CardSerializer

    def create_card(self, stripe_token):
        # Messed up, but so is the default.
        customer = self.get_customer()
        print("Stripe Token {}".format(stripe_token))
        sources.create_card(customer, token=stripe_token)

    def post(self, request, *args, **kwargs):
        try:
            print("Request.data: {}".format(request.data))
            self.create_card(request.data.get("stripeToken"))
            return Response(
                            {'status': 'Payment Method Added'},
                            status=status.HTTP_201_CREATED,
                            )
        except stripe.CardError as e:
            return Response(self.get_context_data(errors=smart_str(e)))


class PaymentMethodDeleteView(StripeView, generics.DestroyAPIView, CustomerMixin):
    '''DRF APIView Delete Payment Method (Card)'''
    queryset = Card.objects.all()
    serializer_class = CardSerializer

    def delete_card(self, stripe_id):
        customer = self.get_customer()
        sources.delete_card(customer, stripe_id)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.delete_card(self.object.stripe_id)
            return Response(
                            {'status': 'Payment Method Deleted'},
                            status=status.HTTP_200_OK,
                            )
        except stripe.CardError as e:
            return Response(self.get_context_data(errors=smart_str(e)))


class PaymentMethodUpdateView(StripeView, generics.UpdateAPIView, CustomerMixin, PaymentsContextMixin):
    '''DRF APIView Update Payment Method (Card)

    TODO : Add more Validation on Fields like the Django App Version
    '''
    queryset = Card.objects.all()
    serializer_class = CardSerializer

    def update_card(self, exp_month, exp_year):
        customer = self.get_customer()
        sources.update_card(customer, self.object.stripe_id, exp_month=exp_month, exp_year=exp_year)
        return Response({'status': 'Card Updated'})

    def patch(self, request, *args, **kwargs):
        self.object = self.get_object()
        print("Payment Update Patch {}, request {}".format(self.object, repr(request.data)))
        return self.update_card(request.data.get('expMonth'), request.data.get('expYear'))

    def put(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.update_card(request.data.get('expMonth'), request.data.get('expYear'))


class SubscriptionView(StripeView):
    """ See, change/set the current customer/user subscription plan """
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()


class SubscriptionViewSet(StripeView, viewsets.ModelViewSet, CustomerMixin):
    ''' Combine Subscription ListView, CreateView, DeleteView, UpdateView '''
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()
    @property
    def current_plan(self):
        if not hasattr(self, "_current_plan"):
            self._current_plan = self.object.plan
        return self._current_plan

    def update_subscription(self, plan_id, **kwargs):
        print("Plan ID {}".format(plan_id))
        subscriptions.update(self.object, plan_id)

    def get_initial(self):
        initial = super(SubscriptionUpdateView, self).get_initial()
        initial.update({
            "plan": self.current_plan
        })
        return initial

    def data_valid(self, plan, **kwargs):
        '''Data Validty Check of Plan Name'''
        customer = self.get_customer()
        print("Customer {}".format(customer))
        try:
            message = "PATCH/UPDATE Subscription for Customer {} for Plan {} for Token {}".format(
                                                                                        customer,
                                                                                        self.request.data.get("plan"),
                                                                                        self.request.data.get("stripeToken"),
                                                                                        )
            plan=self.request.data.get("plan")
            print("Plan {}".format(plan))
            self.update_subscription(plan, **kwargs)
            return Response(
                            data=message,
                            status=status.HTTP_200_OK,
                            )
        except stripe.StripeError as e:
            return Response(errors=smart_str(e))
        except Exception as e:
            return Response(errors=smart_str(e))

    def update(self, request, pk=None, **kwargs):
        self.object = self.get_object()
        print("Request.data {}".format(request.data))
        try:
            plan=self.request.data.get("plan")
            print("Plan {}".format(plan))
            return self.data_valid(plan, **kwargs)
        except:
            return Response(
                            self.serializer_class.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                            )

class SubscriptionListView(StripeView, generics.ListAPIView, CustomerMixin):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return self.get_current_subscription()



class SubscriptionCreateView(StripeView, generics.CreateAPIView, PaymentsContextMixin, CustomerMixin):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

    @property
    def tax_percent(self):
        return settings.PINAX_STRIPE_SUBSCRIPTION_TAX_PERCENT

    def subscribe(self, customer, plan, token):
        subscriptions.create(customer, plan, token=token, tax_percent=self.tax_percent)

    def post(self, request, *args, **kwargs):
        customer = self.get_customer()
        # try:request.POST.get("stripeToken")
        self.subscribe(customer, plan=self.request.data.get("plan"), token=self.request.data.get("stripeToken"))
        message = "POST/CREATE Subscription for Customer {} for Plan {} for Token {}".format(
                                                                                        customer,
                                                                                        self.request.data.get("plan"),
                                                                                        self.request.data.get("stripeToken"),
                                                                                        )
        return Response(
                        data=message,
                        status=status.HTTP_201_CREATED,
                        )
        # except stripe.StripeError as e:
        #     return Response(self.get_context_data(errors=smart_str(e)))


class SubscriptionDeleteView(StripeView, generics.DestroyAPIView, PaymentsContextMixin, CustomerMixin):
    '''Sets specific Subscription to end.

    Doesn't immediately delete, it sets cancel_at_period_end to True'''
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

    def cancel(self):
        subscriptions.cancel(self.object)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        customer = self.get_customer()
        try:
            self.cancel()
            message = "DELETE Subscription for Customer {} for Plan {} for Token {}".format(
                                                                                        customer,
                                                                                        self.request.data.get("plan"),
                                                                                        self.request.data.get("stripeToken"),
                                                                                        )
            return Response(
                            data=message,
                            status=status.HTTP_200_OK,
                            )
        except stripe.StripeError as e:
            return Response(self.get_context_data(errors=smart_str(e)))


class SubscriptionUpdateView(StripeView, generics.UpdateAPIView, PaymentsContextMixin, CustomerMixin):
    '''Not validated fully yet'''
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

    @property
    def current_plan(self):
        if not hasattr(self, "_current_plan"):
            self._current_plan = self.object.plan
        return self._current_plan

    def update_subscription(self, plan_id):
        subscriptions.update(self.object, plan_id)

    def get_initial(self):
        initial = super(SubscriptionUpdateView, self).get_initial()
        initial.update({
            "plan": self.current_plan
        })
        return initial

    def data_valid(self, plan):
        customer = self.get_customer()
        try:
            message = "PATCH/UPDATE Subscription for Customer {} for Plan {} for Token {}".format(
                                                                                        customer,
                                                                                        self.request.data.get("plan"),
                                                                                        self.request.data.get("stripeToken"),
                                                                                        )
            plan=self.request.data.get("plan")
            self.update_subscription(plan)
            return Response(
                            data=message,
                            status=status.HTTP_200_OK,
                            )
        except stripe.StripeError as e:
            return Response(errors=smart_str(e))

    def patch(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            plan=self.request.data.get("plan")
            return self.data_valid(plan)
        except:
            return Response(
                            self.serializer_class.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                            )

    def put(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            plan=self.request.data.get("plan")
            return self.data_valid(plan)
        except:
            return Response(
                            self.serializer_class.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                            )


class Webhook(StripeView):

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(Webhook, self).dispatch(*args, **kwargs)

    def extract_json(self):
        data = json.loads(smart_str(self.request.body))
        return data

    def post(self, request, *args, **kwargs):
        data = self.extract_json()
        if events.dupe_event_exists(data["id"]):
            exceptions.log_exception(data, "Duplicate event record")
        else:
            events.add_event(
                stripe_id=data["id"],
                kind=data["type"],
                livemode=data["livemode"],
                message=data
            )
        return HttpResponse()


class CustomerViewSet(viewsets.ModelViewSet):
    """ See the current customer/user payment details """

    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()


class PlanViewSet(viewsets.ModelViewSet):
    '''Plan Viewset'''
    serializer_class = PlanSerializer
    queryset = Plan.objects.all()

