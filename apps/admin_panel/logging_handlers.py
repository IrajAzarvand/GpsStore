try:
    import logging
except ImportError as e:
    print(f"Import error: {e}")


class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that saves log records to the database
    """

    def __init__(self):
        super().__init__()
        print("DatabaseLogHandler instantiated")
    def emit(self, record):
        print(f"DatabaseLogHandler.emit called for: {record.getMessage()}")
        try:
            # Lazy import to avoid AppRegistryNotReady
            import django
            # Removed apps_ready check to allow logging during settings load

            from django.apps import apps
            if 'admin_panel' not in [app.label for app in apps.get_app_configs()]:
                return

            from apps.admin_panel.models import Log

            # Create log entry
            Log.objects.create(
                level=record.levelname,
                message=self.format(record),
                module=record.module,
                function=record.funcName if hasattr(record, 'funcName') else '',
                line_number=record.lineno if hasattr(record, 'lineno') else None,
                process_id=record.process if hasattr(record, 'process') else None,
                thread_id=record.thread if hasattr(record, 'thread') else None,
                extra_data=getattr(record, 'extra_data', {}),
            )
        except Exception as e:
            # Raise exception instead of passing silently
            raise e