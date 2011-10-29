from django.db import models

# Create your models here.


class ViewCounterValue(models.Model):
    date_stored = models.DateTimeField(db_index=True,verbose_name="A Date field to group related entries")
    view = models.CharField(max_length=100,db_index=True,verbose_name="The view to which these counter relate to")
    counter = models.CharField(max_length=100,verbose_name="Counter name for this view")
    value = models.TextField(verbose_name="counter value, in json format")




