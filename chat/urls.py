from django.urls import path

from .views import ChatMessageView


urlpatterns = [
    path("messages/", ChatMessageView.as_view(), name="chat-message-list-create"),
]
