import frappe
from frappe import _
import requests
from xml.etree import ElementTree as ET
import html
import re

@frappe.whitelist(allow_guest=True)
def get_app_list(filters=None, fields=None, order_by=None, start=0, limit=20):
    """
    Whitelisted wrapper for fetching App DocType data
    Allows guest users to browse apps
    """
    return frappe.get_list(
        doctype="App",
        fields=fields or ["name", "app_name", "app_title", "app_description", "app_icon", "app_color", "app_logo",
            "category", "pricing_model", "price", "subscription_price", "currency", "rating", "review_count", "total_downloads"],
        filters=filters or {"is_published": 1, "moderation_status": "Approved"},
        order_by=order_by or "total_downloads desc",
        start=start,
        limit=limit
    )

@frappe.whitelist(allow_guest=True)
def get_category_list(fields=None, order_by=None):
    """
    Whitelisted wrapper for fetching App Category DocType data
    Allows guest users to browse categories
    """
    return frappe.get_list(
        doctype="App Category",
        fields=fields or ["name", "category_name", "slug", "description", "icon", "color", "display_order", "app_count"],
        order_by=order_by or "display_order"
    )

@frappe.whitelist(allow_guest=True)
def get_app_details(app_id):
    """
    Whitelisted wrapper for fetching single App document
    Allows guest users to view app details
    """
    app_doc = frappe.get_doc("App", app_id).as_dict()
    
    # Enrich with developer details if developer is linked
    if app_doc.get('developer'):
        try:
            developer = frappe.get_doc("App Developer", app_doc.developer)
            app_doc["developer_name"] = developer.developer_name
            app_doc["developer_avatar"] = developer.avatar
            app_doc["developer_is_verified"] = developer.is_verified
            app_doc["developer_bio"] = developer.bio
            app_doc["total_apps"] = developer.total_apps or 0
        except:
            app_doc["developer_name"] = app_doc.get('app_publisher', 'Unknown')
            app_doc["developer_avatar"] = None
            app_doc["developer_is_verified"] = False
            app_doc["developer_bio"] = None
            app_doc["total_apps"] = 0
    else:
        app_doc["developer_name"] = app_doc.get('app_publisher', 'Unknown')
        app_doc["developer_avatar"] = None
        app_doc["developer_is_verified"] = False
        app_doc["developer_bio"] = None
        app_doc["total_apps"] = 0
    
    # Use the app's name for filtering reviews
    app_name = app_doc.get('name')
    
    # Get reviews for the app
    try:
        reviews = frappe.get_all("App Review",
            filters={"app": app_name},
            fields=["name", "rating", "review_text", "review_date", 
                "is_verified_purchase", "helpful_count", "member"],
            order_by="review_date DESC",
            limit=10,
            ignore_permissions=True  # Allow all users to read reviews
        )
        
        # Enrich reviews with member details
        for review in reviews:
            try:
                # The member field in App Review stores the member's name (ID)
                # Get the member's full_name from the Member doctype
                member_doc = frappe.get_doc("Member", review.member)
                review["member_name"] = member_doc.full_name if member_doc else review.member
            except:
                # If we can't fetch the member doc, use the member field directly
                review["member_name"] = review.member
            # Check if current user owns this review
            if frappe.session.user and frappe.session.user != "Guest":
                try:
                    current_member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
                    review["is_owner"] = review.member == current_member
                except:
                    review["is_owner"] = False
            else:
                review["is_owner"] = False
        
        app_doc["reviews"] = reviews
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get App Reviews Error")
        app_doc["reviews"] = []
    
    # Get current user's review if logged in
    if frappe.session.user and frappe.session.user != "Guest":
        try:
            member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
            if member:
                user_review = frappe.db.get_value("App Review",
                    filters={"app": app_name, "member": member},
                    fieldname=["name", "rating", "review_text", "review_date", "is_verified_purchase"]
                )
                app_doc["user_review"] = user_review
            else:
                app_doc["user_review"] = None
        except:
            app_doc["user_review"] = None
    else:
        app_doc["user_review"] = None
    
    return app_doc

@frappe.whitelist(allow_guest=True)
def get_child_table_data(doctype, parent, fields=None, order_by=None):
    """
    Whitelisted wrapper for fetching child table data
    Allows guest users to view screenshots, tags, etc.
    """
    return frappe.get_list(
        doctype=doctype,
        fields=fields,
        filters={"parent": parent},
        order_by=order_by
    )

@frappe.whitelist(allow_guest=True)
def search_apps(query, start=0, limit=10, developer=None):
    """
    Search apps by title, name, or description
    Similar to ERPNext's awesome bar search functionality
    """
    filters = {
        "is_published": 1,
        "moderation_status": "Approved"
    }

    if query and len(query) >= 2:
        query = query.strip()
        filters["app_title"] = ["like", f"%{query}%"]

    if developer:
        filters["developer"] = developer

    return frappe.get_list(
        doctype="App",
        fields=["name", "app_name", "app_title", "app_description", "app_icon", "app_color", "app_logo",
            "category", "pricing_model", "price", "subscription_price", "currency", "rating", "review_count", "total_downloads"],
        filters=filters,
        order_by="rating desc, total_downloads desc",
        start=start,
        limit=limit
    )

