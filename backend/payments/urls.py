from django.urls import path

from .views import AlipayNotifyView, DevCompletePaymentView, EasypayNotifyView

urlpatterns = [
    path("alipay/notify", AlipayNotifyView.as_view()),
    path("easypay/notify", EasypayNotifyView.as_view()),
    path("dev/complete", DevCompletePaymentView.as_view()),
]
