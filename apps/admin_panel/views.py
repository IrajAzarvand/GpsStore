from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from pathlib import Path
import os
import datetime
from backup import DatabaseBackup
from restore import DatabaseRestore
import logging

logger = logging.getLogger(__name__)

# Security check: Superuser only
def superuser_required(user):
    return user.is_superuser

@method_decorator(user_passes_test(superuser_required), name='dispatch')
class BackupRestoreView(View):
    template_name = 'admin_panel/backup_restore.html'
    backup_dir = settings.BASE_DIR / 'backups'

    def get(self, request):
        backups = []
        if self.backup_dir.exists():
            for item in self.backup_dir.iterdir():
                if item.is_file() and (item.suffix == '.sql' or item.suffix == '.sqlite3'):
                    stat = item.stat()
                    backups.append({
                        'name': item.name,
                        'size': self._format_size(stat.st_size),
                        'created': datetime.datetime.fromtimestamp(stat.st_mtime),
                        'path': str(item)
                    })
        
        # Sort by created date desc
        backups.sort(key=lambda x: x['created'], reverse=True)
        return render(request, self.template_name, {'backups': backups})

    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'create_backup':
            try:
                backup = DatabaseBackup()
                if backup.run_backup():
                    messages.success(request, 'Backup created successfully.')
                else:
                    messages.error(request, 'Backup failed. Check server logs.')
            except Exception as e:
                logger.error(f"Backup error: {e}")
                messages.error(request, f'Backup error: {str(e)}')
                
        elif action == 'restore_backup':
            filename = request.POST.get('filename')
            file_path = self.backup_dir / filename
            
            if file_path.exists():
                try:
                    restore = DatabaseRestore()
                    # Determine full restore or partial. Logic in restore.py handles defaults.
                    # We assume full restore for now as per requirements.
                    if restore.restore_database(file_path):
                         messages.success(request, f'Database restored successfully from {filename}.')
                    else:
                         messages.error(request, 'Restore failed. Check server logs.')
                except Exception as e:
                     logger.error(f"Restore error: {e}")
                     messages.error(request, f'Restore error: {str(e)}')
            else:
                 messages.error(request, 'Backup file not found.')
                 
        elif action == 'upload_restore':
            if 'backup_file' in request.FILES:
                uploaded_file = request.FILES['backup_file']
                
                # Security: Check extension
                if not (uploaded_file.name.endswith('.sql') or uploaded_file.name.endswith('.sqlite3')):
                     messages.error(request, 'Invalid file type. Only .sql or .sqlite3 allowed.')
                     return redirect('backup_restore')
                
                # Save file
                upload_dir = self.backup_dir / 'uploaded'
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                save_path = upload_dir / f"uploaded_{timestamp}_{uploaded_file.name}"
                
                with open(save_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                # Perform Restore
                try:
                    restore = DatabaseRestore()
                    if restore.restore_database(save_path):
                         messages.success(request, f'Uploaded backup restored successfully.')
                    else:
                         messages.error(request, 'Restore from uploaded file failed.')
                except Exception as e:
                     logger.error(f"Upload restore error: {e}")
                     messages.error(request, f'Error restoring uploaded file: {str(e)}')
            else:
                messages.error(request, 'No file uploaded.')

        return redirect('backup_restore')

    def _format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