@frappe.whitelist()
def insert_default_app_categories():
    """
    Insert default app categories
    """
    categories = [
        {
            "category_name": "Productivity",
            "description": "Apps to boost your productivity and workflow",
            "icon": "zap",
            "color": "#3b82f6",
            "display_order": 1,
            "is_active": 1
        },
        {
            "category_name": "Business",
            "description": "Business management and ERP solutions",
            "icon": "briefcase",
            "color": "#10b981",
            "display_order": 2,
            "is_active": 1
        },
        {
            "category_name": "Communication",
            "description": "Messaging, email, and collaboration tools",
            "icon": "message-square",
            "color": "#8b5cf6",
            "display_order": 3,
            "is_active": 1
        },
        {
            "category_name": "Analytics",
            "description": "Data analysis and reporting applications",
            "icon": "bar-chart-2",
            "color": "#f59e0b",
            "display_order": 4,
            "is_active": 1
        },
        {
            "category_name": "E-commerce",
            "description": "Online store and shopping cart solutions",
            "icon": "shopping-cart",
            "color": "#ec4899",
            "display_order": 5,
            "is_active": 1
        },
        {
            "category_name": "Frontend Frameworks",
            "description": "Vue3, React, and other frontend integrations for Frappe",
            "icon": "layout",
            "color": "#06b6d4",
            "display_order": 6,
            "is_active": 1
        },
        {
            "category_name": "Integrations",
            "description": "API integrations, payment gateways, and third-party services",
            "icon": "link",
            "color": "#6366f1",
            "display_order": 7,
            "is_active": 1
        },
        {
            "category_name": "Developer Tools",
            "description": "CLI tools, testing frameworks, and debugging utilities",
            "icon": "code",
            "color": "#64748b",
            "display_order": 8,
            "is_active": 1
        },
        {
            "category_name": "Security & Compliance",
            "description": "Security, authentication, and compliance tools",
            "icon": "shield",
            "color": "#dc2626",
            "display_order": 9,
            "is_active": 1
        },
        {
            "category_name": "Automation & Workflows",
            "description": "Automation scripts, workflow engines, and process automation",
            "icon": "git-branch",
            "color": "#8b5cf6",
            "display_order": 10,
            "is_active": 1
        },
        {
            "category_name": "Healthcare",
            "description": "Healthcare, medical, and hospital management solutions",
            "icon": "heart",
            "color": "#ef4444",
            "display_order": 11,
            "is_active": 1
        },
        {
            "category_name": "Education",
            "description": "Learning management systems and educational tools",
            "icon": "book-open",
            "color": "#f97316",
            "display_order": 12,
            "is_active": 1
        },
        {
            "category_name": "Manufacturing",
            "description": "Manufacturing, production, and inventory management",
            "icon": "settings",
            "color": "#78716c",
            "display_order": 13,
            "is_active": 1
        },
        {
            "category_name": "Utilities & Helpers",
            "description": "Utility functions, helpers, and miscellaneous tools",
            "icon": "tool",
            "color": "#4b5563",
            "display_order": 14,
            "is_active": 1
        }
    ]
    
    inserted = []
    for cat_data in categories:
        try:
            if not frappe.db.exists("App Category", {"category_name": cat_data["category_name"]}):
                doc = frappe.get_doc({
                    "doctype": "App Category",
                    **cat_data
                })
                doc.insert()
                inserted.append(doc.name)
                print(f"Inserted: {doc.name}")
            else:
                print(f"Already exists: {cat_data['category_name']}")
        except Exception as e:
            print(f"Error inserting {cat_data['category_name']}: {e}")
    
    return inserted

@frappe.whitelist(allow_guest=True)
def search_developers(query, start=0, limit=10):
    """
    Search app developers by name, email, or company
    """
    if not query or len(query) < 2:
        return []

    query = query.strip()
    is_guest = not frappe.session.user or frappe.session.user == "Guest"

    # Get all developers matching search - search by developer_name first
    developers = frappe.get_list(
        doctype="App Developer",
        fields=["name", "developer_name", "email", "phone", "company_name", "bio", "avatar", "is_verified", "total_apps", "total_downloads", "show_email", "show_phone", "show_company", "show_stats", "github_username", "twitter_username", "linkedin_url", "show_social_links"],
        filters={
            "is_active": 1,
            "developer_name": ["like", f"%{query}%"]
        },
        order_by="total_apps desc, total_downloads desc",
        start=start,
        limit=limit
    )

    # Filter based on privacy settings for guest users
    if is_guest:
        filtered_developers = []
        for dev in developers:
            dev_dict = {
                "name": dev.name,
                "developer_name": dev.developer_name,
                "avatar": dev.avatar,
                "is_verified": dev.is_verified,
                "bio": dev.bio
            }
            # Only show fields if privacy allows (use getattr for backward compatibility)
            if getattr(dev, 'show_email', 1):
                dev_dict["email"] = dev.email
            if getattr(dev, 'show_phone', 0):
                dev_dict["phone"] = dev.phone
            if getattr(dev, 'show_company', 1):
                dev_dict["company_name"] = dev.company_name
            if getattr(dev, 'show_stats', 1):
                dev_dict["total_apps"] = dev.total_apps
                dev_dict["total_downloads"] = dev.total_downloads
            if getattr(dev, 'show_social_links', 1):
                dev_dict["github_username"] = dev.github_username
                dev_dict["twitter_username"] = dev.twitter_username
                dev_dict["linkedin_url"] = dev.linkedin_url
            filtered_developers.append(dev_dict)
        return filtered_developers

    return developers

