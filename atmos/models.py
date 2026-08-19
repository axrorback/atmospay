import uuid
from django.db import models


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('paid', 'To\'landi'),
        ('failed', 'Xatolik / Bekor qilindi'),
    )

    account = models.CharField(max_length=64, unique=True, default=uuid.uuid4, verbose_name="Account / Order ID")
    amount = models.BigIntegerField(help_text="Summa tiyinda (masalan: 1000 sum = 100000 tiyin)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    payment_id = models.IntegerField(null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    checkout_url = models.URLField(max_length=500, null=True, blank=True)

    transaction_id = models.CharField(max_length=255, null=True, blank=True)
    transaction_time = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"Order {self.account} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    items_id = models.CharField(max_length=64)
    code = models.CharField(max_length=64, help_text="IKPU / ИКПУ kod",null=True, blank=True)
    name = models.CharField(max_length=255)
    amount = models.BigIntegerField(help_text="Birlik narxi tiyinda")
    quantity = models.IntegerField(default=1)

    package_code = models.CharField(max_length=64, help_text="Kod upakovki")
    mark_code = models.CharField(max_length=255, null=True, blank=True, help_text="Kod markirovki")
    tin = models.CharField(max_length=32, null=True, blank=True, help_text="INN/PINFL")
    discount = models.BigIntegerField(default=0, help_text="Chegirma tiyinda")

    def __str__(self):
        return f"{self.name} x {self.quantity}"