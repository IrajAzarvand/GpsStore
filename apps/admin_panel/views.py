from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.apps import apps
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Log
import io
import tempfile
import os


@login_required
@user_passes_test(lambda u: u.is_staff)
def backup_view(request):
    if request.method == 'POST':
        selected_models = request.POST.getlist('models')
        with io.StringIO() as buf:
            call_command('dumpdata', *selected_models, indent=2, stdout=buf)
            data = buf.getvalue()
        return HttpResponse(data, content_type='application/json', headers={'Content-Disposition': 'attachment; filename="backup.json"'})
    else:
        all_models = apps.get_models()
        models_by_app = {}
        for model in all_models:
            app_label = model._meta.app_label
            if app_label not in models_by_app:
                models_by_app[app_label] = []
            models_by_app[app_label].append(model)
        return render(request, 'admin_panel/backup.html', {'models_by_app': models_by_app})


@login_required
@user_passes_test(lambda u: u.is_staff)
def restore_view(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('backup_file')
        if not uploaded_file:
            messages.error(request, 'No file uploaded.')
            return redirect('restore')
        if not uploaded_file.name.endswith('.json'):
            messages.error(request, 'File must be a JSON file.')
            return redirect('restore')
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            call_command('loaddata', temp_file_path)
            messages.success(request, 'Database restored successfully.')
            os.unlink(temp_file_path)
        except Exception as e:
            messages.error(request, f'Error restoring database: {str(e)}')
            if 'temp_file_path' in locals():
                os.unlink(temp_file_path)
        return redirect('restore')
    else:
        return render(request, 'admin_panel/restore.html')


@login_required
@user_passes_test(lambda u: u.is_staff)
def logs_view(request):
    # Get filter parameters
    level_filter = request.GET.get('level', '')
    module_filter = request.GET.get('module', '')
    search_query = request.GET.get('search', '')

    # Base queryset
    logs = Log.objects.all()

    # Apply filters
    if level_filter:
        logs = logs.filter(level=level_filter)
    if module_filter:
        logs = logs.filter(module=module_filter)
    if search_query:
        logs = logs.filter(message__icontains=search_query)

    # Order by creation time descending
    logs = logs.order_by('-created_at')

    # Pagination
    paginator = Paginator(logs, 50)  # 50 logs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get unique levels and modules for filter dropdowns
    levels = Log.objects.values_list('level', flat=True).distinct()
    modules = Log.objects.values_list('module', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'levels': levels,
        'modules': modules,
        'level_filter': level_filter,
        'module_filter': module_filter,
        'search_query': search_query,
    }

    return render(request, 'admin_panel/logs.html', context)