@frappe.whitelist(allow_guest=True)
def get_developer_details(developer_id):
    """
    Get developer details with privacy settings respected
    """
    if not developer_id:
        return None

    is_guest = not frappe.session.user or frappe.session.user == "Guest"

    developer = frappe.get_value(
        "App Developer",
        {"name": developer_id, "is_active": 1},
        ["name", "developer_name", "email", "phone", "company_name", "website", "bio", "avatar", "is_verified", "total_apps", "total_downloads", "total_earnings", "show_email", "show_phone", "show_company", "show_stats", "github_username", "twitter_username", "linkedin_url", "show_social_links", "creation"]
    )

    if not developer:
        return None

    # Privacy settings (handle missing fields for backward compatibility)
    show_email = developer[12] if len(developer) > 12 else 1
    show_phone = developer[13] if len(developer) > 13 else 0
    show_company = developer[14] if len(developer) > 14 else 1
    show_stats = developer[15] if len(developer) > 15 else 1
    show_social_links = developer[19] if len(developer) > 19 else 1

    # Convert tuple to dict
    dev_dict = {
        "name": developer[0],
        "developer_name": developer[1],
        "avatar": developer[7],
        "is_verified": developer[8],
        "bio": developer[6],
        "creation": developer[20] if len(developer) > 20 else None,
        "show_email": show_email,
        "show_phone": show_phone,
        "show_company": show_company,
        "show_stats": show_stats,
        "show_social_links": show_social_links
    }

    # For logged in users, show all fields
    # For guests, respect privacy settings
    if is_guest:
        if show_email:
            dev_dict["email"] = developer[2]
        if show_phone:
            dev_dict["phone"] = developer[3]
        if show_company:
            dev_dict["company_name"] = developer[4]
            dev_dict["website"] = developer[5]
        if show_stats:
            dev_dict["total_apps"] = developer[9]
            dev_dict["total_downloads"] = developer[10]
            dev_dict["total_earnings"] = developer[11] if len(developer) > 11 else 0
        
        # Always return social links, frontend will handle privacy
        dev_dict["github_username"] = developer[16] if len(developer) > 16 else None
        dev_dict["twitter_username"] = developer[17] if len(developer) > 17 else None
        dev_dict["linkedin_url"] = developer[18] if len(developer) > 18 else None
        dev_dict["show_social_links"] = show_social_links
    else:
        # Logged in users see everything
        dev_dict["email"] = developer[2]
        dev_dict["phone"] = developer[3]
        dev_dict["company_name"] = developer[4]
        dev_dict["website"] = developer[5]
        dev_dict["total_apps"] = developer[9]
        dev_dict["total_downloads"] = developer[10]
        dev_dict["total_earnings"] = developer[11] if len(developer) > 11 else 0
        dev_dict["github_username"] = developer[16] if len(developer) > 16 else None
        dev_dict["twitter_username"] = developer[17] if len(developer) > 17 else None
        dev_dict["linkedin_url"] = developer[18] if len(developer) > 18 else None

    return dev_dict

@frappe.whitelist(allow_guest=True)
def get_website_settings():
    """
    Get Website Settings for frontend (logo, app name, etc.)
    """
    settings = frappe.get_single('Website Settings')
    return {
        'app_logo': settings.app_logo,
        'app_name': settings.app_name
    }

