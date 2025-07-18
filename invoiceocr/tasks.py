# # invoice_ocr/tasks.py
# from celery import shared_task
# from django.core.files.base import ContentFile

# from ocr_tool.services.ocr_service import process_invoice, ParseError
# from ocr_tool.models import InvoiceExtract

# @shared_task(bind=True, max_retries=3)
# def run_invoice_ocr(self, upload_id: int):
#     from ocr_tool.models import InvoiceUpload
#     upload = InvoiceUpload.objects.get(id=upload_id)
#     try:
#         result = process_invoice(upload.file)
#         InvoiceExtract.objects.create(upload=upload, payload=result, confidence=result["confidence"])
#     except ParseError as exc:
#         upload.status = "failed"
#         upload.error = str(exc)
#         upload.save()
