from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

try:
    from celery import shared_task
except Exception:  # pragma: no cover - Celery is optional in dev envs
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func

        if args and callable(args[0]):
            return args[0]
        return decorator


@shared_task(name='base.tasks.refresh_stale_field_analysis')
def refresh_stale_field_analysis(max_age_days: int = 12, dry_run: bool = False, limit: int | None = None):
    """
    Refresh EE-derived analysis for planting activities whose latest analysis is older than
    the configured freshness threshold. This keeps NDVI, rainfall, risk, and yield values
    renewed in the database without hardcoded frontend placeholders.
    """
    from .models import AnalysisResult, FieldActivity

    cutoff = timezone.now() - timedelta(days=max_age_days)
    queryset = (
        FieldActivity.objects.filter(activity_type='planting', crop__isnull=False)
        .order_by('-date')
    )
    if limit is not None:
        queryset = queryset[:limit]

    refreshed = []

    for activity in queryset:
        latest_result = (
            AnalysisResult.objects.filter(field=activity.field, activity=activity)
            .order_by('-updated_at')
            .first()
        )

        if latest_result and latest_result.updated_at >= cutoff:
            continue

        field_name = activity.field.name if activity.field_id else 'Unknown field'
        crop_name = activity.crop.name if activity.crop_id else 'Unknown crop'

        record = {
            'field_id': activity.field_id,
            'field_name': field_name,
            'activity_id': activity.id,
            'crop_name': crop_name,
            'max_age_days': max_age_days,
            'stale': True,
        }

        if dry_run:
            refreshed.append({**record, 'dry_run': True})
            continue

        try:
            from .views import _run_synchronous

            result, created = AnalysisResult.objects.update_or_create(
                field=activity.field,
                activity=activity,
                defaults={'pipeline_status': 'queued', 'full_bundle': {}},
            )
            _run_synchronous(activity.field_id, activity.id, result.id)
            result.refresh_from_db()

            bundle = result.full_bundle or {}
            yield_value = bundle.get('predicted_yield_t_ha')
            if yield_value is None:
                scientific_yield = bundle.get('scientific_yield') or {}
                yield_value = (
                    scientific_yield.get('predicted_yield_t_ha')
                    or scientific_yield.get('yield_t_ha')
                )

            record.update({
                'dry_run': False,
                'created': created,
                'result_id': result.id,
                'pipeline_status': result.pipeline_status,
                'yield_t_ha': yield_value,
                'ndvi_latest': result.ndvi_latest,
                'latest_scene_date': result.latest_scene_date,
                'total_rainfall_mm': result.total_rainfall_mm,
                'updated_at': result.updated_at.isoformat() if result.updated_at else None,
            })
        except Exception as exc:  # pragma: no cover - task-level error logging
            record.update({
                'dry_run': False,
                'error': str(exc),
                'pipeline_status': 'error',
            })

        refreshed.append(record)

    return {
        'max_age_days': max_age_days,
        'count': len(refreshed),
        'refreshed': refreshed,
    }
