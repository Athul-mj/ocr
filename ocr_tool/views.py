from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, parsers

from .serializers import InvoiceUploadSerializer
from .services.ocr_service import process_invoice, ParseError

class InvoiceOCRAPIView(APIView):
    parser_classes = [parsers.MultiPartParser]

    def post(self, request):
        ser = InvoiceUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            data = process_invoice(ser.validated_data["file"])
            return Response(data, status=status.HTTP_200_OK)
        except ParseError as e:
            return Response({"detail": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ValueError as e:           # unsupported ext, etc.
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

