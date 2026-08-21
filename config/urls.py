from django.contrib import admin
from django.urls import path , re_path
from atmos import views
urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^webhook/atmos/?$', views.AtmosCallbackView.as_view(), name='atmos_callback'),
    path('api/v1/order/', views.CreateOrderCheckoutView.as_view(), name='create_order'),
]
