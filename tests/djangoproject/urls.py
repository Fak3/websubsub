from django.urls import path
from websubsub.views import WssView

from .tasks import websub_handler

urlpatterns = [
    path('websubcallback/<uuid:id>', WssView.as_view(websub_handler), name='wscallback'),
    path('news_websubcallback/<uuid:id>', WssView.as_view(websub_handler), name='news_wscallback'),
]