@frappe.whitelist(allow_guest=True)
def get_github_profile_data(github_url):
    """
    Fetch GitHub profile data for a developer
    Uses caching to avoid rate limits (60 requests/hour for unauthenticated requests)
    """
    import requests
    import json
    from datetime import datetime, timedelta

    if not github_url:
        return None

    # Extract GitHub username from URL
    # Handle both "https://github.com/username" and just "username"
    if github_url.startswith("http"):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(github_url)
            github_username = parsed.path.strip("/")
        except:
            github_username = github_url
    else:
        github_username = github_url

    if not github_username:
        return None

    # Check if we have cached data (cache for 2 hours)
    cache_key = f"github_profile_{github_username}"
    cached_data = frappe.cache().get_value(cache_key)

    if cached_data:
        try:
            cached_data = json.loads(cached_data)
            # Check if cache is still valid (2 hours)
            cache_time = datetime.fromisoformat(cached_data.get("cached_at"))
            if datetime.now() - cache_time < timedelta(hours=2):
                return cached_data["data"]
        except:
            pass

    # Fetch fresh data from GitHub API
    try:
        # Fetch user profile
        user_url = f"https://api.github.com/users/{github_username}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Frappe-Bench-Manager"
        }

        response = requests.get(user_url, headers=headers, timeout=10)

        if response.status_code == 200:
            user_data = response.json()

            # Fetch public repositories (limit to 6 most recent)
            repos_url = f"https://api.github.com/users/{github_username}/repos?sort=updated&per_page=6"
            repos_response = requests.get(repos_url, headers=headers, timeout=10)

            repos_data = []
            if repos_response.status_code == 200:
                repos_data = repos_response.json()

            # Fetch recent public events (limit to 5)
            events_url = f"https://api.github.com/users/{github_username}/events/public?per_page=5"
            events_response = requests.get(events_url, headers=headers, timeout=10)

            events_data = []
            if events_response.status_code == 200:
                events_data = events_response.json()

            # Prepare the response data
            github_data = {
                "login": user_data.get("login"),
                "name": user_data.get("name"),
                "bio": user_data.get("bio"),
                "avatar_url": user_data.get("avatar_url"),
                "public_repos": user_data.get("public_repos"),
                "followers": user_data.get("followers"),
                "following": user_data.get("following"),
                "location": user_data.get("location"),
                "company": user_data.get("company"),
                "blog": user_data.get("blog"),
                "twitter_username": user_data.get("twitter_username"),
                "created_at": user_data.get("created_at"),
                "updated_at": user_data.get("updated_at"),
                "html_url": user_data.get("html_url"),
                "repos": [
                    {
                        "name": repo.get("name"),
                        "description": repo.get("description"),
                        "stars": repo.get("stargazers_count"),
                        "forks": repo.get("forks_count"),
                        "language": repo.get("language"),
                        "updated_at": repo.get("updated_at"),
                        "html_url": repo.get("html_url")
                    }
                    for repo in repos_data
                ],
                "recent_activity": [
                    {
                        "type": event.get("type"),
                        "repo_name": event.get("repo", {}).get("name"),
                        "created_at": event.get("created_at"),
                        "payload": event.get("payload", {})
                    }
                    for event in events_data
                ]
            }

            # Cache the data
            cache_payload = {
                "data": github_data,
                "cached_at": datetime.now().isoformat()
            }
            frappe.cache().set_value(cache_key, json.dumps(cache_payload), expires_in_sec=7200)  # 2 hours

            return github_data

        else:
            frappe.log_error(f"GitHub API error: {response.status_code} - {response.text}", "GitHub API Error")
            return None

    except Exception as e:
        frappe.log_error(f"Failed to fetch GitHub data: {str(e)}", "GitHub API Error")
        return None

@frappe.whitelist()
def update_all_category_counts():
    """
    Update app_count for all categories
    This should be called after importing apps or changing categories
    """
    categories = frappe.get_list("App Category", fields=["name"])
    updated = []

    for category in categories:
        try:
            cat_doc = frappe.get_doc("App Category", category.name)
            cat_doc.update_app_count()
            updated.append({
                "category": category.name,
                "app_count": cat_doc.app_count
            })
        except Exception as e:
            frappe.log_error(f"Failed to update category {category.name}: {str(e)}")

    return updated

@frappe.whitelist(allow_guest=True)
def signup(full_name, email, password, role):
    """
    Sign up a new user with role assignment
    role: 'buyer', 'developer', or 'both'
    """
    # Check if user already exists
    if frappe.db.exists("User", email):
        frappe.throw(_("Email already registered"))

    # Validate role
    valid_roles = ['buyer', 'developer', 'both']
    if role not in valid_roles:
        frappe.throw(_("Invalid role"))

    # Create user
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": full_name.split()[0] if full_name else "",
        "last_name": " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
        "full_name": full_name,
        "send_welcome_email": False,
        "new_password": password
    })

    user.insert(ignore_permissions=True)

    # Assign roles based on selection
    roles_to_add = []
    if role in ['buyer', 'both']:
        # Add Member role (create if doesn't exist)
        if not frappe.db.exists("Role", "Member"):
            member_role = frappe.get_doc({
                "doctype": "Role",
                "role_name": "Member",
                "desk_access": 1,
                "is_custom": 1
            })
            member_role.insert(ignore_permissions=True)
        roles_to_add.append("Member")

    if role in ['developer', 'both']:
        # Ensure App Developer role exists
        if not frappe.db.exists("Role", "App Developer"):
            app_dev_role = frappe.get_doc({
                "doctype": "Role",
                "role_name": "App Developer",
                "desk_access": 1,
                "is_custom": 1
            })
            app_dev_role.insert(ignore_permissions=True)
        roles_to_add.append("App Developer")

    # Assign roles to user (Frappe automatically adds System User)
    if roles_to_add:
        user.add_roles(*roles_to_add)

    # If buyer role, create Member document
    if role in ['buyer', 'both']:
        try:
            from datetime import date
            member = frappe.get_doc({
                "doctype": "Member",
                "member_name": full_name,
                "email": email,
                "user": email,
                "member_since": date.today(),
                "member_status": "Active"
            })
            member.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to create Member for {email}: {str(e)}")

    # If developer role, create App Developer document
    if role in ['developer', 'both']:
        try:
            app_developer = frappe.get_doc({
                "doctype": "App Developer",
                "user": email,
                "developer_name": full_name,
                "email": email,
                "is_active": 1
            })
            app_developer.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to create App Developer for {email}: {str(e)}")

    frappe.db.commit()

    return {
        "success": True,
        "message": "Account created successfully. Please sign in.",
        "user_email": email
    }


