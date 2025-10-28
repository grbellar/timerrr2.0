#!/usr/bin/env python3
"""
Migration script to add trial-related columns to existing users table.
This is a one-time migration script for the free trial feature.
"""

import sqlite3
import os
from datetime import datetime, timezone

def migrate_database():
    """Add trial_started_at and banner_dismissed columns to users table"""

    # Get database path from environment or use default
    db_path = os.environ.get('DATABASE_PATH', 'timerrr.db')

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("No migration needed - new database will be created with correct schema")
        return

    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        migrations_applied = []

        # Add trial_started_at column if it doesn't exist
        if 'trial_started_at' not in columns:
            print("Adding trial_started_at column...")
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN trial_started_at DATETIME
            """)

            # Set trial_started_at for existing FREE tier users to now
            # This gives them a 14-day trial starting from the migration
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                UPDATE users
                SET trial_started_at = ?
                WHERE tier = 'Free' AND trial_started_at IS NULL
            """, (now,))

            migrations_applied.append("trial_started_at column added")
        else:
            print("trial_started_at column already exists")

        # Add banner_dismissed column if it doesn't exist
        if 'banner_dismissed' not in columns:
            print("Adding banner_dismissed column...")
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN banner_dismissed BOOLEAN DEFAULT 0
            """)
            migrations_applied.append("banner_dismissed column added")
        else:
            print("banner_dismissed column already exists")

        # Commit changes
        conn.commit()

        if migrations_applied:
            print("\nMigration completed successfully!")
            print("Applied migrations:")
            for migration in migrations_applied:
                print(f"  - {migration}")
        else:
            print("\nNo migration needed - database already up to date")

        # Show summary
        cursor.execute("SELECT COUNT(*) FROM users WHERE tier = 'Free'")
        free_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE tier = 'Pro'")
        pro_users = cursor.fetchone()[0]

        print(f"\nDatabase summary:")
        print(f"  - Free tier users: {free_users}")
        print(f"  - Pro tier users: {pro_users}")
        print(f"  - Total users: {free_users + pro_users}")

    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
