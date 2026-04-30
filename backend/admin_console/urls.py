from django.urls import path

from .views import AdminMeView


urlpatterns = [
    path("me", AdminMeView.as_view()),
]