@frappe.whitelist(allow_guest=True)
def get_user_info():
    """
    Get current user info with roles - similar to LMS pattern
    """
    if frappe.session.user == "Guest":
        return None

    try:
        user = frappe.db.get_value(
            "User",
            frappe.session.user,
            ["name", "email", "enabled", "user_image", "full_name", "user_type"],
            as_dict=1,
        )
        if not user:
            return None

        # Get roles using frappe.get_roles (standard Frappe function)
        roles = frappe.get_roles(user.name)
        user.roles = roles if roles else []

        # Add computed role flags for easy frontend use
        user.is_member = "Member" in user.roles
        user.is_app_developer = "App Developer" in user.roles
        user.is_system_manager = "System Manager" in user.roles

        return user
    except Exception as e:
        frappe.log_error(f"Error in get_user_info: {str(e)}")
        return None


@frappe.whitelist()
def get_member_dashboard():
    """
    Get member dashboard data including user roles and member details
    """
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw(_("Please login to access dashboard"))

    try:
        # Get user roles using frappe.get_roles (returns list of role names)
        roles = frappe.get_roles(frappe.session.user)

        # Check if user has Member role
        member_data = None
        if "Member" in roles:
            try:
                member = frappe.get_value(
                    "Member",
                    {"user": frappe.session.user},
                    ["name", "member_name", "email", "phone", "company", "designation", "profile_image", "member_since", "member_status", "total_purchases"]
                )
                if member:
                    member_data = {
                        "name": member[0],
                        "member_name": member[1],
                        "email": member[2],
                        "phone": member[3],
                        "company": member[4],
                        "designation": member[5],
                        "profile_image": member[6],
                        "member_since": member[7],
                        "member_status": member[8],
                        "total_purchases": member[9]
                    }
            except Exception as e:
                frappe.log_error(f"Failed to fetch Member data for {frappe.session.user}: {str(e)}")

        return {
            "user": frappe.session.user,
            "roles": roles,
            "is_member": "Member" in roles,
            "is_developer": "App Developer" in roles,
            "member_data": member_data
        }
    except Exception as e:
        frappe.log_error(f"Error in get_member_dashboard: {str(e)}")
        frappe.throw(_("Failed to load dashboard data. Please try again."))


@frappe.whitelist(allow_guest=True)
def get_reddit_posts(subreddit="frappe_framework", limit=25, after=None):
    """
    Fetch Reddit posts from a subreddit using RSS feed
    No API key required - uses public RSS feed
    Results are cached for 15 minutes to avoid rate limits
    
    Parameters:
        subreddit: Subreddit name (default: frappe_framework)
        limit: Number of posts to fetch (default: 25, max: 100)
        after: Reddit post ID for pagination (for infinite scroll)
    """
    try:
        # Build RSS URL with pagination
        rss_url = f"https://www.reddit.com/r/{subreddit}.rss?limit={limit}"
        if after:
            rss_url += f"&after={after}"

        # Cache key based on parameters
        cache_key = f"reddit_posts_{subreddit}_{limit}_{after or 'first'}"
        cached_data = frappe.cache().get_value(cache_key)
        if cached_data:
            return cached_data

        # Fetch RSS feed
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Define XML namespace
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'media': 'http://search.yahoo.com/mrss/'
        }

        # Extract posts
        posts = []
        entries = root.findall('atom:entry', ns)

        # Extract last post ID for pagination
        last_post_id = None
        if entries:
            last_entry = entries[-1]
            last_link = last_entry.find('atom:link', ns).get('href')
            # Extract post ID from URL (format: https://www.reddit.com/r/frappe_framework/comments/1smxefh/...)
            if last_link and '/comments/' in last_link:
                last_post_id = last_link.split('/comments/')[-1].split('/')[0]

        for entry in entries:
            # Extract data
            title = entry.find('atom:title', ns).text
            link = entry.find('atom:link', ns).get('href')
            published = entry.find('atom:published', ns).text
            updated = entry.find('atom:updated', ns).text
            content = entry.find('atom:content', ns).text

            # Extract author
            author_elem = entry.find('atom:author/atom:name', ns)
            author = author_elem.text if author_elem is not None else "Unknown"

            # Extract thumbnail if exists
            thumbnail = None
            thumbnail_elem = entry.find('media:thumbnail', ns)
            if thumbnail_elem is not None:
                thumbnail = thumbnail_elem.get('url')

            # Clean HTML content (remove SC_OFF/SC_ON markers and decode HTML entities)
            content_clean = content
            if '<!-- SC_OFF -->' in content:
                content_clean = content.split('<!-- SC_OFF -->')[1]
            if '<!-- SC_ON -->' in content_clean:
                content_clean = content_clean.split('<!-- SC_ON -->')[0]
            content_clean = html.unescape(content_clean)

            # Strip HTML tags for excerpt
            excerpt = re.sub('<[^<]+?>', '', content_clean)
            excerpt = excerpt.strip()
            if len(excerpt) > 200:
                excerpt = excerpt[:200] + "..."

            posts.append({
                "title": title,
                "link": link,
                "author": author,
                "published": published,
                "updated": updated,
                "content": content_clean,
                "excerpt": excerpt,
                "thumbnail": thumbnail
            })

        # Cache for 15 minutes (900 seconds)
        result = {
            "posts": posts,
            "after": last_post_id,
            "has_more": last_post_id is not None
        }
        frappe.cache().set_value(cache_key, result, expires_in_sec=900)

        return result

    except requests.RequestException as e:
        frappe.log_error(f"Failed to fetch Reddit RSS feed: {str(e)}")
        return {"posts": [], "after": None, "has_more": False}
    except Exception as e:
        frappe.log_error(f"Error in get_reddit_posts: {str(e)}")
        return {"posts": [], "after": None, "has_more": False}


