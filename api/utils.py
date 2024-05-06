from api.models import Order, User, ConfirmEmailToken
from api_test import settings

from typing import Type

from django.core.mail import send_mail, EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """
     отправляем письмо с подтрердждением почты
    """
    if created and not instance.is_active:
        # send an e-mail to the user
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)

        msg = EmailMultiAlternatives(
            # title:
            f"Password Reset Token for {instance.email}",
            # message:
            token.key,
            # from:
            settings.EMAIL_HOST_USER,
            # to:
            [instance.email]
        )
        msg.send()

def send_order_status_email(user_id, status=None):
    user = User.objects.get(id=user_id)
    user_email = user.email
    status = 'СФОРМИРОВАН' if status is True else 'ОТМЕНЕН'
    subject = f'Обновление статуса'
    message = f'Статус вашего заказа изменен на ЗАКАЗ {status}'
    sender_email = settings.EMAIL_HOST_USER
    recipient_list = [user_email]
    send_mail(subject, message, sender_email, recipient_list)