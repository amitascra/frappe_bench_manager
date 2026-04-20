# Bench Manager

<div align="center">
  <img src="bench_manager/public/images/fa-gamepad.svg" width="200" alt="Bench Manager Logo">
  
  <h3>Enterprise-Grade GUI for Frappe Bench Management</h3>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Frappe](https://img.shields.io/badge/Frappe-Framework-orange.svg)](https://frappeframework.com)
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/amitascra/frappe_bench_manager/pulls)
</div>

---

## 📋 Overview

**Bench Manager** is a comprehensive graphical user interface that extends the capabilities of Frappe Bench with powerful cloud infrastructure management, automated deployment, and real-time synchronization features. Originally designed to emulate Frappe Bench CLI commands, this enhanced version now includes enterprise-grade cloud orchestration capabilities.

### 🎯 Key Capabilities

- **🖥️ Local Bench Management** - Complete GUI for bench operations
- **☁️ Cloud Infrastructure** - Deploy and manage cloud servers (AWS, Azure, GCP)
- **🤖 Agent Deployment** - Automated server provisioning with Ansible
- **🔄 Real-Time Sync** - Automatic synchronization every 15 minutes
- **📦 Site & App Management** - Full lifecycle management
- **🔐 SSL/TLS Management** - Automated certificate provisioning
- **📊 Resource Monitoring** - Server plans and resource allocation

---

## 🚀 Quick Start

### Installation

#### Automated Setup (Recommended)

```bash
# Setup Bench Manager with default configuration
bench setup manager
```

This command will:
1. Create a new site `bench-manager.local`
2. Fetch the bench_manager app from GitHub
3. Install and configure the app automatically

#### Manual Installation

```bash
# Create a new site
bench new-site bench-manager.local

# Get the app
bench get-app https://github.com/amitascra/frappe_bench_manager.git

# Install on site
bench --site bench-manager.local install-app bench_manager

# Start bench
bench start
```

### First-Time Setup

1. Access Bench Manager at `http://bench-manager.local:8000`
2. Login with your administrator credentials
3. Navigate to **Bench Settings** and click **Sync** to populate initial data
4. Configure cloud providers if using infrastructure features

---

## 🌟 Features

### Core Bench Management

#### 1. **Bench Settings**
Central control panel for your bench instance:
- **Update Bench** - Emulates `bench update` command
- **Sync Data** - Automatically discovers and loads:
  - All installed apps
  - All sites in the bench
  - All backup files
- **Configuration Display** - View `common_site_config.json` parameters
- **Real-Time Sync** - Automatic hourly synchronization

#### 2. **Site Management**
Comprehensive site lifecycle management:

| Feature | Description |
|---------|-------------|
| **Migrate** | Apply schema changes and data migrations |
| **Backup** | Create full site backups with files |
| **Install App** | Add apps to existing sites |
| **Uninstall App** | Remove apps from sites |
| **Reinstall** | Fresh site reinstallation |
| **Drop Site** | Delete sites (auto-backup before deletion) |
| **View Site** | Direct browser access to sites |
| **Create Alias** | Multiple domains for one site |
| **Delete Alias** | Remove site aliases |

#### 3. **Site Backup & Restore**
- View all backups (active and archived sites)
- One-click restore to existing or new sites
- Automatic backup before destructive operations
- Backup file management and cleanup

#### 4. **App Management**
- List all installed apps
- View Git repository information
- Track app versions and branches
- Install/uninstall apps across sites

#### 5. **Command Logger**
Complete audit trail of all operations:
- Command source tracking (doctype and docname)
- Execution timestamps
- Status monitoring (Success/Failed/Ongoing)
- Full console output logs

### Cloud Infrastructure Management

#### 6. **Cloud Provider Integration**
Multi-cloud support with unified interface:

**Supported Providers:**
- Amazon Web Services (AWS)
- Microsoft Azure
- Google Cloud Platform (GCP)

**Features:**
- API key management
- SSH key pair generation
- Region selection
- Resource provisioning

#### 7. **Virtual Machine Management**
Deploy and manage cloud servers:
- **Automated Provisioning** - One-click server deployment
- **Agent Installation** - Automated Frappe agent setup
- **SSH Key Management** - Secure access configuration
- **Status Monitoring** - Real-time server status
- **Resource Allocation** - CPU, RAM, storage management

