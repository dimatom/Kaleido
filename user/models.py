from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from django.db import models


class Gender(models.IntegerChoices):
    MALE = 1, '男'
    FEMALE = 2, '女'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=11, unique=True, verbose_name='手机号')
    birth_date = models.DateField(null=True, blank=True)
    gender = models.IntegerField(choices=Gender.choices, default=Gender.MALE)
    age = models.IntegerField(null=True, blank=True)