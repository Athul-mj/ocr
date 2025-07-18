from django.urls import path
from .views import *

urlpatterns = [
    path('invoice/', InvoiceOCRAPIView.as_view(), name='invoice-ocr'),
    
]