@frappe.whitelist()
def get_wishlist():
    """
    Get all wishlist items for the current user
    """
    if frappe.session.user == "Guest":
        return []
    
    # Get member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        return []
    
    # Get wishlist items
    wishlist_items = frappe.get_list(
        "Member Wishlist",
        filters={"parent": member},
        fields=["app", "added_on"],
        order_by="added_on desc"
    )
    
    # Get app details for each wishlist item
    apps = []
    for item in wishlist_items:
        app = frappe.get_doc("App", item.app).as_dict()
        app.added_on = item.added_on
        apps.append(app)
    
    return apps


@frappe.whitelist()
def add_to_wishlist(app_id):
    """
    Add an app to the current user's wishlist
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to add items to wishlist"))
    
    # Get or create member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        frappe.throw(_("Member profile not found"))
    
    # Check if app is already in wishlist
    existing = frappe.db.exists("Member Wishlist", {"parent": member, "app": app_id})
    if existing:
        return {"success": False, "message": "App already in wishlist"}
    
    # Add to wishlist
    member_doc = frappe.get_doc("Member", member)
    member_doc.append("wishlist", {"app": app_id, "added_on": frappe.utils.today()})
    member_doc.save()
    
    return {"success": True, "message": "Added to wishlist"}


@frappe.whitelist()
def remove_from_wishlist(app_id):
    """
    Remove an app from the current user's wishlist
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to manage wishlist"))
    
    # Get member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        frappe.throw(_("Member profile not found"))
    
    # Find and remove the wishlist item
    wishlist_item = frappe.db.get_value("Member Wishlist", {"parent": member, "app": app_id}, "name")
    if not wishlist_item:
        return {"success": False, "message": "Item not found in wishlist"}
    
    frappe.delete_doc("Member Wishlist", wishlist_item)
    
    return {"success": True, "message": "Removed from wishlist"}


@frappe.whitelist()
def get_purchase_history():
    """
    Get all purchase history for the current user
    """
    if frappe.session.user == "Guest":
        return []
    
    # Get member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        return []
    
    # Get the member document to access child table
    member_doc = frappe.get_doc("Member", member)
    
    # Get all app purchases from child table
    purchases = []
    if member_doc.purchased_apps:
        for item in member_doc.purchased_apps:
            if item.app:
                app = frappe.get_doc("App", item.app).as_dict()
                # Merge purchase details into app
                app.purchase_date = item.purchase_date
                app.pricing_model = item.pricing_model
                app.subscription_type = item.subscription_type
                app.license_key = item.license_key
                app.license_type = item.license_type
                app.expiry_date = item.expiry_date
                app.subscription_start_date = item.subscription_start_date
                app.subscription_end_date = item.subscription_end_date
                app.is_active = item.is_active
                app.status = item.status
                app.payment_transaction = item.payment_transaction
                purchases.append(app)
    
    # Sort by purchase date desc
    purchases.sort(key=lambda x: x.purchase_date, reverse=True)
    
    return purchases


@frappe.whitelist()
def get_my_apps():
    """
    Get all apps owned by the current user (active purchases)
    """
    if frappe.session.user == "Guest":
        return []
    
    # Get member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        return []
    
    # Get the member document to access child table
    member_doc = frappe.get_doc("Member", member)
    
    # Get active app purchases from child table
    purchases = []
    if member_doc.purchased_apps:
        for item in member_doc.purchased_apps:
            if item.is_active and item.app:
                app = frappe.get_doc("App", item.app).as_dict()
                # Merge purchase details into app
                app.purchase_date = item.purchase_date
                app.pricing_model = item.pricing_model
                app.subscription_type = item.subscription_type
                app.license_key = item.license_key
                app.license_type = item.license_type
                app.expiry_date = item.expiry_date
                app.subscription_start_date = item.subscription_start_date
                app.subscription_end_date = item.subscription_end_date
                app.is_active = item.is_active
                app.status = item.status
                app.payment_transaction = item.payment_transaction
                purchases.append(app)
    
    # Sort by purchase date desc
    purchases.sort(key=lambda x: x.purchase_date, reverse=True)
    
    return purchases