#### 8. **Server Plans**
Pre-configured server templates:
- Small (2 vCPU, 4GB RAM)
- Medium (4 vCPU, 8GB RAM)
- Large (8 vCPU, 16GB RAM)
- Custom configurations

#### 9. **Agent Deployment**
Automated server configuration using Ansible:
- **User Management** - Frappe user creation (UID 2000)
- **Repository Cloning** - Automated agent installation
- **NGINX Configuration** - Web server setup
- **Supervisor Setup** - Process management
- **TLS/SSL** - Certificate configuration
- **Error Handling** - Robust deployment with fallbacks

**Key Improvements:**
- ACL permission handling
- Empty certificate validation
- NGINX module compatibility
- Supervisor command fixes

#### 10. **SSL Certificate Management**
- Certificate generation and renewal
- Let's Encrypt integration
- Multi-domain support
- Automatic NGINX configuration

#### 11. **Load Balancing**
- Proxy server configuration
- Traffic distribution
- Health checks
- Failover management

#### 12. **Database & Application Servers**
- MariaDB server management
- Application server pools
- Connection management
- Performance monitoring

---

## 🔄 Real-Time Synchronization

### Automatic Sync Features

**Smart File Monitoring (Every 15 minutes):**
- Monitors `apps.txt` for new installations
- Watches `site_config.json` for new sites
- Detects new backup files
- Only syncs when changes detected (resource-efficient)

**Guaranteed Hourly Sync:**
- Full synchronization every hour
- Ensures data consistency
- Background processing (non-blocking)

**Manual Sync:**
- On-demand sync via UI button
- Force sync API endpoint
- Immediate updates when needed

### Configuration

Enable/disable in `common_site_config.json`:
```json
{
  "pause_scheduler": 0  // 0 = enabled, 1 = disabled
}
```

Adjust frequency in `hooks.py`:
```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": [  // Every 15 minutes
            "bench_manager.bench_manager.realtime_sync.check_and_sync_if_needed"
        ]
    },
    "hourly": [
        "bench_manager.bench_manager.doctype.bench_settings.bench_settings.auto_sync_all"
    ]
}
```

---

## 🛠️ Development Features

### Pre-configured Development Passwords

Streamline development workflow with automatic password configuration:

**Configuration File:** `bench_manager/dev_config.py`

```python
DEV_DEFAULTS = {
    "admin_password": "admin",
    "mysql_root_password": "root",
    "github_username": "",
    "github_password": "",
}
```

**Benefits:**
- No repetitive password entry
- Faster site creation
- Seamless reinstallation
- Development-optimized workflow

**⚠️ Security Warning:** Development mode only! Never use in production.

---

## 📚 Documentation

### Additional Guides

