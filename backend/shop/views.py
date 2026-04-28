from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_home_payload


class HomeView(APIView):
    permission_classes = [AllowAny]

    def get(self, _request):
        return Response(get_home_payload())

