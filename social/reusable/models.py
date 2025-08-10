import importlib

from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


def get_network_model(class_name):
    models_module = importlib.import_module("network.models")
    return getattr(models_module, class_name)
