# -*- coding: utf-8 -*-
# Development Environment Defaults
# This file contains hardcoded defaults for development environment
# DO NOT use these values in production!

DEV_DEFAULTS = {
    # Default passwords for new sites
    "admin_password": "admin@123",
    
    # MariaDB root password (update this to match your actual root password)
    "mysql_root_password": "admin",
    
    # GitHub credentials (optional, for bench get-app operations)
    "github_username": "",
    "github_password": "",
    
    # Default apps to install on new sites
    "default_apps_to_install": [
        "erpnext",
        "custom_reports",
        "bench_manager"
    ],
    
    # Auto-migrate after app installation
    "auto_migrate_after_install": True,
    
    # Auto-setup nginx after site creation
    "auto_setup_nginx": False,
    
    # Email settings for development
    "auto_email_id": "noreply@localhost",
    "mail_server": "localhost",
    "mail_port": 1025,
}

def get_dev_default(key, fallback=None):
    """Get a development default value"""
    return DEV_DEFAULTS.get(key, fallback)
