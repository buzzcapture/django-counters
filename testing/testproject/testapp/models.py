from django.db import models

# Create your models here.


class TestModel(models.Model):
    char_field = models.CharField(max_length=20)

