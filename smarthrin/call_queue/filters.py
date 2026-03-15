"""Filters for CallQueue and CallQueueItem."""
import django_filters

from .models import CallQueue, CallQueueItem


class CallQueueFilterSet(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=CallQueue.Status.choices)
    job = django_filters.UUIDFilter(field_name="job_id")

    class Meta:
        model = CallQueue
        fields = ["status", "job"]


class CallQueueItemFilterSet(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=CallQueueItem.Status.choices)
    application = django_filters.UUIDFilter(field_name="application_id")

    class Meta:
        model = CallQueueItem
        fields = ["status", "application"]
