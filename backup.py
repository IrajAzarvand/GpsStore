#!/usr/bin/env python
"""
GPS Store Database Backup Script
Creates automated backups of the database and media files
"""

import os
import sys
import shutil
import datetime
import subprocess
from pathlib import Path

# Add Django project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gps_store.settings')

import django
django.setup()

from django.conf import settings
from django.core.management import call_command


class DatabaseBackup:
    def __init__(self):
        self.backup_dir = BASE_DIR / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    def create_database_backup(self):
        """Create database backup"""
        print("Creating database backup...")

        db_settings = settings.DATABASES['default']
        engine = db_settings['ENGINE']

        if 'sqlite3' in engine:
            # SQLite backup
            db_path = db_settings['NAME']
            backup_path = self.backup_dir / f'db_backup_{self.timestamp}.sqlite3'
            shutil.copy2(db_path, backup_path)
            print(f"SQLite backup created: {backup_path}")

        elif 'postgresql' in engine:
            # PostgreSQL backup
            db_name = db_settings['NAME']
            db_user = db_settings.get('USER', '')
            db_host = db_settings.get('HOST', 'localhost')
            db_port = db_settings.get('PORT', '5432')

            backup_path = self.backup_dir / f'db_backup_{self.timestamp}.sql'
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-f', str(backup_path),
                '--no-password',
                '--format=custom'
            ]

            try:
                subprocess.run(cmd, check=True, env={'PGPASSWORD': db_settings.get('PASSWORD', '')})
                print(f"PostgreSQL backup created: {backup_path}")
            except subprocess.CalledProcessError as e:
                print(f"PostgreSQL backup failed: {e}")
                return False

        return True

    def create_media_backup(self):
        """Create media files backup"""
        print("Creating media files backup...")

        media_dir = BASE_DIR / 'media'
        if media_dir.exists():
            backup_path = self.backup_dir / f'media_backup_{self.timestamp}'
            shutil.copytree(media_dir, backup_path, dirs_exist_ok=True)
            print(f"Media backup created: {backup_path}")
            return True
        else:
            print("Media directory not found, skipping media backup")
            return True

    def create_fixtures_backup(self):
        """Create Django fixtures backup"""
        print("Creating fixtures backup...")

        fixtures_dir = self.backup_dir / 'fixtures'
        fixtures_dir.mkdir(exist_ok=True)

        # List of apps to backup
        apps_to_backup = [
            'accounts', 'products', 'cart', 'orders', 'payments',
            'gps_devices', 'tracking', 'subscriptions', 'api', 'admin_panel'
        ]

        for app in apps_to_backup:
            try:
                fixture_path = fixtures_dir / f'{app}_{self.timestamp}.json'
                with open(fixture_path, 'w', encoding='utf-8') as f:
                    call_command('dumpdata', app, stdout=f, indent=2)
                print(f"Fixture created for {app}: {fixture_path}")
            except Exception as e:
                print(f"Failed to create fixture for {app}: {e}")

        return True

    def cleanup_old_backups(self, days=30):
        """Remove backups older than specified days"""
        print(f"Cleaning up backups older than {days} days...")

        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)

        for item in self.backup_dir.iterdir():
            if item.is_file() or item.is_dir():
                try:
                    # Extract date from filename
                    if '_' in item.name:
                        date_str = item.name.split('_')[1] if len(item.name.split('_')) > 1 else item.name.split('_')[0]
                        if len(date_str) >= 8:  # YYYYMMDD
                            file_date = datetime.datetime.strptime(date_str[:8], '%Y%m%d')
                            if file_date < cutoff_date:
                                if item.is_dir():
                                    shutil.rmtree(item)
                                else:
                                    item.unlink()
                                print(f"Removed old backup: {item}")
                except (ValueError, OSError) as e:
                    print(f"Error processing {item}: {e}")

    def run_backup(self):
        """Run complete backup process"""
        print(f"Starting backup process at {datetime.datetime.now()}")

        success = True
        success &= self.create_database_backup()
        success &= self.create_media_backup()
        success &= self.create_fixtures_backup()
        self.cleanup_old_backups()

        if success:
            print("Backup completed successfully!")
        else:
            print("Backup completed with errors!")

        return success


if __name__ == '__main__':
    backup = DatabaseBackup()
    backup.run_backup()