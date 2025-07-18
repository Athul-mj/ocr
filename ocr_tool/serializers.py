# serializers.py
from rest_framework import serializers
from ocr_tool.utils.invoice_math import calc_invoice_totals

class InvoiceUploadSerializer(serializers.Serializer):
    file = serializers.FileField()         


