# Development Configuration - Pre-configured Passwords

## Overview
This feature allows you to hardcode common passwords and credentials for your development environment, eliminating the need to enter them repeatedly when creating or managing sites.

## Configuration File
**Location**: `bench_manager/dev_config.py`

## Default Settings

```python
DEV_DEFAULTS = {
    "admin_password": "admin",           # Default admin password for new sites
    "mysql_root_password": "root",       # Your MariaDB root password
    "github_username": "",               # Optional: for bench get-app
    "github_password": "",               # Optional: for bench get-app
}
```

## How to Configure

1. **Update MySQL Root Password**:
   Edit `bench_manager/dev_config.py` and set your actual MariaDB root password:
   ```python
   "mysql_root_password": "your_actual_root_password",
   ```

2. **Change Default Admin Password** (optional):
   ```python
   "admin_password": "your_preferred_admin_password",
   ```

## Features Enabled

### 1. **Create New Site**
- No need to enter admin password or MySQL password
- Automatically uses values from `dev_config.py`
- Falls back to "admin" and "root" if config file is missing

### 2. **Reinstall Site**
- Admin password automatically filled from config
- No manual password entry required

### 3. **Drop Site**
- MySQL root password automatically filled from config
- No manual password entry required

### 4. **Password Verification**
- Automatically provides passwords when checking if they exist
- Seamless integration with Bench Manager UI

## Usage Examples

### Creating a New Site
```python
# Before: Had to provide passwords manually
create_site("mysite.local", "true", "root", "admin", "key123")

# After: Passwords optional, uses dev_config defaults
create_site("mysite.local", "true", key="key123")
```

### Reinstalling a Site
```python
# Before: Had to provide admin password
site.console_command(key="key123", caller="reinstall", admin_password="admin")

# After: Password optional, uses dev_config default
site.console_command(key="key123", caller="reinstall")
```

### Dropping a Site
```python
# Before: Had to provide MySQL password
site.console_command(key="key123", caller="drop_site", mysql_password="root")

# After: Password optional, uses dev_config default
site.console_command(key="key123", caller="drop_site")
```

## Security Warning

⚠️ **IMPORTANT**: This configuration is for **DEVELOPMENT ENVIRONMENTS ONLY**!

- Never use these hardcoded passwords in production
- Never commit actual passwords to version control
- Add `dev_config.py` to `.gitignore` if using real credentials

## Fallback Behavior

If `dev_config.py` is missing or import fails:
- MySQL password defaults to: `"root"`
- Admin password defaults to: `"admin"`

This ensures the app continues to work even without the config file.

## Modified Files

The following files have been updated to support this feature:
1. `bench_manager/dev_config.py` - Configuration file (NEW)
2. `bench_manager/bench_manager/doctype/site/site.py` - Updated functions:
   - `create_site()` - Uses dev defaults for passwords
   - `console_command()` - Uses dev defaults for reinstall/drop operations
   - `pass_exists()` - Returns dev defaults when passwords not in config

## Testing

After configuration, test by:
1. Creating a new site without providing passwords
2. Reinstalling a site without providing admin password
3. Verifying passwords are correctly applied

## Troubleshooting

**Issue**: Passwords not working
- **Solution**: Verify `mysql_root_password` in `dev_config.py` matches your actual MariaDB root password

**Issue**: Import error
- **Solution**: Ensure `dev_config.py` is in the correct location: `bench_manager/dev_config.py`

**Issue**: Still being prompted for passwords
- **Solution**: Clear bench cache: `bench clear-cache`
