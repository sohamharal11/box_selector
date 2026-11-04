from django.urls import path

from . import views

urlpatterns = [
    path("recommend-box/", views.recommend_box_adhoc, name="recommend-box"),
    path("orders/<str:reference>/recommend-box/", views.order_recommendation, name="order-recommend-box"),
]
