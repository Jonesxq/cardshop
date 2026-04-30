from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminConsoleUser
from .serializers import serialize_admin_me


class AdminMeView(APIView):
    permission_classes = [IsAdminConsoleUser]

    def get(self, request):
        return Response(serialize_admin_me(request.user))
