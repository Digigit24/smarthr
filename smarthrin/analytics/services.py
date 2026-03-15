from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

def get_dashboard_metrics(tenant_id: str) -> dict:
    """Returns dashboard metrics for the tenant."""
    from jobs.models import Job
    from applications.models import Application
    from calls.models import CallRecord
    today = timezone.now().date()
    return {
        "total_jobs_open": Job.objects.filter(tenant_id=tenant_id, status="OPEN").count(),
        "total_applications": Application.objects.filter(tenant_id=tenant_id).count(),
        "total_calls_completed": CallRecord.objects.filter(tenant_id=tenant_id, status="COMPLETED").count(),
        "avg_candidate_score": Application.objects.filter(
            tenant_id=tenant_id, score__isnull=False
        ).aggregate(avg=Avg("score"))["avg"],
        "applications_today": Application.objects.filter(
            tenant_id=tenant_id, created_at__date=today
        ).count(),
        "calls_today": CallRecord.objects.filter(
            tenant_id=tenant_id, created_at__date=today
        ).count(),
        "shortlisted_count": Application.objects.filter(tenant_id=tenant_id, status="SHORTLISTED").count(),
        "offers_count": Application.objects.filter(tenant_id=tenant_id, status="OFFER").count(),
        "hiring_conversion_rate": _hiring_conversion_rate(tenant_id),
    }

def _hiring_conversion_rate(tenant_id: str) -> float:
    from applications.models import Application
    total = Application.objects.filter(tenant_id=tenant_id).count()
    hired = Application.objects.filter(tenant_id=tenant_id, status="HIRED").count()
    if total == 0:
        return 0.0
    return round((hired / total) * 100, 2)

def get_funnel_data(tenant_id: str) -> list:
    from applications.models import Application
    return list(
        Application.objects.filter(tenant_id=tenant_id)
        .values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

def get_score_distribution(tenant_id: str) -> list:
    """Returns score buckets 0-10, 10-20, ..., 90-100."""
    from applications.models import Application
    from django.db.models import Case, When, IntegerField
    # Return raw scores grouped into buckets
    scores = Application.objects.filter(
        tenant_id=tenant_id, score__isnull=False
    ).values_list("score", flat=True)
    buckets = {f"{i*10}-{(i+1)*10}": 0 for i in range(10)}
    for score in scores:
        bucket_idx = min(int(float(score) / 10), 9)
        key = f"{bucket_idx*10}-{(bucket_idx+1)*10}"
        buckets[key] += 1
    return [{"range": k, "count": v} for k, v in buckets.items()]

def get_timeline_data(tenant_id: str, period: str = "30d") -> list:
    """Returns daily counts of applications, calls, hires."""
    from applications.models import Application
    from calls.models import CallRecord
    from django.db.models.functions import TruncDate
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    since = timezone.now() - timedelta(days=days)

    apps_by_day = (
        Application.objects.filter(tenant_id=tenant_id, created_at__gte=since)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
    )
    calls_by_day = (
        CallRecord.objects.filter(tenant_id=tenant_id, status="COMPLETED", created_at__gte=since)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
    )
    hires_by_day = (
        Application.objects.filter(tenant_id=tenant_id, status="HIRED", created_at__gte=since)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
    )

    # Merge all into a date-keyed dict
    result = {}
    for item in apps_by_day:
        d = str(item["date"])
        result.setdefault(d, {"date": d, "applications": 0, "calls": 0, "hires": 0})
        result[d]["applications"] = item["count"]
    for item in calls_by_day:
        d = str(item["date"])
        result.setdefault(d, {"date": d, "applications": 0, "calls": 0, "hires": 0})
        result[d]["calls"] = item["count"]
    for item in hires_by_day:
        d = str(item["date"])
        result.setdefault(d, {"date": d, "applications": 0, "calls": 0, "hires": 0})
        result[d]["hires"] = item["count"]

    return sorted(result.values(), key=lambda x: x["date"])