@frappe.whitelist()
def get_account_settings():
    """
    Get account settings for the current user
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to view account settings"))
    
    # Get member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        frappe.throw(_("Member profile not found"))
    
    member_doc = frappe.get_doc("Member", member)
    return member_doc.as_dict()


@frappe.whitelist()
def update_account_settings(data):
    """
    Update account settings for the current user
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to update account settings"))
    
    # Get member document
    member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
    if not member:
        frappe.throw(_("Member profile not found"))
    
    member_doc = frappe.get_doc("Member", member)
    
    # Update allowed fields
    allowed_fields = ["member_name", "phone", "company", "designation", "profile_image", "billing_address", "gstin", "notes"]
    for field in allowed_fields:
        if field in data:
            member_doc.set(field, data[field])
    
    member_doc.save()
    
    return {"success": True, "message": "Account settings updated successfully"}


# Review System APIs
@frappe.whitelist()
def get_app_reviews(app_id):
	"""
	Get all reviews for an app
	"""
	try:
		# Check if app exists
		if not frappe.db.exists("App", app_id):
			return {
				"success": False,
				"error": "App not found"
			}
		
		# Get all reviews with member details
		reviews = frappe.get_all("App Review",
			filters={"app": app_id},
			fields=["name", "rating", "review_text", "review_date", 
				"is_verified_purchase", "helpful_count", "member"],
			order_by="review_date DESC"
		)
		
		# Enrich with member details
		for review in reviews:
			member = frappe.get_value("Member", review.member, ["full_name", "email"])
			review["member_name"] = member.get("full_name") if member else "Unknown"
			review["member_email"] = member.get("email") if member else ""
			# Check if current user owns this review
			review["is_owner"] = review.member == frappe.db.get_value("Member", 
				{"email": frappe.session.user}, "name")
		
		return {
			"success": True,
			"reviews": reviews
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get App Reviews Error")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def get_user_review(app_id):
	"""
	Get current user's review for an app
	"""
	try:
		# Get current member
		member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
		
		if not member:
			return {
				"success": False,
				"error": "Member not found"
			}
		
		# Get user's review
		review = frappe.db.get_value("App Review",
			filters={
				"app": app_id,
				"member": member
			},
			fieldname=["name", "rating", "review_text", "review_date", "is_verified_purchase"]
		)
		
		return {
			"success": True,
			"review": review
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get User Review Error")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def add_review(app_id, rating, review_text=""):
	"""
	Add a new review for an app
	"""
	try:
		# Get current member
		member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
		
		if not member:
			return {
				"success": False,
				"error": "Please login to review"
			}
		
		# Check if app exists - use app_id as the app name
		app_name = frappe.db.get_value("App", {"name": app_id}, "name")
		if not app_name:
			return {
				"success": False,
				"error": "App not found"
			}
		
		# Validate rating
		try:
			rating = int(rating)
		except:
			return {
				"success": False,
				"error": "Invalid rating"
			}
		
		if rating < 1 or rating > 5:
			return {
				"success": False,
				"error": "Rating must be between 1 and 5"
			}
		
		# Check if member already has a review for this app
		existing_review = frappe.db.exists("App Review", {
			"app": app_name,
			"member": member
		})
		
		if existing_review:
			return {
				"success": False,
				"error": "You have already reviewed this app"
			}
		
		# Check if member has reached the 2 reviews limit (across all apps)
		total_reviews = frappe.db.count("App Review", filters={"member": member})
		if total_reviews >= 2:
			return {
				"success": False,
				"error": "You can only submit 2 reviews total. Please delete an existing review to submit a new one."
			}
		
		# Create review
		review = frappe.get_doc({
			"doctype": "App Review",
			"app": app_name,
			"member": member,
			"rating": rating,
			"review_text": review_text,
			"review_date": frappe.utils.today()
		})
		review.insert(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"success": True,
			"review": review.name
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Add Review Error")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def update_review(review_id=None, rating=None, review_text=""):
	"""
	Update an existing review
	"""
	try:
		if not review_id:
			return {
				"success": False,
				"error": "Review ID is required"
			}
		
		# Get current member
		member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
		
		if not member:
			return {
				"success": False,
				"error": "Please login to update review"
			}
		
		# Get review
		review = frappe.get_doc("App Review", review_id)
		
		# Check ownership
		if review.member != member:
			return {
				"success": False,
				"error": "You can only update your own review"
			}
		
		# Validate rating if provided
		if rating:
			try:
				rating = int(rating)
				if rating < 1 or rating > 5:
					return {
						"success": False,
						"error": "Rating must be between 1 and 5"
					}
			except:
				return {
					"success": False,
					"error": "Invalid rating"
				}
		
		# Update review (only update provided fields)
		if rating:
			review.rating = rating
		if review_text is not None:
			review.review_text = review_text
		
		review.save(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"success": True,
			"review": review.name
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Update Review Error")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def delete_review(review_id=None):
	"""
	Delete a review
	"""
	try:
		if not review_id:
			return {
				"success": False,
				"error": "Review ID is required"
			}
		
		# Get current member
		member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
		
		if not member:
			return {
				"success": False,
				"error": "Please login to delete review"
			}
		
		# Get review
		review = frappe.get_doc("App Review", review_id)
		
		# Check ownership
		if review.member != member:
			return {
				"success": False,
				"error": "You can only delete your own review"
			}
		
		# Delete review
		review.delete(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"success": True,
			"message": "Review deleted successfully"
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Review Error")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def mark_review_helpful(review_id):
	"""
	Mark a review as helpful (increment helpful count)
	"""
	try:
		# Get review
		review = frappe.get_doc("App Review", review_id)
		
		# Increment helpful count
		review.helpful_count = (review.helpful_count or 0) + 1
		review.save(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"success": True,
			"helpful_count": review.helpful_count
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Mark Review Helpful Error")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def test_get_reviews(app_id):
	"""
	Test API to debug review fetching
	"""
	app_doc = frappe.get_doc("App", app_id).as_dict()
	app_name = app_doc.get('name')
	
	# Try to get reviews
	reviews = frappe.get_all("App Review",
		filters={"app": app_name},
		fields=["name", "rating", "review_text", "member"]
	)
	
	return {
		"app_id": app_id,
		"app_name": app_name,
		"reviews_count": len(reviews),
		"reviews": reviews
	}


@frappe.whitelist(allow_guest=True)
def generate_sitemap():
	"""
	Generate XML sitemap for the app store
	Includes all public pages, apps, categories, and developers
	"""
	from datetime import datetime
	from urllib.parse import urljoin
	
	base_url = "https://worf.cloud"
	
	# Create root element
	urlset = ET.Element("urlset")
	urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")
	
	# Static pages with high priority
	static_pages = [
		{"loc": "/", "priority": "1.0", "changefreq": "daily"},
		{"loc": "/store", "priority": "0.9", "changefreq": "daily"},
		{"loc": "/apps", "priority": "0.9", "changefreq": "daily"},
		{"loc": "/about", "priority": "0.8", "changefreq": "monthly"},
		{"loc": "/contact", "priority": "0.8", "changefreq": "monthly"},
		{"loc": "/community", "priority": "0.7", "changefreq": "weekly"},
	]
	
	for page in static_pages:
		url = ET.SubElement(urlset, "url")
		loc = ET.SubElement(url, "loc")
		loc.text = urljoin(base_url, page["loc"])
		priority = ET.SubElement(url, "priority")
		priority.text = page["priority"]
		changefreq = ET.SubElement(url, "changefreq")
		changefreq.text = page["changefreq"]
		lastmod = ET.SubElement(url, "lastmod")
		lastmod.text = datetime.now().strftime("%Y-%m-%d")
	
	# Get all published apps
	try:
		apps = frappe.get_list(
			"App",
			filters={"is_published": 1, "moderation_status": "Approved"},
			fields=["name", "modified"],
			order_by="modified desc",
			limit=1000
		)
		
		for app in apps:
			url = ET.SubElement(urlset, "url")
			loc = ET.SubElement(url, "loc")
			loc.text = urljoin(base_url, f"/app-store/{app.name}")
			priority = ET.SubElement(url, "priority")
			priority.text = "0.7"
			changefreq = ET.SubElement(url, "changefreq")
			changefreq.text = "weekly"
			lastmod = ET.SubElement(url, "lastmod")
			lastmod.text = app.modified.strftime("%Y-%m-%d") if app.modified else datetime.now().strftime("%Y-%m-%d")
	except Exception as e:
		frappe.log_error(f"Error fetching apps for sitemap: {str(e)}")
	
	# Get all categories
	try:
		categories = frappe.get_list(
			"App Category",
			filters={"is_active": 1},
			fields=["slug", "modified"],
			order_by="modified desc"
		)
		
		for category in categories:
			url = ET.SubElement(urlset, "url")
			loc = ET.SubElement(url, "loc")
			loc.text = urljoin(base_url, f"/category/{category.slug}")
			priority = ET.SubElement(url, "priority")
			priority.text = "0.6"
			changefreq = ET.SubElement(url, "changefreq")
			changefreq.text = "weekly"
			lastmod = ET.SubElement(url, "lastmod")
			lastmod.text = category.modified.strftime("%Y-%m-%d") if category.modified else datetime.now().strftime("%Y-%m-%d")
	except Exception as e:
		frappe.log_error(f"Error fetching categories for sitemap: {str(e)}")
	
	# Get all active developers
	try:
		developers = frappe.get_list(
			"App Developer",
			filters={"is_active": 1},
			fields=["name", "modified"],
			order_by="modified desc",
			limit=500
		)
		
		for developer in developers:
			url = ET.SubElement(urlset, "url")
			loc = ET.SubElement(url, "loc")
			loc.text = urljoin(base_url, f"/developer/{developer.name}")
			priority = ET.SubElement(url, "priority")
			priority.text = "0.5"
			changefreq = ET.SubElement(url, "changefreq")
			changefreq.text = "monthly"
			lastmod = ET.SubElement(url, "lastmod")
			lastmod.text = developer.modified.strftime("%Y-%m-%d") if developer.modified else datetime.now().strftime("%Y-%m-%d")
	except Exception as e:
		frappe.log_error(f"Error fetching developers for sitemap: {str(e)}")
	
	# Generate XML string with declaration
	xml_str = ET.tostring(urlset, encoding="unicode", xml_declaration=True)
	
	return xml_str



