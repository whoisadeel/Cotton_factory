from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.settings_app'
    verbose_name = 'Settings'

    def ready(self):
        """Start the background scheduler when Django starts."""
        import os
        # Only start in the main process (not in management commands or migrations)
        if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('SCHEDULER_ENABLED'):
            try:
                from .scheduler import start_scheduler
                start_scheduler()
            except Exception as e:
                import logging
                logging.getLogger('scheduler').warning(f"Scheduler not started: {e}")
