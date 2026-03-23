from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="analytics-dashboard"),
    path("funnel/", views.funnel, name="analytics-funnel"),
    path("scores/", views.scores, name="analytics-scores"),
    path("timeline/", views.timeline, name="analytics-timeline"),
    path("export/", views.export_report, name="analytics-export"),
]
