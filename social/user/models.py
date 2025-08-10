from django.db import models

from reusable.models import BaseModel


class Profile(BaseModel):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    cell_number = models.SlugField(max_length=11, unique=True, null=True, blank=True)
    chat_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    about_me = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"({self.pk} - {self.cell_number})"
