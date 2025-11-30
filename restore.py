#!/usr/bin/env python
"""
GPS Store Database Restore Script
Restores database and media files from backups
"""

import os
import sys
import shutil
import glob
from pathlib import Path

# Add Django project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gps_store.settings')

import django
django.setup()

from django.conf import settings
from django.core.management import call_command


class DatabaseRestore:
    def __init__(self, backup_timestamp=None):
        self.backup_dir = BASE_DIR / 'backups'
        self.timestamp = backup_timestamp

    def find_latest_backup(self, backup_type):
        """Find the latest backup of specified type"""
        pattern = f"{backup_type}_backup_*.sqlite3" if backup_type == 'db' else f"{backup_type}_backup_*"
        backups = list(self.backup_dir.glob(pattern))

        if not backups:
            print(f"No {backup_type} backups found")
            return None

        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return backups[0]

    def restore_database(self, backup_path=None):
        """Restore database from backup"""
        print("Restoring database...")

        if not backup_path:
            backup_path = self.find_latest_backup('db')

        if not backup_path or not backup_path.exists():
            print("Database backup not found")
            return False

        db_settings = settings.DATABASES['default']
        engine = db_settings['ENGINE']

        if 'sqlite3' in engine:
            # SQLite restore
            db_path = db_settings['NAME']
            shutil.copy2(backup_path, db_path)
            print(f"SQLite database restored from: {backup_path}")

        elif 'postgresql' in engine:
            # PostgreSQL restore
            db_name = db_settings['NAME']
            db_user = db_settings.get('USER', '')
            db_host = db_settings.get('HOST', 'localhost')
            db_port = db_settings.get('PORT', '5432')

            cmd = [
                'pg_restore',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '--clean',
                '--if-exists',
                '--no-password',
                str(backup_path)
            ]

            try:
                import subprocess
                subprocess.run(cmd, check=True, env={'PGPASSWORD': db_settings.get('PASSWORD', '')})
                print(f"PostgreSQL database restored from: {backup_path}")
            except subprocess.CalledProcessError as e:
                print(f"PostgreSQL restore failed: {e}")
                return False

        return True

    def restore_media(self, backup_path=None):
        """Restore media files from backup"""
        print("Restoring media files...")

        if not backup_path:
            backup_path = self.find_latest_backup('media')

        if not backup_path or not backup_path.exists():
            print("Media backup not found")
            return False

        media_dir = BASE_DIR / 'media'

        # Remove existing media directory
        if media_dir.exists():
            shutil.rmtree(media_dir)

        # Copy backup to media directory
        shutil.copytree(backup_path, media_dir)
        print(f"Media files restored from: {backup_path}")
        return True

    def restore_fixtures(self, fixtures_dir=None):
        """Restore data from Django fixtures"""
        print("Restoring fixtures...")

        if not fixtures_dir:
            fixtures_dir = self.backup_dir / 'fixtures'

        if not fixtures_dir.exists():
            print("Fixtures directory not found")
            return False

        # Find latest fixtures
        fixture_files = list(fixtures_dir.glob('*.json'))
        if not fixture_files:
            print("No fixture files found")
            return False

        # Sort by modification time (newest first)
        fixture_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Load each fixture
        for fixture_file in fixture_files:
            try:
                print(f"Loading fixture: {fixture_file}")
                call_command('loaddata', str(fixture_file))
            except Exception as e:
                print(f"Failed to load fixture {fixture_file}: {e}")
                return False

        return True

    def run_restore(self, include_db=True, include_media=True, include_fixtures=True):
        """Run complete restore process"""
        print("Starting restore process...")

        success = True

        if include_db:
            success &= self.restore_database()

        if include_media:
            success &= self.restore_media()

        if include_fixtures:
            success &= self.restore_fixtures()

        if success:
            print("Restore completed successfully!")
        else:
            print("Restore completed with errors!")

        return success


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Restore GPS Store backups')
    parser.add_argument('--no-db', action='store_true', help='Skip database restore')
    parser.add_argument('--no-media', action='store_true', help='Skip media restore')
    parser.add_argument('--no-fixtures', action='store_true', help='Skip fixtures restore')
    parser.add_argument('--timestamp', help='Specific backup timestamp to restore')

    args = parser.parse_args()

    restore = DatabaseRestore(args.timestamp)
    restore.run_restore(
        include_db=not args.no_db,
        include_media=not args.no_media,
        include_fixtures=not args.no_fixtures
    )


if __name__ == '__main__':
    main()