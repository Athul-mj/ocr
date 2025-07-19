from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import traceback

class InvoiceOCRView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            file = request.FILES.get("file")

            if not file:
                return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

            # 👉 Dummy OCR logic (replace with real OCR)
            # result = your_ocr_library.extract_text(file)
            result = {"text": "Sample OCR result"}

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ Exception during OCR POST request:", str(e))
            traceback.print_exc()  # 👈 This will show full error in Render logs
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