- **[Real-Time Sync Guide](REALTIME_SYNC_README.md)** - Detailed sync configuration
- **[Development Configuration](DEV_CONFIG_README.md)** - Dev environment setup
- **[Wiki](https://github.com/frappe/bench_manager/wiki)** - Community documentation

### API Reference

**Force Sync Endpoint:**
```python
import frappe
frappe.call("bench_manager.bench_manager.realtime_sync.force_sync_now")
```

**Check Last Sync:**
```python
last_sync = frappe.db.get_single_value("Bench Settings", "last_sync_timestamp")
```

---

## 🏗️ Architecture

### DocTypes Overview

| DocType | Purpose |
|---------|---------|
| **Bench Settings** | Central configuration and sync control |
| **Site** | Site lifecycle management |
| **Site Backup** | Backup and restore operations |
| **App** | Application management |
| **Bench Manager Command** | Command execution logging |
| **Cloud Provider** | Cloud platform credentials |
| **Virtual Machine** | Server instance management |
| **Server Plan** | Resource templates |
| **Site Plan** | Site resource allocation |
| **SSL Certificate** | TLS/SSL management |
| **Agent Job** | Background task tracking |
| **Database Server** | Database instance management |
| **Application Server** | App server management |
| **Proxy Server** | Load balancer configuration |
| **Team** | Multi-tenancy support |

### Technology Stack

- **Framework:** Frappe Framework
- **Backend:** Python 3.8+
- **Database:** MariaDB
- **Queue:** Redis + RQ
- **Automation:** Ansible
- **Cloud APIs:** boto3 (AWS), Azure SDK, GCP SDK
- **Web Server:** NGINX
- **Process Manager:** Supervisor

---

## 🔧 Configuration

### Cloud Provider Setup

#### AWS Configuration

```python
# In Cloud Provider doctype
provider_type = "AWS"
api_key = "YOUR_AWS_ACCESS_KEY"
api_secret = "YOUR_AWS_SECRET_KEY"
region = "ap-south-1"
```

#### SSH Key Management

```bash
# Keys are automatically generated and stored securely
# Format: BenchManager-{provider_name}-key
```

### NGINX Configuration

The agent deployment automatically:
- Removes incompatible directives (`more_set_headers`, `vhost_traffic_status`)
- Configures TLS certificates
- Sets up proxy rules
- Handles empty certificate files gracefully

---

## 🧪 Testing

### Test Site Creation

```bash
# Create test site
bench new-site test.local --admin-password admin

# Verify in Bench Manager (auto-syncs in 15 min)
bench --site bench-manager.local execute \
  "frappe.get_all('Site', pluck='site_name')"
```

### Test App Installation

```bash
# Install app
bench get-app erpnext

# Verify sync
bench --site bench-manager.local execute \
  "frappe.get_all('App', pluck='app_name')"
```

### Test Cloud Deployment

1. Configure Cloud Provider
2. Create Server Plan
3. Deploy Virtual Machine
4. Monitor Agent Job status
5. Verify server accessibility

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup

```bash
# Fork and clone repository
git clone https://github.com/YOUR_USERNAME/frappe_bench_manager.git
cd frappe_bench_manager

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and test
bench --site bench-manager.local migrate
bench --site bench-manager.local clear-cache

# Commit with descriptive message
git commit -m "feat: add new feature description"

# Push and create pull request
git push origin feature/your-feature-name
```

### Code Standards

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to all functions
- Include error handling
- Write unit tests for new features
- Update documentation

### Pull Request Process

1. Ensure all tests pass
2. Update README if needed
3. Add description of changes
4. Link related issues
5. Request review from maintainers

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** Sites not appearing after creation
- **Solution:** Wait 15 minutes for auto-sync or click Sync button manually

**Issue:** Agent deployment fails with ACL error
- **Solution:** Updated in latest version - uses `sudo -u frappe` instead of `become_user`

**Issue:** NGINX unknown directive errors
- **Solution:** Fixed - problematic directives automatically removed

**Issue:** Supervisor reread command fails
- **Solution:** Fixed - now uses `shell` module instead of `command`

**Issue:** Empty TLS certificates cause NGINX failure
- **Solution:** Fixed - certificates validated before NGINX config test

### Debug Mode

```bash
# Enable debug logging
bench --site bench-manager.local set-config developer_mode 1

# View logs
tail -f logs/bench-manager.local.log
```

### Support

- **Issues:** [GitHub Issues](https://github.com/amitascra/frappe_bench_manager/issues)
- **Discussions:** [GitHub Discussions](https://github.com/amitascra/frappe_bench_manager/discussions)
- **Email:** Open an issue for support requests

---

## 📊 Roadmap

### Upcoming Features

- [ ] Kubernetes deployment support
- [ ] Multi-region load balancing
- [ ] Automated backup to S3/Azure Blob
- [ ] Performance metrics dashboard
- [ ] Cost optimization recommendations
- [ ] Terraform integration
- [ ] Docker container support
- [ ] CI/CD pipeline integration

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](license.txt) file for details.

### MIT License Summary

- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use
- ❌ Liability
- ❌ Warranty

---

## 🙏 Acknowledgments

- **Frappe Technologies** - Original Bench Manager concept
- **Frappe Community** - Continuous support and feedback
- **Contributors** - All developers who have contributed to this project

---

## 📞 Contact

- **Repository:** [https://github.com/amitascra/frappe_bench_manager](https://github.com/amitascra/frappe_bench_manager)
- **Issues:** [Report a Bug](https://github.com/amitascra/frappe_bench_manager/issues/new)
- **Feature Requests:** [Request a Feature](https://github.com/amitascra/frappe_bench_manager/issues/new?labels=enhancement)

---

<div align="center">
  <p>Made with ❤️ by the Frappe Community</p>
  <p>
    <a href="#-overview">Back to Top ↑</a>
  </p>
</div>
