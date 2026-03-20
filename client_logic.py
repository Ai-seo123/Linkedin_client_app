import json
import time
import threading
import csv
from datetime import datetime, date
from flask import Flask, request, jsonify
import json
import time
import threading
import csv
from datetime import datetime, date
from flask import Flask, request, jsonify
import requests
from linkedin_automation import LinkedInAutomation
import logging
import os
import uuid
from collections import defaultdict
from tkinter import ttk, messagebox, scrolledtext
import signal
import atexit
import random
import re
import hashlib
from typing import List, Dict, Any
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional
# Import all functions from LinkedIn_automation_script.py
from urllib.parse import urlencode, quote
import tempfile
import platform
import shutil
from typing import List, Dict, Any
import sys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Import from your new modules
from ai_inbox import EnhancedAIInbox
from gui import create_config_gui, show_status_gui
from linkedin_automation import LinkedInAutomation 
# Note: You might need to adjust other internal method calls inside the class.
# The following is a simplified structure.

logger = logging.getLogger(__name__)

LINKEDIN_NETWORK_CODE_BY_DEGREE = {
    "1st": "F",
    "2nd": "S",
    "3rd+": "O",
    "3rd": "O",
}

LINKEDIN_GEO_URN_BY_LOCATION = {
    "australia": "101452733",
    "belgium": "100565514",
    "california": "102095887",
    "california united states": "102095887",
    "california usa": "102095887",
    "brazil": "106057199",
    "canada": "101174742",
    "china": "102890883",
    "england": "102299470",
    "france": "105015875",
    "germany": "101282230",
    "india": "102713980",
    "italy": "103350119",
    "japan": "101355337",
    "mexico": "103323778",
    "netherlands": "102890719",
    "new york": "103644278",
    "new york city": "103644278",
    "nyc": "103644278",
    "maharashtra": "106300413",
    "maharashtra india": "106300413",
    "maharashtra ind": "106300413",
    "karnataka": "100811329",
    "karnataka india": "100811329",
    "greater bengaluru area": "90009633",
    "greater bangalore area": "90009633",
    "bengaluru": "105214831",
    "bangalore": "105214831",
    "bengaluru karnataka india": "105214831",
    "bangalore karnataka india": "105214831",
    "miami": "102394087",
    "miami florida": "102394087",
    "miami fl": "102394087",
    "miami florida united states": "102394087",
    "miami fl usa": "102394087",
    "russia": "101728296",
    "san francisco": "102277331",
    "san francisco california": "102277331",
    "san francisco ca": "102277331",
    "san francisco california united states": "102277331",
    "san francisco ca usa": "102277331",
    "singapore": "102454443",
    "south korea": "105149562",
    "spain": "105646813",
    "sweden": "105117694",
    "switzerland": "106693272",
    "uae": "104305776",
    "united arab emirates": "104305776",
    "united arab emirates uae": "104305776",
    "united states": "103644278",
    "united states of america": "103644278",
    "usa": "103644278",
}

LINKEDIN_PROFILE_LANGUAGE_CODE_BY_NAME = {
    "english": "en",
    "en": "en",
    "spanish": "es",
    "es": "es",
    "portuguese": "pt",
    "portugese": "pt",
    "portugues": "pt",
    "pt": "pt",
    "french": "fr",
    "fr": "fr",
    "chinese": "zh",
    "mandarin": "zh",
    "zh": "zh",
}

class EnhancedLinkedInAutomationClient:
    def __init__(self):
        self.config_file = "client_config.json"
        self.config = self.load_or_create_config()
        self.runtime_api_key = None
        self.current_user_config = {}
        self.current_linkedin_profile_key = ""
        self.active_browser_profile_key = None
        self.driver = None
        self.wait = None
        self.temp_profile_dir = None
        self.browser_lock = threading.Lock()
        
        # Exit if config creation was cancelled
        if self.config is None:
            logger.error("❌ Configuration setup was cancelled or failed.")
            sys.exit(1)

        # KEY CHANGE: Ensure a unique client_id exists and save it if new
        config_updated = False
        if 'client_id' not in self.config or not self.config['client_id']:
            self.config['client_id'] = str(uuid.uuid4())
            config_updated = True
            logger.info(f"✨ Generated new unique client ID: {self.config['client_id']}")

        if config_updated:
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2)
                logger.info("✅ Saved new client ID to configuration file.")
            except Exception as e:
                logger.error(f"⚠️ Could not save new client ID to config: {e}")

        self.bootstrap_client_api_key()
        self.email = (self.current_user_config.get('linkedin_email') or self.config.get('linkedin_email') or '').strip()
        self.password = (self.current_user_config.get('linkedin_password') or self.config.get('linkedin_password') or '').strip()
        
        # Initialize EnhancedAIInbox
        self.enhanced_inbox = EnhancedAIInbox(client_instance=self)
        
        self.automation_instances = {}
        self.active_campaigns = defaultdict(lambda: {
            'user_action': None, 
            'awaiting_confirmation': False,
            'current_contact': None,
            'status': 'idle'
        })
        self.running = False
        self.active_searches = defaultdict(lambda: {
            "status": "idle", # idle | running | completed | failed
            "keywords": "",
            "max_invites": 0,
            "invites_sent": 0,
            "progress": 0,
            "stop_requested": False,
            "start_time": None,
            "end_time": None,
            "driver_errors": 0
        })
        self.active_sales_nav_fetches = defaultdict(lambda: {
            "status": "idle",
            "stop_requested": False
        })

        poll_interval=int(self.config.get('poll_interval_seconds',15))
        try:
            self.start_polling(poll_interval_seconds=poll_interval)
        except Exception as e:
            logger.error(f"❌ Error starting polling: {e}")

    def load_or_create_config(self):
        """Load existing config or create new one via GUI"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info("✅ Configuration loaded successfully")
                return config
            except Exception as e:
                logger.error(f"❌ Error loading config: {e}")
        
        logger.info("📋 No configuration found, launching setup GUI...")
        return create_config_gui(self)

    def bootstrap_client_api_key(self):
        """Authenticate with dashboard credentials and fetch the runtime client API key."""
        dashboard_url = (self.config.get('dashboard_url') or '').strip()
        dashboard_email = (self.config.get('dashboard_email') or '').strip().lower()
        dashboard_password = (self.config.get('dashboard_password') or '').strip()
        client_id = (self.config.get('client_id') or '').strip()

        if not dashboard_url or not dashboard_email or not dashboard_password:
            logger.warning("Dashboard credentials are incomplete; bootstrap authentication was skipped.")
            self.runtime_api_key = None
            return

        endpoint = f"{dashboard_url.rstrip('/')}/api/client/bootstrap-auth"
        payload = {
            "email": dashboard_email,
            "password": dashboard_password,
            "client_id": client_id
        }

        try:
            resp = requests.post(endpoint, json=payload, timeout=20)
        except requests.exceptions.RequestException as exc:
            logger.error(f"❌ Dashboard bootstrap request failed: {exc}")
            self.runtime_api_key = None
            return

        if resp.status_code != 200:
            details = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            logger.error(f"❌ Dashboard bootstrap authentication failed: {details}")
            self.runtime_api_key = None
            return

        data = resp.json() if resp.content else {}
        self.runtime_api_key = (data.get('client_api_key') or '').strip() or None
        self.current_user_config = data.get('user_config') or {}
        self.current_linkedin_profile_key = (
            data.get('linkedin_profile_key')
            or self.current_user_config.get('linkedin_profile_key')
            or ''
        ).strip()
        logger.info("✅ Dashboard bootstrap authentication successful.")

    def _get_auth_headers(self):
        """Return authorization headers for dashboard requests"""
        api_key = self.runtime_api_key or ""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    # ... (rest of the methods remain the same) ...
    def start_polling(self, poll_interval_seconds: int = 15):
        """Start polling the dashboard for tasks with heartbeat."""
        if getattr(self, "_polling_thread", None) and self._polling_thread.is_alive():
            logger.info("🔁 Polling already running.")
            return

        self._stop_polling = False
        self._poll_interval = max(5, int(poll_interval_seconds))
        
        # Start heartbeat
        self.start_heartbeat(interval_seconds=60)
        
        self._polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._polling_thread.start()
        logger.info(f"🔁 Started polling loop (interval {self._poll_interval}s).")


    def stop_polling(self):
        """Stop the polling loop and heartbeat."""
        self._stop_polling = True
        self.stop_heartbeat()
        
        if getattr(self, "_polling_thread", None):
            self._polling_thread.join(timeout=5)
        logger.info("🔁 Polling stopped.")

    def _polling_loop(self):
        """Enhanced polling loop with exponential backoff and jitter."""
        backoff_attempts = 0
        consecutive_failures = 0
        
        while not getattr(self, "_stop_polling", False):
            try:
                tasks = self.poll_once()
                
                # Reset failure counters on success
                backoff_attempts = 0
                consecutive_failures = 0
                
                if tasks:
                    logger.info(f"📥 Received {len(tasks)} tasks")
                    for task in tasks:
                        try:
                            self.handle_task(task)
                        except Exception as e:
                            logger.error(f"❌ Error handling task {task.get('id', 'unknown')}: {e}")
                            self.report_task_failure(task, str(e))

                time.sleep(self._poll_interval)
                
            except Exception as e:
                consecutive_failures += 1
                backoff_attempts += 1
                
                # Exponential backoff with jitter
                wait = min(300, (2 ** backoff_attempts) + random.random() * 3)
                
                if consecutive_failures <= 3:
                    logger.warning(f"⚠️ Polling error (attempt {consecutive_failures}): {e}")
                else:
                    logger.error(f"❌ Persistent polling error (attempt {consecutive_failures}): {e}")
                    
                logger.info(f"⏳ Backing off for {wait:.1f}s")
                time.sleep(wait)
                
                # Reset backoff if too many failures
                if consecutive_failures >= 10:
                    logger.warning("🔄 Too many consecutive failures, resetting backoff")
                    backoff_attempts = 0
            
    def report_task_failure(self, task, error_message):
        """Report task failure back to dashboard"""
        try:
            task_id = task.get('id', str(uuid.uuid4()))
            result = {
                "task_id": task_id,
                "type": task.get('type', 'unknown'),
                "success": False,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            }
            self.report_task_result(result)
        except Exception as e:
            logger.error(f"Failed to report task failure: {e}")

    def poll_once(self):
        """Request tasks from the dashboard. Returns list of tasks or empty list."""
        SERVER_BASE = self.config.get('dashboard_url') or "https://your-render-app.onrender.com"
        endpoint = f"{SERVER_BASE.rstrip('/')}/api/get-tasks"
        if not self.runtime_api_key:
            self.bootstrap_client_api_key()

        if not self.runtime_api_key:
            logger.warning("No runtime client API key available after dashboard bootstrap; skipping poll.")
            return []

        payload = {
            'client_id': self.config.get('client_id') or self.config.get('instance_id') or str(uuid.uuid4()),
            'client_info': {
                'platform': platform.system(),
                'app_version': self.config.get('version', 'unknown')
            }
        }
        try:
            resp = requests.post(endpoint, json=payload, headers=self._get_auth_headers(), timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                tasks = data.get('tasks') or []
                logger.info(f"📥 Polled {len(tasks)} tasks from server.")
                return tasks
            elif resp.status_code == 204:
                return []
            elif resp.status_code in (401, 403):
                logger.warning(f"Poll rejected with {resp.status_code}. Clearing runtime API key and retrying bootstrap on the next cycle.")
                self.runtime_api_key = None
                return []
            else:
                logger.warning(f"Poll returned {resp.status_code}: {resp.text[:200]}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Poll request failed: {e}")
            return []
        
    def start_heartbeat(self, interval_seconds=60):
        """Start heartbeat to keep connection alive with dashboard"""
        if getattr(self, "_heartbeat_thread", None) and self._heartbeat_thread.is_alive():
            return
        
        self._stop_heartbeat = False
        self._heartbeat_interval = max(30, int(interval_seconds))
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        logger.info(f"💓 Started heartbeat (interval {self._heartbeat_interval}s)")

    def stop_heartbeat(self):
        """Stop the heartbeat"""
        self._stop_heartbeat = True
        if getattr(self, "_heartbeat_thread", None):
            self._heartbeat_thread.join(timeout=5)
        logger.info("💓 Heartbeat stopped")

    def _heartbeat_loop(self):
        """Send periodic ping to dashboard to show we're alive"""
        while not getattr(self, "_stop_heartbeat", False):
            try:
                self.send_heartbeat_ping()
                time.sleep(self._heartbeat_interval)
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")
                time.sleep(self._heartbeat_interval)

    def send_heartbeat_ping(self):
        """Send ping to dashboard and process returned actions."""
        try:
            SERVER_BASE = self.config.get('dashboard_url')
            if not SERVER_BASE:
                return
                
            endpoint = f"{SERVER_BASE.rstrip('/')}/api/client-ping"
            if not self.runtime_api_key:
                self.bootstrap_client_api_key()
            if not self.runtime_api_key:
                logger.warning("No runtime client API key available after dashboard bootstrap; skipping heartbeat.")
                return
            
            # ... (all the payload creation logic is fine) ...
            active_inbox_sessions = []
            if hasattr(self, 'enhanced_inbox') and self.enhanced_inbox:
                for session_id, session_data in self.enhanced_inbox.active_inbox_sessions.items():
                    if session_data.get('awaiting_confirmation'):
                        active_inbox_sessions.append({
                            'session_id': session_id,
                            'conversation': session_data.get('current_conversation')
                        })
            
            payload = {
                'client_id': self.config.get('client_id', str(uuid.uuid4())),
                'status': 'active',
                'timestamp': datetime.now().isoformat(),
                'client_info': {
                    'platform': platform.system(),
                    'version': '1.0'
                },
                'active_inbox_sessions': active_inbox_sessions
            }
            
            resp = requests.post(endpoint, json=payload, headers=self._get_auth_headers(), timeout=15)
            if resp.status_code in (401, 403):
                logger.warning(f"Heartbeat rejected with {resp.status_code}. Clearing runtime API key and retrying bootstrap on the next cycle.")
                self.runtime_api_key = None
                return
            
            # --- THIS IS THE FIX ---
            # We no longer need to check for actions here.
            if resp.status_code in (200, 201):
                logger.debug("💓 Heartbeat ping successful")
            else:
                logger.warning(f"💓 Heartbeat ping returned {resp.status_code}: {resp.text[:200]}")
                
        except Exception as e:
            logger.debug(f"💓 Heartbeat ping failed: {e}")
        
    def report_task_started(self, task_id, task_type):
        """Report that a task has started"""
        try:
            SERVER_BASE = self.config.get('dashboard_url')
            if not SERVER_BASE:
                return
                
            endpoint = f"{SERVER_BASE.rstrip('/')}/api/task-status"
            if not self.runtime_api_key:
                self.bootstrap_client_api_key()
            if not self.runtime_api_key:
                logger.warning("No runtime client API key available after dashboard bootstrap; skipping task-start report.")
                return
            
            payload = {
                'task_id': task_id,
                'status': 'started',
                'task_type': task_type,
                'timestamp': datetime.now().isoformat()
            }
            
            requests.post(endpoint, json=payload, headers=self._get_auth_headers(), timeout=10)
            logger.debug(f"📤 Reported task {task_id[:8]}... started")
            
        except Exception as e:
            logger.debug(f"Failed to report task started: {e}")

    def is_browser_alive(self):
        """Check if the Selenium WebDriver session is still active."""
        if not self.driver:
            return False
        try:
            # A lightweight way to check if the browser is still responsive
            _ = self.driver.window_handles
            return True
        except Exception:
            # This will catch errors if the browser has been closed
            return False

    def _get_browser_profile_identity(self):
        """Resolve the account identity used to isolate persistent Chrome profiles."""
        profile_key = (self.current_linkedin_profile_key or "").strip()
        if profile_key:
            return f"profile_{profile_key}"

        email = (
            self.email
            or self.current_user_config.get('linkedin_email')
            or self.config.get('linkedin_email')
            or ""
        ).strip().lower()
        if email:
            return f"email_{email}"

        return "default"

    def _get_persistent_profile_dir(self):
        """Return a stable Chrome user-data directory for the current LinkedIn account."""
        app_data_dir = os.path.join(os.path.expanduser("~"), ".linkedin_automation")
        profiles_root = os.path.join(app_data_dir, "chrome_profiles")
        os.makedirs(profiles_root, exist_ok=True)

        profile_identity = self._get_browser_profile_identity()
        safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', profile_identity).strip('._-') or "default"
        safe_name = safe_name[:48]
        profile_hash = hashlib.sha1(profile_identity.encode("utf-8")).hexdigest()[:10]
        profile_dir = os.path.join(profiles_root, f"{safe_name}_{profile_hash}")
        os.makedirs(profile_dir, exist_ok=True)

        return profile_identity, profile_dir

    def get_shared_driver(self):
        """
        Gets the shared browser instance. Creates a new one if it doesn't exist,
        if the user closed the window, or if the session is invalid,
        or if the user account has changed.
        """
        browser_alive = self.is_browser_alive()
        target_profile_identity = self._get_browser_profile_identity()
        account_changed = (
            browser_alive
            and self.active_browser_profile_key is not None
            and target_profile_identity != self.active_browser_profile_key
        )

        if not browser_alive or account_changed:
            if account_changed:
                logger.info("🔄 Account change detected! Re-initializing browser session...")
            else:
                logger.info("Browser not found or was closed. Initializing a new shared session...")
            
            # Ensure any old driver is fully closed
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass

            self.driver = self.initialize_browser() 
            if self.driver:
                self.wait = WebDriverWait(self.driver, 15)
                # Attempt to log in only when creating a new browser
                if self.login(): # Use the client's login method
                    self.user_name = self.get_user_profile_name(self.driver)
                    self.active_browser_profile_key = target_profile_identity
                else:
                    logger.error("❌ Failed to log in with the new browser instance. Cannot proceed.")
                    self.driver.quit()
                    self.driver = None
                    return None
            else:
                logger.error("❌ Failed to initialize the browser.")
                return None
        else:
            logger.info("✅ Re-using existing active browser session.")
            
        return self.driver

    def handle_task(self, task: dict):
        """Execute a single task with enhanced error handling and progress reporting."""
        task_id = task.get('id') or str(uuid.uuid4())
        ttype = task.get('type','').strip()
        params = task.get('params', {})
        user_config = params.get('user_config', {})
        if 'linkedin_email' in user_config:
            self.email = (user_config.get('linkedin_email') or '').strip()
        if 'linkedin_password' in user_config:
            self.password = (user_config.get('linkedin_password') or '').strip()
        if 'linkedin_profile_key' in user_config:
            self.current_linkedin_profile_key = (user_config.get('linkedin_profile_key') or '').strip()
        elif 'linkedin_email' in user_config:
            self.current_linkedin_profile_key = ''
        
        logger.info(f"🧩 Starting task {task_id[:8]}... type={ttype}")
        
        result = {
            "task_id": task_id,
            "type": ttype,
            "success": False,
            "error": None,
            "payload": None,
            "start_time": datetime.now().isoformat()
        }
        
        try:
            self.report_task_started(task_id, ttype)
            
            driver = None
            if ttype in ("process_inbox", "send_message", "collect_profiles", "keyword_search", "outreach_campaign", "sync_network_stats"):
                driver = self.get_shared_driver()
                if not driver:
                    raise Exception("Failed to get valid browser session")

            # ENHANCED INBOX PROCESSING WITH PREVIEW
            if ttype == "process_inbox":
                process_id = params.get('process_id', task_id)

                # Start the inbox processing in a new thread to avoid blocking
                threading.Thread(
                    target=self.execute_inbox_task, 
                    args=(process_id,), 
                    daemon=True
                ).start()
                
                result['success'] = True
                result['payload'] = {'message': 'Inbox processing task has been started.', 'process_id': process_id}
                    
        # ENHANCED INBOX ACTION HANDLING - EXACTLY LIKE OUTREACH
            elif ttype == "process_inbox":
                process_id = params.get('process_id', task_id)
                threading.Thread(
                    target=self.execute_inbox_task, 
                    args=(process_id, "linkedin"), # Pass platform
                    daemon=True
                ).start()
                result['success'] = True
                result['payload'] = {'message': 'LinkedIn Inbox processing started.'}
                
            elif ttype == "process_sales_nav_inbox":
                process_id = params.get('process_id', task_id)
                threading.Thread(
                    target=self.execute_inbox_task, 
                    args=(process_id, "sales_navigator"), # Pass platform
                    daemon=True
                ).start()
                result['success'] = True
                result['payload'] = {'message': 'Sales Navigator Inbox processing started.'}
                
            elif ttype == 'inbox_action':
                params = task.get('params', {})
                session_id = params.get('session_id')
                action = params.get('action')

                logger.info(f"📥 Received inbox user action: '{action}' for session {session_id}")
                
                if session_id and self.enhanced_inbox:
                    # This call passes the user's decision to the waiting inbox process.
                    # The handle_inbox_action method will set a flag that the waiting loop can see.
                    self.enhanced_inbox.handle_inbox_action(session_id, params)
                    
                    result['success'] = True
                    result['payload'] = {'message': f"User action '{action}' for session '{session_id}' has been processed."}
                else:
                    result['error'] = 'Invalid session_id or inbox handler not initialized'
            # --- End of replacement ---
            elif ttype == 'stop_inbox_session':
                # Handle stop request for inbox session
                params = task.get('params', {})
                session_id = params.get('session_id')
                
                if session_id and self.enhanced_inbox:
                    self.enhanced_inbox.stop_inbox_session(session_id)
                    result['success'] = True
                    result['payload'] = {'message': f'Stop request sent to session {session_id}'}
                else:
                    result['error'] = 'Invalid session_id'

            elif ttype == 'stop_task':
                params = task.get('params', {})
                # Look for the new param, but fall back to the old one
                task_to_stop = params.get('task_to_stop') or params.get('task_id') 
                logger.info(f"🛑 Received STOP request for task: {task_to_stop}")

                if not task_to_stop:
                    raise Exception("No task_to_stop or task_id provided in stop_task action")

                # Check and stop active campaigns
                if task_to_stop in self.active_campaigns:
                    self.active_campaigns[task_to_stop]['stop_requested'] = True
                    logger.info(f"Set stop_requested flag for campaign {task_to_stop}")

                # Check and stop active inbox sessions
                elif self.enhanced_inbox and task_to_stop in self.enhanced_inbox.active_inbox_sessions:
                    self.enhanced_inbox.stop_inbox_session(task_to_stop)
                    logger.info(f"Called stop_inbox_session for {task_to_stop}")
                
                # Check and stop active keyword searches
                elif task_to_stop in self.active_searches:
                    self.active_searches[task_to_stop]['stop_requested'] = True
                    logger.info(f"Set stop_requested flag for search {task_to_stop}")

                elif task_to_stop in self.active_sales_nav_fetches:
                    self.active_sales_nav_fetches[task_to_stop]['stop_requested'] = True
                    logger.info(f"Set stop_requested flag for Sales Nav list fetch {task_to_stop}")
                
                else:
                    logger.warning(f"Could not find active task {task_to_stop} to stop. It might have already completed.")

                result['success'] = True
                result['payload'] = {'message': f"Stop request for {task_to_stop} processed."}
            
            elif ttype == "outreach_campaign" or ttype == "start_campaign":
                campaign_id = params.get('campaign_id', task_id)
                user_config = params.get('user_config', {})
                campaign_data = params.get('campaign_data', {})
                threading.Thread(
                    target=self.execute_outreach_task,
                    args=(task_id, campaign_id, user_config, campaign_data),
                    daemon=True
                ).start()
                result['success'] = True
                result['payload'] = {'message': 'Outreach campaign started', 'campaign_id': campaign_id}

            
            elif ttype == 'campaign_action':
                params = task.get('params', {})
                campaign_id = params.get('campaign_id')
                if campaign_id:
                    action = {
                        'action': params.get('action'),
                        'message': params.get('message'),
                        'contact_index': params.get('contact_index'),
                        'received_at': datetime.now().isoformat()
                    }
        # Ensure the campaign entry exists
                if campaign_id not in self.active_campaigns:
                    self.active_campaigns[campaign_id] = {
                        'awaiting_confirmation': False,
                        'user_action': None,
                        'current_contact_preview': None,
                        'status': 'unknown'
                    }
                self.active_campaigns[campaign_id]['user_action'] = action
                logger.info(f"📥 Applied campaign_action for {campaign_id}: {action['action']}")
                return {'success': True}              
            # --- THIS BLOCK IS NOW FIXED ---
            elif ttype == "keyword_search":
                # The main task_id IS the search_id for reporting
                # We pass the original task_id to the execution thread
                search_params = params.get('search_params', {})
                threading.Thread(target=self.execute_keyword_search_task, args=(task_id, search_params), daemon=True).start()
                
                result['success'] = True
                result['payload'] = {'message': 'Keyword search started', 'search_id': task_id}
            # --- END OF FIX ---
            elif ttype == "sync_network_stats":
                threading.Thread(target=self.execute_sync_network_stats_task, args=(task_id,), daemon=True).start()
                result['success'] = True
                result['payload'] = {'message': 'Network stats sync started', 'task_id': task_id}    
            
            elif ttype == 'process_non_responders':
                campaign_id = params.get('campaign_id')
                # Run in thread
                threading.Thread(target=self.process_non_responders, args=(campaign_id,), daemon=True).start()
                result['success'] = True
                result['payload'] = {'message': 'Started processing non-responders'}
            
            elif ttype == "process_sales_nav_inbox":
                process_id = params.get('process_id', task_id)
                threading.Thread(
                    target=self.execute_inbox_task, 
                    args=(process_id, "sales_navigator"), # Pass platform
                    daemon=True
                ).start()
                result['success'] = True
                result['payload'] = {'message': 'Sales Navigator Inbox processing started.'}
            
            elif ttype == "fetch_sales_nav_lists":
                threading.Thread(target=self.fetch_sales_nav_lists, args=(task_id,), daemon=True).start()
                result['success'] = True
                result['payload'] = {'message': 'Fetching Sales Nav lists...'}

            elif ttype == "sales_nav_outreach_campaign":
                campaign_id = params.get('campaign_id', task_id)
                user_config = params.get('user_config', {})
                campaign_params = params.get('campaign_params', {})
                threading.Thread(
                    target=self.run_sales_nav_outreach_campaign,
                    args=(task_id, campaign_id, user_config, campaign_params),
                    daemon=True
                ).start()
                result['success'] = True
                result['payload'] = {'message': 'Sales Nav campaign started', 'campaign_id': campaign_id}
            
            else:
                raise Exception(f"Unknown task type: {ttype}")
            
            logger.info(f"✅ Task {task_id[:8]}... logic completed for type {ttype}")
        
        except Exception as e:
            logger.exception(f"❌ Task {task_id[:8]}... failed: {e}")
            result['error'] = str(e)
            result['success'] = False
        
        finally:
            result['end_time'] = datetime.now().isoformat()
            # For threaded tasks, we report success immediately, the thread reports final status
            if ttype not in ["outreach_campaign", "start_campaign", "collect_profiles", "keyword_search", "campaign_action", "sync_network_stats", "fetch_sales_nav_lists", "sales_nav_outreach_campaign"]:
                try:
                    self.report_task_result(result)
                except Exception as report_e:
                    logger.error(f"Failed to report task result: {report_e}")
    
    def handle_inbox_action(self, session_id: str, action_data: Dict[str, Any]):
        """Handle inbox action from dashboard"""
        try:
            if not session_id:
                return {"success": False, "error": "No session_id provided"}
            
            logger.info(f"📥 Processing inbox action for session {session_id}: {action_data.get('action')}")
            
            # Pass the action directly to the enhanced inbox
            if hasattr(self, 'enhanced_inbox') and self.enhanced_inbox:
                self.enhanced_inbox.handle_inbox_action(session_id, action_data)
                return {"success": True, "message": "Action processed"}
            else:
                return {"success": False, "error": "Enhanced inbox not initialized"}
                
        except Exception as e:
            logger.error(f"Error handling inbox action: {e}")
            return {"success": False, "error": str(e)}

    def report_task_result(self, result):
        """Report task result back to dashboard"""
        try:
            SERVER_BASE = self.config.get('dashboard_url')
            report_url = f"{SERVER_BASE.rstrip('/')}/api/report-task"
            resp = requests.post(report_url, json=result, headers=self._get_auth_headers(), timeout=15)
            if resp.status_code == 200:
                logger.info(f"✅ Reported result for task {result.get('task_id')}")
            else:
                logger.warning(f"⚠️ Dashboard progress report returned status {resp.status_code}")
        except Exception as e:
            logger.error(f"Failed to report task result: {e}")

    def get_total_connection_count(self, driver) -> Optional[int]:
        """Scrape total LinkedIn connections count from user's profile page (stable 2025 method)."""
        try:
            logger.info("Syncing network stats: Navigating to user profile page...")

            # Step 1: Navigate to the user's profile
            driver.get("https://www.linkedin.com/in/")
            time.sleep(3)

            # Step 2: Wait for the connection count element
            # Updated to support new LinkedIn markup (e.g. <p class="...">239 connections</p>)
            def find_connection_element(d):
                elements = d.find_elements(By.XPATH, "//*[contains(translate(text(), 'CONNECTION', 'connection'), 'connection')]")
                for el in elements:
                    try:
                        txt = el.text.strip().lower()
                        # Matches exact phrases like "239 connections" or "500+ connections"
                        if re.search(r'^\d+\+?\s*connections?$', txt):
                            return el
                    except:
                        pass
                return False
                
            count_element = WebDriverWait(driver, 15).until(find_connection_element)

            count_text = count_element.text.strip()
            logger.info(f"Found connection count text: '{count_text}'")

            # Step 3: Parse and clean numeric value
            count_digits = re.sub(r"[^\d]", "", count_text)
            if not count_digits:
                logger.warning("Could not parse numeric value from connections text.")
                return None

            count = int(count_digits)
            if "+" in count_text and count == 500:
                logger.info("Detected '500+' display, reporting 501 as proxy.")
                count = 501

            logger.info(f"✅ Successfully extracted total connections: {count}")
            return count

        except TimeoutException:
            logger.error("Timed out waiting for the connections count on profile page.")
            return None
        except Exception as e:
            logger.error(f"Error scraping connection count from profile page: {e}", exc_info=True)
            return None
   
    # --- NEW FUNCTION: Wrapper for the sync task ---
    def execute_sync_network_stats_task(self, task_id):
        """Thread-safe wrapper to execute the network stats sync task."""
        self.browser_lock.acquire()
        payload = {}
        error = None
        success = False
        try:
            logger.info(f"🔑 Browser lock acquired for network sync task {task_id}")
            driver = self.get_shared_driver()
            if not driver:
                raise Exception("Failed to get a valid browser session for network sync.")
            
            connection_count = self.get_total_connection_count(driver)
            
            if connection_count is not None:
                payload = {'total_connections': connection_count}
                success = True
                logger.info(f"✅ Successfully synced network stats. Total connections: {connection_count}")
            else:
                error = "Failed to scrape connection count."
                success = False

        except Exception as e:
            logger.error(f"❌ A critical error occurred in network sync task {task_id}: {e}", exc_info=True)
            error = str(e)
            success = False
        finally:
            logger.info(f"🔑 Browser lock released for network sync task {task_id}")
            self.browser_lock.release()
            
            # Report the final result to the server
            self.report_task_result({
                'task_id': task_id,
                'type': 'sync_network_stats',
                'success': success,
                'payload': payload,
                'error': error
            })
    def report_collection_results_to_dashboard(self, collection_id, results, final=False):
        """Report profile collection results back to dashboard."""
        try:
            dashboard_url = self.config.get('dashboard_url')
            if not dashboard_url:
                return

            endpoint = f"{dashboard_url}/api/collection_results"
            
            payload = {
                'collection_id': collection_id,
                'results': results
            }
            if final:
                payload['final'] = True

            response = requests.post(endpoint, json=payload, timeout=45, verify=True)
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully reported collection results for {collection_id}")
            else:
                logger.warning(f"⚠️ Dashboard collection report returned status {response.status_code}")

        except Exception as e:
            logger.error(f"Could not report collection results for {collection_id}: {e}")
    
    def report_search_results_to_dashboard(self, search_id, results):
        """Report search results back to dashboard with better error handling"""
        try:
            dashboard_url = self.config.get('dashboard_url')
            if not dashboard_url:
                return

            endpoint = f"{dashboard_url}/api/search_results"
            
            response = requests.post(endpoint, json={
                'search_id': search_id,
                'results': results
            }, timeout=30, verify=True)
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully reported search results for {search_id}")
            else:
                logger.warning(f"⚠️ Dashboard search report returned status {response.status_code}")

        except Exception as e:
            logger.debug(f"Could not report search results for {search_id}: {e}")

    def report_inbox_results_to_dashboard(self, process_id, results):
        """Report inbox processing results back to dashboard - FIXED VERSION"""
        try:
            dashboard_url = self.config.get('dashboard_url')
            if not dashboard_url:
                logger.debug("No dashboard URL configured")
                return

            endpoint = f"{dashboard_url}/api/inbox_results"
            
            # CRITICAL FIX: Ensure results are JSON serializable
            def make_serializable(obj):
                """Recursively make object JSON serializable"""
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(item) for item in obj]
                elif isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                elif hasattr(obj, '__dict__'):
                    return make_serializable(obj.__dict__)
                elif isinstance(obj, Enum):
                    return obj.value
                elif hasattr(obj, 'value'):  # Additional check for enum-like objects
                    return obj.value
                else:
                    try:
                        json.dumps(obj)  # Test if it's already serializable
                        return obj
                    except (TypeError, ValueError):
                        return str(obj)
            
            # Convert results to serializable format
            serializable_results = make_serializable(results)
            
            # Add process metadata
            payload = {
                'process_id': process_id,
                'results': serializable_results,
                'timestamp': datetime.now().isoformat(),
                'client_id': self.config.get('client_id', str(uuid.uuid4()))
            }
            
            # Log what we're sending (truncated for debugging)
            logger.debug(f"Sending inbox results payload with {len(serializable_results.get('processed', []))} conversations")
            
            response = requests.post(
                endpoint, 
                json=payload,
                headers=self._get_auth_headers(), 
                timeout=30, 
                verify=True
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully reported inbox results for {process_id}")
                logger.info(f"  - Total processed: {serializable_results.get('total_processed', 0)}")
                logger.info(f"  - Auto-replied: {serializable_results.get('auto_replied', 0)}")
                logger.info(f"  - High priority: {serializable_results.get('high_priority', 0)}")
            else:
                logger.warning(f"⚠️ Dashboard inbox report returned status {response.status_code}")
                logger.debug(f"Response: {response.text[:500]}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON serialization error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Could not report inbox results for {process_id}: {e}", exc_info=True)
    # ==============================================
    # ENHANCED LINKEDIN AUTOMATION FUNCTIONS
    # ==============================================

    def initialize_browser(self):
        """Initialize Chrome browser with PERSISTENT profile for session persistence"""
        from selenium import webdriver
        
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Use a dedicated persistent profile directory per LinkedIn account.
            profile_identity, profile_dir = self._get_persistent_profile_dir()
            
            options.add_argument(f"--user-data-dir={profile_dir}")
            
            # Store profile path for reference (don't set temp_profile_dir since it's persistent)
            self.persistent_profile_dir = profile_dir
            logger.debug(f"Resolved browser profile identity: {profile_identity}")
            
            logger.info(f"🔧 Using persistent Chrome profile: {profile_dir}")
            
            # Additional options for better session persistence
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions-except")
            options.add_argument("--disable-plugins-discovery")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            
            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Browser initialized with persistent profile")
            return driver
            
        except Exception as e:
            logger.error(f"❌ Browser initialization failed: {e}")
            raise

    def human_delay(self, min_seconds=1, max_seconds=3):
        """Add human-like delays"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def type_like_human(self, element, text):
        """Type text with human-like delays"""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))

    def login(self):
        """Enhanced login with better session persistence detection"""
        try:
            logger.info("🔐 Checking LinkedIn session...")
            
            # First, try to go to LinkedIn feed to check for existing session
            self.driver.get("https://www.linkedin.com/feed")
            time.sleep(3)
            
            # Check if already logged in
            if self._is_logged_in():
                logger.info("✅ Found existing session - already logged in!")
                return True
            
            # If not logged in, try LinkedIn homepage first
            logger.info("🔄 No active session found, checking login page...")
            self.driver.get("https://www.linkedin.com")
            time.sleep(2)
            
            # Check again after going to homepage (sometimes redirects if logged in)
            if self._is_logged_in():
                logger.info("✅ Session restored from homepage redirect!")
                return True
            
            # Navigate to login page
            logger.info("🔑 Navigating to login page...")
            self.driver.get("https://www.linkedin.com/login")
            
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            except TimeoutException:
                logger.error("❌ Login page did not load properly")
                return False
            
            self.human_delay(1.5, 3)
            
            # Type email
            username_field = self.driver.find_element(By.ID, "username")
            logger.info("✏️ Typing email...")
            self.type_like_human(username_field, self.email)
            
            self.human_delay(1, 2)
            
            # Type password
            password_field = self.driver.find_element(By.ID, "password")
            logger.info("✏️ Typing password...")
            self.type_like_human(password_field, self.password)
            
            # Click Login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.safe_click(self.driver, login_button)
            
            # Wait for login success with longer timeout for 2FA
            try:
                WebDriverWait(self.driver, 45).until(lambda d: self._is_logged_in())
                logger.info("✅ LinkedIn login successful! Session will be saved for next time.")
                self.human_delay(2, 4)
                return True
                
            except TimeoutException:
                current_url = self.driver.current_url
                if "checkpoint" in current_url or "challenge" in current_url:
                    logger.warning("⚠️ 2FA/Security challenge detected")
                    logger.info("⏳ Please complete the security challenge manually...")
                    logger.info("✋ Waiting up to 5 minutes for manual completion...")
                    
                    # Extended wait for manual 2FA completion
                    for i in range(300):  # 5 minutes
                        time.sleep(1)
                        if self._is_logged_in():
                            logger.info("✅ Security challenge completed successfully!")
                            logger.info("💾 Session saved - no login required next time!")
                            return True
                        
                        # Show progress every 30 seconds
                        if i % 30 == 0 and i > 0:
                            logger.info(f"⏳ Still waiting... ({i//60}m {i%60}s elapsed)")
                    
                    logger.error("❌ Security challenge timeout")
                    return False
                
                logger.error("❌ Login failed or timed out")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login exception: {e}")
            return False

    def _is_logged_in(self):
        """Enhanced login status check with more indicators"""
        try:
            current_url = self.driver.current_url
            
            # Check URL patterns that indicate successful login
            logged_in_patterns = [
                "linkedin.com/feed",
                "linkedin.com/in/",
                "linkedin.com/mynetwork",
                "linkedin.com/jobs", 
                "linkedin.com/messaging",
                "linkedin.com/notifications"
            ]
            
            if any(pattern in current_url for pattern in logged_in_patterns):
                return True
            
            # Check for navigation elements
            nav_selectors = [
                "[data-test-id='global-nav']",
                ".global-nav",
                ".global-nav__nav",
                "nav.global-nav",
                ".global-nav__primary-items"
            ]
            
            for selector in nav_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        return True
                except:
                    continue
            
            # Check for profile elements
            profile_selectors = [
                ".global-nav__primary-item--profile",
                ".global-nav__me-photo", 
                "[data-test-id='nav-profile-photo']",
                "button[aria-label*='View profile']"
            ]
            
            for selector in profile_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        return True
                except:
                    continue
            
            # Check for search box (appears when logged in)
            try:
                search_elements = self.driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='Search']")
                if search_elements:
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.debug(f"Login check error: {e}")
            return False
    
    def get_user_profile_name(self, driver) -> Optional[str]:
        """Get the logged-in user's name with multiple fallback strategies"""
        logger.info("🔎 Attempting to get user's profile name with enhanced strategies...")
        
        # STRATEGY 1: "Me" button dropdown (most reliable)
        try:
            # FIX: Use a more general selector that is less likely to change
            me_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.global-nav__primary-link[aria-label*='Me'], button[data-test-id='nav-me-dropdown-trigger']"))
            )
            driver.execute_script("arguments[0].click();", me_button)
            time.sleep(1.5)

            # FIX: Wait for a non-empty span to ensure the name has loaded
            name_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.global-nav__me-content a.global-nav__me-profile-link span:not(:empty), .global-nav__me-name"))
            )
            name = name_element.text.strip()
            
            # Close the dropdown
            driver.execute_script("arguments[0].click();", me_button)
            time.sleep(0.5)

            if name and len(name) > 1:
                logger.info(f"✅ Got name from nav dropdown: {name}")
                return name
        except Exception as e:
            logger.debug(f"Strategy 1 (Nav Dropdown) failed: {e}")
            try:
                # Attempt to close dropdown if it failed mid-way
                body = driver.find_element(By.TAG_NAME, 'body')
                body.click()
            except: pass

        # STRATEGY 2: Fallback to profile photo alt text (very reliable)
        try:
            # FIX: Use a more specific selector for the profile photo image
            photo_element = driver.find_element(By.CSS_SELECTOR, "img.global-nav__me-photo-image, img.global-nav__me-photo")
            alt_text = photo_element.get_attribute('alt')
            if alt_text and "View profile" not in alt_text:
                 logger.info(f"✅ Got name from profile photo alt text: {alt_text}")
                 return alt_text
        except Exception as e:
            logger.debug(f"Strategy 2 (Profile Photo) failed: {e}")
            
        logger.warning("❌ All strategies failed to get user profile name.")
        return None


    def extract_profile_data(self, driver):
        """Extract profile data from LinkedIn profile page"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import NoSuchElementException

        def normalize_text(value):
            return re.sub(r"\s+", " ", value or "").strip()

        def is_probable_name(value):
            value = normalize_text(value)
            if not value or len(value) > 80:
                return False

            lower_value = value.lower()
            blocked_terms = [
                "about",
                "activity",
                "connect",
                "contact info",
                "experience",
                "followers",
                "following",
                "message",
                "mutual",
                "open to",
                "people also viewed",
                "profile",
                "see all",
                "show all",
                "view profile",
            ]
            if any(term in lower_value for term in blocked_terms):
                return False

            tokens = [token for token in value.split(" ") if token]
            if not 1 <= len(tokens) <= 5:
                return False

            return any(any(char.isalpha() for char in token) for token in tokens)

        def is_probable_summary(value, excluded_texts=None):
            value = normalize_text(value)
            if not value:
                return False

            if excluded_texts and value in excluded_texts:
                return False

            if len(value) < 8 or len(value) > 220:
                return False

            lower_value = value.lower()
            blocked_terms = [
                "about",
                "activity",
                "connect",
                "contact info",
                "experience",
                "followers",
                "following",
                "message",
                "mutual",
                "people also viewed",
                "see all",
                "show all",
            ]
            return not any(term in lower_value for term in blocked_terms)

        def get_first_matching_text(selectors, predicate):
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                except Exception:
                    continue

                for element in elements:
                    text = normalize_text(element.text)
                    if predicate(text):
                        return text
            return ""

        def get_profile_snapshot():
            script = """
                const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                };
                const uniqueTexts = (nodes, limit) => {
                    const texts = [];
                    for (const node of nodes) {
                        if (!isVisible(node)) continue;
                        const text = normalize(node.innerText || node.textContent || '');
                        if (!text || texts.includes(text)) continue;
                        texts.push(text);
                        if (texts.length >= limit) break;
                    }
                    return texts;
                };

                const headingNodes = [];
                const headingSelectors = ['main h1', 'main h2', 'section h1', 'section h2', 'h1', 'h2', '[data-anonymize="person-name"]'];
                for (const selector of headingSelectors) {
                    for (const node of document.querySelectorAll(selector)) {
                        headingNodes.push(node);
                    }
                }

                const firstVisibleHeading = headingNodes.find(isVisible) || null;
                const headerContainer = firstVisibleHeading
                    ? (firstVisibleHeading.closest('section, article, main, div') || firstVisibleHeading.parentElement || document.body)
                    : document.body;

                let aboutText = '';
                for (const section of document.querySelectorAll('section, div')) {
                    if (!isVisible(section)) continue;

                    const labels = Array.from(section.querySelectorAll('h1, h2, h3, span, p'))
                        .map(node => normalize(node.innerText || node.textContent || ''))
                        .filter(Boolean);

                    if (!labels.some(label => label.toLowerCase() === 'about')) continue;

                    const detailNodes = Array.from(section.querySelectorAll('p, span, div, li'));
                    const detailTexts = uniqueTexts(detailNodes, 80).filter(text => text.toLowerCase() !== 'about');
                    aboutText = detailTexts.sort((a, b) => b.length - a.length)[0] || '';
                    if (aboutText) break;
                }

                return {
                    nameCandidates: uniqueTexts(headingNodes, 20),
                    headlineCandidates: uniqueTexts(headerContainer.querySelectorAll('p, h3, h4, span, div, li'), 60),
                    aboutText
                };
            """
            try:
                return driver.execute_script(script) or {}
            except Exception as exc:
                logger.debug(f"Profile snapshot script failed: {exc}")
                return {}
        
        profile_data = {}
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            snapshot = get_profile_snapshot()

            name_candidates = [normalize_text(text) for text in snapshot.get('nameCandidates', []) if normalize_text(text)]
            headline_candidates = [normalize_text(text) for text in snapshot.get('headlineCandidates', []) if normalize_text(text)]
            about_text = normalize_text(snapshot.get('aboutText', ''))

            name = next((text for text in name_candidates if is_probable_name(text)), "")
            if not name:
                name = get_first_matching_text(
                    [
                        "main h1",
                        "main h2",
                        "section h1",
                        "section h2",
                        "[data-anonymize='person-name']",
                        "h1",
                        "h2",
                    ],
                    is_probable_name
                )

            profile_data['extracted_name'] = name or "Professional"
            if name:
                logger.info(f"📝 Extracted name: {profile_data['extracted_name']}")
            else:
                logger.warning("Could not confidently extract profile name. Using fallback.")

            excluded_texts = {profile_data['extracted_name']}
            headline = next((text for text in headline_candidates if is_probable_summary(text, excluded_texts)), "")
            if not headline:
                headline = get_first_matching_text(
                    [
                        "main p",
                        "main div",
                        "section p",
                        "section div",
                        "div.text-body-medium.break-words",
                        "p",
                    ],
                    lambda text: is_probable_summary(text, excluded_texts)
                )

            profile_data['extracted_headline'] = headline
            if headline:
                logger.info(f"💼 Extracted headline: {headline[:50]}...")

            if not about_text:
                about_selectors = [
                    "[data-test-id='about-section'] .pv-shared-text-with-see-more span[aria-hidden='true']",
                    ".pv-about-section .pv-shared-text-with-see-more span",
                    "section[data-view-name*='about'] span[aria-hidden='true']",
                    "section[data-view-name*='about'] div[aria-hidden='true']",
                ]
                for selector in about_selectors:
                    try:
                        about_elem = driver.find_element(By.CSS_SELECTOR, selector)
                        about_text = normalize_text(about_elem.text)
                        if about_text:
                            break
                    except NoSuchElementException:
                        continue

            if about_text:
                profile_data['about_snippet'] = about_text[:150] + "..." if len(about_text) > 150 else about_text
                logger.info(f"📄 Extracted about: {profile_data['about_snippet'][:50]}...")

            # Set defaults
            if not profile_data.get('about_snippet'):
                profile_data['about_snippet'] = ""
            if not profile_data.get('extracted_headline'):
                profile_data['extracted_headline'] = ""

        except Exception as e:
            logger.warning(f"⚠️ Profile data extraction failed: {e}")
            profile_data = {
                'extracted_name': 'Professional',
                'extracted_headline': '',
                'about_snippet': ''
            }

        return profile_data

    def generate_message(self, name, company, role, service_1, service_2, profile_data=None):
        """Generate personalized message using AI via backend proxy"""
        actual_name = profile_data.get('extracted_name', name) if profile_data else name
        extracted_headline = profile_data.get('extracted_headline', '') if profile_data else ''
        about_snippet = profile_data.get('about_snippet', '') if profile_data else ''

        fallback_msg = f"Hi {actual_name}, I'm impressed by your {role} work at {company}. I'd love to connect and exchange insights. Looking forward to connecting!"
        
        MESSAGE_TEMPLATE = """Create a personalized LinkedIn connection message based on the profile information provided.

Profile Information:
- Name: {Name}
- Company: {Company}  
- Role: {Role}
- Headline / Company Description: {Headline}
- Services/Expertise: {service_1}, {service_2}
- About/Bio: {about_snippet}

Create a professional, engaging message under 280 characters that:
1. Addresses them by name (ONLY USE FIRST NAMES)
2. References their specific work/company
3. Mentions a relevant connection point
4. Has a clear call to action

Return ONLY the message text, no labels or formatting.
"""

        prompt = MESSAGE_TEMPLATE.format(
            Name=actual_name,
            Company=company,
            Role=role,
            Headline=extracted_headline,
            service_1=service_1 or "your field",
            service_2=service_2 or "industry trends",
            about_snippet=about_snippet
        )

        dashboard_url = self.config.get('dashboard_url', 'http://127.0.0.1:5000')
        endpoint = f"{dashboard_url.rstrip('/')}/api/client/ai/generate"

        for attempt in range(3):
            try:
                response = requests.post(
                    endpoint,
                    json={'prompt': prompt},
                    headers=self._get_auth_headers(),
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        message = data.get('message', '').strip()
                        message = re.sub(r'^(Icebreaker:|Message:)\s*', '', message, flags=re.IGNORECASE)
                        message = message.strip('"\'[]')
                        
                        if len(message) > 280:
                            message = message[:277] + "..."
                            
                        return message
                    else:
                        logger.error(f"❌ Backend AI Generation error: {data.get('error')}")
                        break
                elif response.status_code == 429:
                    logger.warning("⏳ Daily AI quota exceeded or rate limit hit. Using fallback message.")
                    return fallback_msg[:280]
                else:
                    logger.error(f"❌ AI proxy returned {response.status_code}: {response.text}")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Error communicating with AI proxy: {e}")
                time.sleep(2)

        # Fallback message
        return fallback_msg[:280]

    def safe_click(self, driver, element):
        """Safely click an element with fallback methods"""
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.common.exceptions import ElementClickInterceptedException, ElementNotInteractableException
        
        try:
            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", element)
            time.sleep(random.uniform(0.5, 1.5))
            element.click()
            return True
        except (ElementClickInterceptedException, ElementNotInteractableException):
            try:
                ActionChains(driver).move_to_element(element).pause(0.5).click().perform()
                return True
            except Exception as e:
                logger.warning(f"Click fallback failed: {e}")
                return False
        except Exception as e:
            logger.warning(f"Click failed: {e}")
            return False

    def go_to_next_page(self, driver, timeout=10):
        """Advance LinkedIn search pagination when a visible Next button exists."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        selectors = [
            (By.CSS_SELECTOR, "button[data-testid='pagination-controls-next-button-visible']"),
            (By.CSS_SELECTOR, "button[aria-label='Next']"),
            (By.XPATH, "//button[.//span[normalize-space()='Next']]"),
            (By.XPATH, "//button[normalize-space()='Next']"),
        ]

        previous_url = (driver.current_url or "").strip()
        previous_marker = None
        try:
            items = driver.find_elements(By.CSS_SELECTOR, "main a[href*='/in/'], main a[href*='/sales/lead/']")
            for item in items:
                href = (item.get_attribute("href") or "").strip()
                if href:
                    previous_marker = href
                    break
        except Exception:
            previous_marker = None

        next_button = None
        for by, selector in selectors:
            try:
                candidates = driver.find_elements(by, selector)
            except Exception:
                continue

            for candidate in candidates:
                try:
                    if not candidate.is_displayed():
                        continue
                    disabled_attr = (candidate.get_attribute("disabled") or "").strip().lower()
                    aria_disabled = (candidate.get_attribute("aria-disabled") or "").strip().lower()
                    classes = (candidate.get_attribute("class") or "").lower()
                    if disabled_attr in {"true", "disabled"} or aria_disabled == "true" or "disabled" in classes:
                        logger.info("Next page button is present but disabled.")
                        return False
                    next_button = candidate
                    break
                except Exception:
                    continue
            if next_button:
                break

        if not next_button:
            logger.info("Next page button not found on the current results page.")
            return False

        try:
            if not self.safe_click(driver, next_button):
                driver.execute_script("arguments[0].click();", next_button)
        except Exception as exc:
            logger.warning(f"Failed to click next page button: {exc}")
            return False

        def page_advanced(_driver):
            try:
                current_url = (_driver.current_url or "").strip()
                if current_url and current_url != previous_url:
                    return True
            except Exception:
                pass

            if previous_marker:
                try:
                    items = _driver.find_elements(By.CSS_SELECTOR, "main a[href*='/in/'], main a[href*='/sales/lead/']")
                    for item in items:
                        href = (item.get_attribute("href") or "").strip()
                        if href and href != previous_marker:
                            return True
                except Exception:
                    pass

            try:
                loading_spinners = _driver.find_elements(By.CSS_SELECTOR, "[aria-busy='true'], .artdeco-loader, .search-loader")
                if loading_spinners:
                    return False
            except Exception:
                pass

            return False

        try:
            WebDriverWait(driver, timeout).until(page_advanced)
        except Exception:
            logger.warning("Clicked Next, but could not confirm that the results page advanced.")
            return False

        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
            )
        except Exception:
            pass

        self.human_delay(2, 4)
        return True

    

    def find_element_safe(self, driver, selectors, timeout=10):
        """Find element using multiple selectors"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        
        for selector_type, selector in selectors:
            try:
                if selector_type == "xpath":
                    element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                else:
                    element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                return element
            except TimeoutException:
                continue
        return None

    def _find_active_connect_dialog(self, driver, timeout=8):
        """Find a visible invite dialog. Used as a helper, not a hard gate."""
        deadline = time.time() + timeout
        selectors = [
            (By.CSS_SELECTOR, "dialog"),
            (By.CSS_SELECTOR, "#artdeco-modal-outlet [data-test-modal-id='send-invite-modal'][aria-hidden='false']"),
            (By.CSS_SELECTOR, "#artdeco-modal-outlet [data-test-modal-container][data-test-modal-id='send-invite-modal']"),
            (By.CSS_SELECTOR, "#artdeco-modal-outlet .artdeco-modal-overlay:not([aria-hidden='true'])"),
            (By.CSS_SELECTOR, "div[role='dialog'][aria-labelledby]"),
            (By.CSS_SELECTOR, "div[role='dialog']"),
            (By.CSS_SELECTOR, "div.artdeco-modal"),
            (By.CSS_SELECTOR, "#artdeco-modal-outlet div[data-test-modal][role='dialog']"),
            (By.CSS_SELECTOR, "#artdeco-modal-outlet div[role='dialog']"),
            (By.CSS_SELECTOR, "div[data-test-modal][role='dialog']"),
            (By.CSS_SELECTOR, "div.artdeco-modal.send-invite"),
        ]

        while time.time() < deadline:
            for by, selector in selectors:
                try:
                    dialogs = driver.find_elements(by, selector)
                except Exception:
                    continue

                for dialog in reversed(dialogs):
                    try:
                        if not dialog.is_displayed():
                            continue
                        aria_hidden = (dialog.get_attribute("aria-hidden") or "").strip().lower()
                        if aria_hidden == "true":
                            continue
                        return dialog
                    except Exception:
                        continue
            time.sleep(0.2)
        return None

    def _wait_for_people_results(self, driver, timeout=12):
        """Wait for LinkedIn people search results to render before scanning for buttons."""
        deadline = time.time() + timeout
        result_selectors = [
            (By.CSS_SELECTOR, "main li.reusable-search__result-container"),
            (By.CSS_SELECTOR, "main div.entity-result"),
            (By.CSS_SELECTOR, "main li[data-chameleon-result-urn]"),
            (By.CSS_SELECTOR, "main a[href*='/in/']"),
            (By.CSS_SELECTOR, "main a[href*='/sales/lead/']"),
        ]

        while time.time() < deadline:
            for by, selector in result_selectors:
                try:
                    matches = driver.find_elements(by, selector)
                except Exception:
                    continue

                for match in matches:
                    try:
                        if match.is_displayed():
                            return True
                    except Exception:
                        continue
            time.sleep(0.25)
        return False

    def _button_or_card_indicates_sent(self, driver, button):
        """Check whether the clicked result card now reflects a sent invitation."""
        try:
            return bool(driver.execute_script("""
                const btn = arguments[0];
                if (!btn) return false;

                const textOf = (node) => ((node?.innerText || '') + ' ' + (node?.getAttribute?.('aria-label') || '')).toLowerCase();
                const selfText = textOf(btn);
                if (selfText.includes('pending') || selfText.includes('invitation sent')) {
                    return true;
                }

                const card = btn.closest(
                    "li, .reusable-search__result-container, .entity-result, [data-chameleon-result-urn], .search-results-container li"
                );
                if (!card) return false;

                const cardText = textOf(card);
                if (cardText.includes('invitation sent')) {
                    return true;
                }

                const pendingButton = Array.from(card.querySelectorAll('button, span, div')).find((node) => {
                    const text = textOf(node).trim();
                    return text === 'pending' || text.includes('invitation sent');
                });
                return Boolean(pendingButton);
            """, button))
        except Exception:
            return False

    def _has_active_invite_modal(self, driver):
        """Detect LinkedIn's active send-invite modal using the live outlet DOM."""
        try:
            return bool(driver.execute_script("""
                const outlet = document.querySelector('#artdeco-modal-outlet');
                if (!outlet) return false;

                const modalRoots = Array.from(
                    outlet.querySelectorAll(
                        "[data-test-modal-id='send-invite-modal'], " +
                        "[data-test-modal-container][data-test-modal-id='send-invite-modal'], " +
                        ".artdeco-modal-overlay, " +
                        ".artdeco-modal.send-invite, " +
                        ".artdeco-modal[role='dialog'], " +
                        "[data-test-modal][role='dialog'], " +
                        "[role='dialog']"
                    )
                );

                return modalRoots.some((node) => {
                    if (!node) return false;

                    const ariaHidden = (node.getAttribute('aria-hidden') || '').trim().toLowerCase();
                    if (ariaHidden === 'true') return false;

                    const visible = Boolean(node.offsetParent || node.getClientRects().length);
                    const dialog = node.matches('.artdeco-modal, [role="dialog"]')
                        ? node
                        : node.querySelector('.artdeco-modal.send-invite, .artdeco-modal[role="dialog"], [data-test-modal][role="dialog"], [role="dialog"]');
                    const actionbar = (dialog && dialog.querySelector('.artdeco-modal__actionbar'))
                        || node.querySelector('.artdeco-modal__actionbar');
                    const sendButton = (actionbar && actionbar.querySelector(
                        "button[aria-label='Send without a note'], " +
                        "button[aria-label*='Send without a note'], " +
                        "button.artdeco-button--primary"
                    )) || node.querySelector(
                        "button[aria-label='Send without a note'], " +
                        "button[aria-label*='Send without a note']"
                    );
                    const text = ((node.innerText || '') + ' ' + ((dialog && dialog.innerText) || '')).toLowerCase();

                    return visible && (
                        Boolean(sendButton) ||
                        text.includes('send without a note') ||
                        text.includes('add a note')
                    );
                });
            """))
        except Exception as exc:
            logger.debug(f"Invite modal probe failed: {exc}")
            return False

    def dismiss_active_modal(self, driver, timeout=3):
        """Dismiss a visible modal so the bot does not click behind it."""
        dialog = self._find_active_connect_dialog(driver, timeout=timeout)
        if not dialog:
            return True

        selectors = [
            (By.CSS_SELECTOR, "button[aria-label='Dismiss']"),
            (By.CSS_SELECTOR, "button[aria-label='Close']"),
            (By.CSS_SELECTOR, "button.artdeco-modal__dismiss"),
            (By.XPATH, ".//button[@aria-label='Dismiss' or @aria-label='Close']"),
        ]

        for by, selector in selectors:
            try:
                buttons = dialog.find_elements(by, selector)
            except Exception:
                continue

            for button in buttons:
                try:
                    if not button.is_displayed():
                        continue
                    if self.safe_click(driver, button):
                        time.sleep(0.5)
                        return self._find_active_connect_dialog(driver, timeout=1) is None
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(0.5)
                    return self._find_active_connect_dialog(driver, timeout=1) is None
                except Exception:
                    continue
        return False

    def _wait_for_invite_submit_result(self, driver, timeout=4):
        """Confirm invite submission by pending state or modal closure."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                pending_items = driver.find_elements(
                    By.XPATH,
                    "//button[contains(., 'Pending')] | //span[contains(., 'Pending')]"
                )
                for item in pending_items:
                    if item.is_displayed():
                        return True
            except Exception:
                pass

            if self._find_active_connect_dialog(driver, timeout=0.2) is None:
                return True
            time.sleep(0.25)
        return False

    def _log_invite_modal_diagnostics(self, driver, context, selectors):
        """Capture lightweight diagnostics for failed invite modal actions."""
        original_handle = None
        try:
            original_handle = driver.current_window_handle
            logger.warning(
                f"[invite_diag:{context}] current_handle={original_handle} "
                f"handles={len(driver.window_handles)} url='{driver.current_url}' title='{driver.title}'"
            )
        except Exception as exc:
            logger.warning(f"[invite_diag:{context}] window_state_error={exc}")

        try:
            dialog_count = len(driver.find_elements(By.CSS_SELECTOR, "#artdeco-modal-outlet div[role='dialog'], div.artdeco-modal"))
            logger.warning(f"[invite_diag:{context}] dialog_count={dialog_count}")
        except Exception as exc:
            logger.warning(f"[invite_diag:{context}] dialog_count_error={exc}")

        try:
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                handle_dialog_count = len(
                    driver.find_elements(By.CSS_SELECTOR, "#artdeco-modal-outlet div[role='dialog'], div.artdeco-modal")
                )
                logger.warning(
                    f"[invite_diag:{context}] handle={handle} "
                    f"url='{driver.current_url}' title='{driver.title}' dialogs={handle_dialog_count}"
                )
        except Exception as exc:
            logger.warning(f"[invite_diag:{context}] handle_scan_error={exc}")
        finally:
            if original_handle:
                try:
                    driver.switch_to.window(original_handle)
                    driver.switch_to.default_content()
                except Exception:
                    pass

        for by, selector in selectors:
            try:
                matches = driver.find_elements(by, selector)
            except Exception:
                continue

            if matches:
                logger.warning(f"[invite_diag:{context}] selector='{selector}' matches={len(matches)}")

            for index, element in enumerate(matches[:2]):
                try:
                    text = re.sub(r"\s+", " ", (element.text or "")).strip()[:80]
                    aria = (element.get_attribute("aria-label") or "").strip()[:80]
                    classes = (element.get_attribute("class") or "").strip()[:120]
                    logger.warning(
                        f"[invite_diag:{context}] candidate#{index + 1} "
                        f"displayed={element.is_displayed()} enabled={element.is_enabled()} "
                        f"aria='{aria}' text='{text}' class='{classes}'"
                    )
                except Exception:
                    continue

        try:
            modal_html = driver.execute_script("""
                let dialog = document.querySelector('div[role="dialog"]');
                if (dialog) return (dialog.outerHTML || '').replace(/\\s+/g, ' ').trim().slice(0, 1200);
                
                const outlet = document.querySelector('#artdeco-modal-outlet');
                if (!outlet) return '';
                return (outlet.outerHTML || '').replace(/\\s+/g, ' ').trim().slice(0, 1200);
            """)
            logger.warning(f"[invite_diag:{context}] modal_html='{modal_html or '<empty>'}'")
        except Exception as exc:
            logger.warning(f"[invite_diag:{context}] modal_html_error={exc}")

    def _iter_window_handles(self, driver):
        """Yield available window handles, keeping current one first."""
        try:
            current = driver.current_window_handle
            handles = list(driver.window_handles)
        except Exception:
            return []

        ordered = [current]
        for handle in handles:
            if handle != current:
                ordered.append(handle)
        return ordered

    def _find_send_button_across_contexts(self, driver, selectors, wait_seconds):
        """Find a visible send button across tabs/windows and top-level frames."""
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        for handle in self._iter_window_handles(driver):
            try:
                driver.switch_to.window(handle)
                driver.switch_to.default_content()
            except Exception:
                continue

            frame_targets = [None]
            try:
                frame_count = len(driver.find_elements(By.TAG_NAME, "iframe"))
                frame_targets.extend(range(frame_count))
            except Exception:
                pass

            for frame_index in frame_targets:
                try:
                    driver.switch_to.default_content()
                    if frame_index is not None:
                        driver.switch_to.frame(frame_index)
                except Exception:
                    continue

                for by, selector in selectors:
                    candidates = []
                    try:
                        clickable = WebDriverWait(driver, wait_seconds).until(
                            EC.element_to_be_clickable((by, selector))
                        )
                        candidates.append(clickable)
                    except TimeoutException:
                        pass
                    except Exception:
                        pass

                    try:
                        candidates.extend(driver.find_elements(by, selector))
                    except Exception:
                        pass

                    for candidate in candidates:
                        try:
                            if candidate.is_displayed() and candidate.is_enabled():
                                return handle, frame_index, candidate
                        except Exception:
                            continue
        return None, None, None

    def click_send_without_note_button(self, driver, timeout=12, dialog=None, context="invite_flow"):
        """Click Send without note with reliability-first waiting and verification."""
        selectors = [
            (By.XPATH, "//button[contains(., 'Send without a note')]"),
            (By.XPATH, "//button[contains(@aria-label, 'Send without a note')]"),
            (By.CSS_SELECTOR, "button[aria-label='Send without a note']"),
            (By.XPATH, "//button[.//span[contains(normalize-space(), 'Send without a note')]]"),
            (By.CSS_SELECTOR, "div[role='dialog'] .artdeco-button--primary"),
            (By.CSS_SELECTOR, "div.artdeco-modal__actionbar button.artdeco-button--primary"),
            (By.CSS_SELECTOR, "#artdeco-modal-outlet button[aria-label='Send without a note']"),
            (By.CSS_SELECTOR, "button.connect-cta-form__send"),
            (By.CSS_SELECTOR, "button[aria-label='Send now']"),
            (By.XPATH, "//button[contains(@aria-label, 'Send invitation')]"),
        ]

        deadline = time.time() + timeout
        settle_deadline = min(deadline, time.time() + 2.5)
        original_handle = None
        try:
            original_handle = driver.current_window_handle
        except Exception:
            original_handle = None

        # Phase 1: short settle wait so LinkedIn can render modal actionbar.
        while time.time() < settle_deadline:
            if self._find_active_connect_dialog(driver, timeout=0.2):
                break
            for by, selector in selectors[:3]:
                try:
                    if any(btn.is_displayed() for btn in driver.find_elements(by, selector)):
                        settle_deadline = time.time()
                        break
                except Exception:
                    continue
            time.sleep(0.2)

        # Phase 2: explicit clickable wait + layered click fallbacks.
        while time.time() < deadline:
            wait_seconds = max(0.2, min(1.2, deadline - time.time()))
            active_handle, frame_index, candidate = self._find_send_button_across_contexts(
                driver,
                selectors,
                wait_seconds
            )

            if not candidate:
                time.sleep(0.25)
                continue

            try:
                driver.switch_to.window(active_handle)
                driver.switch_to.default_content()
                if frame_index is not None:
                    driver.switch_to.frame(frame_index)
            except Exception:
                pass

            try:
                if not candidate.is_displayed() or not candidate.is_enabled():
                    time.sleep(0.15)
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", candidate)
                time.sleep(0.15)

                clicked = False
                try:
                    candidate.click()
                    clicked = True
                    logger.info("Clicked Send Without Note natively.")
                except Exception:
                    pass

                if not clicked:
                    clicked = self.safe_click(driver, candidate)
                    if clicked:
                        logger.info("Clicked Send Without Note via safe_click.")

                if not clicked:
                    try:
                        driver.execute_script("arguments[0].click();", candidate)
                        clicked = True
                        logger.info("Clicked Send Without Note via JS.")
                    except Exception:
                        clicked = False

                if clicked and self._wait_for_invite_submit_result(driver, timeout=4):
                    if original_handle:
                        try:
                            driver.switch_to.window(original_handle)
                            driver.switch_to.default_content()
                        except Exception:
                            pass
                    return True
            except Exception:
                pass

            time.sleep(0.2)

        logger.warning(f"Could not find or click Send Without Note button after {timeout}s.")
        if original_handle:
            try:
                driver.switch_to.window(original_handle)
                driver.switch_to.default_content()
            except Exception:
                pass
        self._log_invite_modal_diagnostics(driver, context, selectors)
        return False

    def _normalize_linkedin_url(self, url):
        if not url:
            return ""
        if url.startswith("/"):
            return f"https://www.linkedin.com{url}"
        return url

    def _extract_sales_nav_list_name(self, element):
        """Extract a human-readable Sales Nav saved-search title."""
        title = (element.text or "").strip()

        if not title or title in {"…", "..."}:
            title = (element.get_attribute("title") or "").strip()

        if not title:
            aria_label = (element.get_attribute("aria-label") or "").strip()
            prefix = "Go to search results for "
            title = aria_label[len(prefix):].strip() if aria_label.startswith(prefix) else aria_label

        if not title:
            title = (element.get_attribute("innerText") or "").strip()

        if "\n" in title:
            title = next((line.strip() for line in title.splitlines() if line.strip()), title)

        return re.sub(r"\s+", " ", title).strip()

    def _scroll_sales_nav_saved_lists_panel(self, driver, anchor=None):
        """Scroll the saved-searches panel to reveal more list entries."""
        try:
            driver.execute_script(
                """
                const anchor = arguments[0];
                if (anchor) {
                    anchor.scrollIntoView({block: 'end'});
                    let parent = anchor.parentElement;
                    while (parent) {
                        const style = window.getComputedStyle(parent);
                        const canScroll = ['auto', 'scroll'].includes(style.overflowY) &&
                            parent.scrollHeight > parent.clientHeight;
                        if (canScroll) {
                            parent.scrollTop = parent.scrollHeight;
                            return true;
                        }
                        parent = parent.parentElement;
                    }
                }
                window.scrollBy(0, 500);
                return false;
                """,
                anchor,
            )
        except Exception:
            pass

    def _get_sales_nav_result_candidates(self, driver):
        """Return visible Sales Navigator row action buttons with extracted lead names."""
        candidates = []
        selectors = [
            "button[aria-label^='See more actions for ']",
            "button[aria-label*='See more actions for']",
            "button[data-search-overflow-trigger]",
        ]

        seen_names = set()
        for selector in selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue

            for button in buttons:
                try:
                    if not button.is_displayed() or not button.is_enabled():
                        continue

                    label = (button.get_attribute("aria-label") or "").strip()
                    match = re.search(r"See more actions for\s+(.+)", label)
                    name = match.group(1).strip() if match else label or f"lead-{button.id}"

                    if name in seen_names:
                        continue

                    seen_names.add(name)
                    candidates.append({"name": name, "button": button})
                except Exception:
                    continue

            if candidates:
                break

        return candidates

    def _dismiss_sales_nav_overlays(self, driver):
        """Dismiss open Sales Navigator menus or modals between lead actions."""
        try:
            from selenium.webdriver.common.keys import Keys

            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception:
            pass

    def _click_sales_nav_connect_action(self, driver):
        """Click the Connect action from an opened Sales Navigator row menu."""
        selectors = [
            ("xpath", "//div[starts-with(@id, 'hue-menu-')]//*[self::button or @role='menuitem' or self::li][.//span[normalize-space()='Connect'] or normalize-space()='Connect']"),
            ("xpath", "//*[@role='menuitem'][.//span[normalize-space()='Connect'] or normalize-space()='Connect']"),
            ("xpath", "//button[.//span[normalize-space()='Connect']]"),
            ("css", "button[aria-label*='Connect']"),
        ]

        for selector_type, selector in selectors:
            try:
                if selector_type == "xpath":
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    if not element.is_displayed():
                        continue
                    if self.safe_click(driver, element):
                        return True
                    driver.execute_script("arguments[0].click();", element)
                    return True
            except Exception:
                continue

        return False

    def _advance_sales_nav_results(self, driver):
        """Reveal more Sales Navigator results via scroll or pagination."""
        try:
            driver.execute_script("window.scrollBy(0, Math.max(window.innerHeight * 0.8, 600));")
            time.sleep(2)
        except Exception:
            pass
        return True

    def _connect_with_sales_nav_result(self, driver, menu_button, lead_name):
        """Open a Sales Nav row menu, click Connect, and send the invitation."""
        try:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", menu_button)
            time.sleep(1)

            if not self.safe_click(driver, menu_button):
                driver.execute_script("arguments[0].click();", menu_button)

            time.sleep(1.5)
            if not self._click_sales_nav_connect_action(driver):
                logger.info(f"Skipping {lead_name}: no Connect action available in Sales Nav menu.")
                self._dismiss_sales_nav_overlays(driver)
                return "skipped"

            time.sleep(2)
            if self.handle_connect_modal(driver):
                logger.info(f"✅ Sales Nav invitation sent to {lead_name}")
                return "successful"

            logger.info(f"Skipping {lead_name}: connect modal did not complete.")
            self._dismiss_sales_nav_overlays(driver)
            return "failed"
        except Exception as e:
            logger.error(f"Error connecting with {lead_name}: {e}")
            self._dismiss_sales_nav_overlays(driver)
            return "failed"

    def send_connection_request_with_note(self, driver, message, name):
        """Send connection request with personalized note"""
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import TimeoutException
        
        logger.info(f"🤝 Attempting to send connection request with note to {name}...")

        # Find Connect button
        connect_button_selectors = [
            ("xpath", "//span[normalize-space()='Connect']"),
            ("xpath", "//*[contains(@class, 'artdeco-button') and .//span[normalize-space()='Connect']]"),
            ("xpath", "//span[normalize-space()=\'Connect\']"),
            ("xpath", "//*[contains(@class, \'artdeco-button\') and .//span[normalize-space()=\'Connect\']]"),
            ("css", "button.artdeco-button.artdeco-button--2.artdeco-button--primary[aria-label*='Connect']"),
            ("xpath", "//button[contains(@aria-label, 'Connect') and contains(@class, 'artdeco-button--primary')]"),
            ("xpath", "//button[.//span[text()='Connect']]"),
            ("css", "button[aria-label*='Connect'][class*='artdeco-button']")
        ]

        connect_button = self.find_element_safe(driver, connect_button_selectors, timeout=8)
        if not connect_button:
            logger.error("❌ Connect button not found")
            return False

        # Click Connect button
        if not self.safe_click(driver, connect_button):
            logger.error("❌ Failed to click Connect button")
            return False

        logger.info("✅ Connect button clicked")
        self.human_delay(2, 3)

        try:
            # Look for "Add a note" button
            add_note_selectors = [
                ("xpath", "//button[.//span[normalize-space()='Add a note']]"),
                ("xpath", "//button[.//span[normalize-space()=\'Add a note\']]"),
                ("css", "button[aria-label='Add a note']"),
                ("xpath", "//button[@aria-label='Add a note']"),
                ("xpath", "//button[.//span[text()='Add a note']]"),
                ("css", "button[aria-label*='Add a note']"),
                ("xpath", "//button[contains(text(), 'Add a note')]")
            ]

            add_note_button = self.find_element_safe(driver, add_note_selectors, timeout=8)
            if not add_note_button:
                logger.info("❌ Add a note button not found - cannot send with note")
                return False

            # Click "Add a note"
            if not self.safe_click(driver, add_note_button):
                logger.error("❌ Failed to click Add a note button")
                return False

            logger.info("✅ Add a note clicked")
            self.human_delay(1, 2)

            # Find and fill note text area
            note_area_selectors = [
                ("css", "textarea[name='message']"),
                ("css", "#custom-message"),
                ("css", "textarea[aria-label*='note']"),
                ("css", ".connect-note-form textarea"),
                ("xpath", "//textarea[@name='message']")
            ]

            note_area = self.find_element_safe(driver, note_area_selectors, timeout=8)
            if not note_area:
                logger.error("❌ Could not find note text area")
                return False

            # Type the personalized message
            self.type_like_human(note_area, message)
            logger.info("✅ Personalized note added successfully")
            self.human_delay(1, 2)

            # Find and click Send button
            send_request_selectors = [
                ("css", "button[aria-label='Send now']"),
                ("xpath", "//button[@aria-label='Send now']"),
                ("css", "button[aria-label*='Send invitation']"),
                ("xpath", "//button[contains(@aria-label, 'Send')]"),
                ("xpath", "//button[.//span[text()='Send']]")
            ]

            send_button = self.find_element_safe(driver, send_request_selectors, timeout=10)
            if send_button and self.safe_click(driver, send_button):
                logger.info(f"✅ Connection request with note sent successfully to {name}!")
                self.human_delay(2, 4)
                return True
            else:
                logger.error("❌ Could not find or click send button")
                return False

        except Exception as e:
            logger.error(f"❌ Error sending connection request with note: {e}")
            return False

    def send_connection_request_without_note(self, driver, name):
        """Send connection request without personalized note"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        logger.info(f"🤝 Attempting to send connection request without note to {name}...")

        connect_button_selectors = [
            ("xpath", "//span[normalize-space()='Connect']"),
            ("xpath", "//*[contains(@class, 'artdeco-button') and .//span[normalize-space()='Connect']]"),
            ("xpath", "//span[normalize-space()=\'Connect\']"),
            ("xpath", "//*[contains(@class, \'artdeco-button\') and .//span[normalize-space()=\'Connect\']]"),
            ("css", "button.artdeco-button.artdeco-button--2.artdeco-button--primary[aria-label*='Connect']"),
            ("xpath", "//button[contains(@aria-label, 'Connect') and contains(@class, 'artdeco-button--primary')]"),
            ("xpath", "//button[.//span[text()='Connect']]"),
            ("css", "button[aria-label*='Connect'][class*='artdeco-button']"),
        ]

        connect_button = self.find_element_safe(driver, connect_button_selectors, timeout=8)
        if not connect_button:
            logger.error("❌ Connect button not found")
            return False

        if not self.safe_click(driver, connect_button):
            logger.error("❌ Failed to click Connect button")
            return False

        logger.info("✅ Connect button clicked")

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    "div[data-test-modal-id='send-invite-modal'], .send-invite, #artdeco-modal-outlet .artdeco-modal"
                ))
            )
            if self.click_send_without_note_button(driver, timeout=10):
                logger.info(f"✅ Connection request without note sent successfully to {name}!")
                self.human_delay(2, 4)
                return True

            logger.error("❌ Could not find or click send button")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending connection request without note: {e}")
            return False

    def send_direct_message(self, driver, message, name):
        """Send direct message to LinkedIn connection"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        from selenium.webdriver.common.action_chains import ActionChains
        
        logger.info(f"🔍 Attempting to locate Message button for {name}...")

        # --- UPDATED SELECTOR LIST ---
        # Prioritizing the new 'pvs-sticky-header-profile-actions__action' class you found
        message_button_selectors = [
            ("xpath", "//a[contains(@href, 'messaging/compose')]"),
            ("xpath", "//a[.//span[normalize-space()='Message']]"),
            ("xpath", "//span[normalize-space()='Message']"),
            ("xpath", "//a[contains(@href, \'messaging/compose\')]"),
            ("xpath", "//a[.//span[normalize-space()=\'Message\']]"),
            ("xpath", "//span[normalize-space()=\'Message\']"),
            ("css", "button.pvs-sticky-header-profile-actions__action[aria-label*='Message']"),
            ("xpath", "//button[contains(@class, 'pvs-sticky-header-profile-actions__action') and contains(@aria-label, 'Message')]"),
            ("css", "button.artdeco-button--primary[aria-label*='Message']"),
            ("xpath", "//button[contains(@aria-label, 'Message') and contains(@class, 'artdeco-button--primary')]"),
            ("css", "button[data-control-name*='message']"),
            ("css", "button[aria-label*='Message']"),
            # Removed selectors based on text 'Message' as they are unreliable
        ]
        # --- END OF UPDATE ---

        msg_btn = None
        for selector_type, selector in message_button_selectors:
            try:
                if selector_type == "xpath":
                    msg_btn = WebDriverWait(driver, 6).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    msg_btn = WebDriverWait(driver, 6).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                if msg_btn and msg_btn.is_displayed() and msg_btn.is_enabled():
                    logger.info(f"✅ Message button found using: {selector}")
                    break
                else:
                    msg_btn = None
            except (TimeoutException, NoSuchElementException):
                continue

        if not msg_btn:
            logger.info("❌ No Message button found - user may not be a 1st degree connection")
            return False

        # Click message button
        try:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", msg_btn)
            self.human_delay(1, 2)

            if not self.safe_click(driver, msg_btn):
                ActionChains(driver).move_to_element(msg_btn).click().perform()

            logger.info("✅ Message button clicked successfully")
            self.human_delay(2, 3)
        except Exception as e:
            logger.error(f"❌ Failed to click Message button: {e}")
            return False

        # Enhanced message composition
        compose_selectors = [
            ("css", ".msg-form__contenteditable"),
            ("css", "[data-test-id='message-composer-input']"),
            ("css", "div[role='textbox'][contenteditable='true']"),
            ("xpath", "//textarea[@aria-label='Write a message…']"),
            ("css", "div[contenteditable='true'][role='textbox']")
        ]

        compose_box = None
        for selector_type, selector in compose_selectors:
            try:
                if selector_type == "xpath":
                    compose_box = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    compose_box = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                if compose_box:
                    logger.info(f"✅ Message compose area found using: {selector}")
                    break
            except (TimeoutException, NoSuchElementException):
                continue

        if not compose_box:
            logger.error("❌ Could not find message compose area")
            return False

        # Type the message
        try:
            compose_box.click()
            self.human_delay(0.5, 1)
            compose_box.clear()

            # Type message character by character
            for char in message:
                compose_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

            logger.info("✅ Message typed successfully")
            self.human_delay(1, 2)
        except Exception as e:
            logger.error(f"❌ Failed to type message: {e}")
            return False

        # Send the message
        send_button_selectors = [
            ("css", "button.msg-form__send-button[type='submit']"),
            ("css", "button[data-control-name='send_message']"),
            ("xpath", "//button[@type='submit' and .//span[text()='Send']]"),
            ("xpath", "//button[contains(@aria-label, 'Send') and @type='submit']"),
            ("css", "button[aria-label*='Send message']")
        ]

        send_btn = None
        for selector_type, selector in send_button_selectors:
            try:
                if selector_type == "xpath":
                    send_btn = WebDriverWait(driver, 6).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    send_btn = WebDriverWait(driver, 6).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                if send_btn and send_btn.is_enabled():
                    logger.info(f"✅ Send button found using: {selector}")
                    break
            except (TimeoutException, NoSuchElementException):
                continue

        if not send_btn or not send_btn.is_enabled():
            logger.error("❌ Send button not found or not enabled")
            return False

        try:
            if self.safe_click(driver, send_btn):
                logger.info(f"🎉 Message sent successfully to {name}!")
                self.human_delay(1, 2)
                return True
            else:
                logger.error("❌ Failed to click Send button")
                return False
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False

    def send_message_with_priority(self, driver, message, name, company):
        """Send message using priority order: connection with note -> connection without note -> direct message"""
        logger.info(f"🚀 Starting outreach process for {name} at {company}")

        try:
            # Wait for page to load completely
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.common.exceptions import TimeoutException
            
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            self.human_delay(2, 4)
        except TimeoutException:
            logger.warning("⚠️ Page load timeout - proceeding anyway")

        # Extract profile data for better personalization
        profile_data = self.extract_profile_data(driver)

        # PRIORITY 1: Try connection request with note
        logger.info("🎯 Priority 1: Attempting connection request with personalized note...")
        if self.send_connection_request_with_note(driver, message, name):
            logger.info(f"✅ Successfully sent connection request with note to {name}")
            return True

        # PRIORITY 2: Try connection request without note
        logger.info("🎯 Priority 2: Attempting connection request without note...")
        if self.send_connection_request_without_note(driver, name):
            logger.info(f"✅ Successfully sent connection request without note to {name}")
            return True

        # PRIORITY 3: Try direct message
        logger.info("🎯 Priority 3: Attempting direct message...")
        if self.send_direct_message(driver, message, name):
            logger.info(f"✅ Successfully sent direct message to {name}")
            return True

        # If all methods fail
        logger.error(f"❌ All outreach methods failed for {name}")
        return False
    def scrape_sales_navigator_search(self, driver, search_url, max_profiles):
        """Scrapes profiles from a Sales Navigator search URL."""
        profiles = []
        collected_urls = set()
        
        try:
            logger.info(f"Navigating to Sales Navigator URL: {search_url}")
            driver.get(search_url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".artdeco-list__item"))
            )
            time.sleep(3)

            page_count = 1
            while len(profiles) < max_profiles:
                logger.info(f"Scraping page {page_count}... (Collected {len(profiles)}/{max_profiles})")
                
                # Scroll to bottom to load all profiles on the page
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))

                profile_elements = driver.find_elements(By.CSS_SELECTOR, "li.artdeco-list__item")
                
                if not profile_elements:
                    logger.info("No more profile elements found on page. Ending collection.")
                    break

                for element in profile_elements:
                    if len(profiles) >= max_profiles:
                        break
                    
                    try:
                        # Extract profile URL and Name
                        link_element = element.find_element(By.CSS_SELECTOR, "a.ember-view")
                        profile_url = link_element.get_attribute('href')
                        name = element.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__title").text.strip()
                        
                        # Skip if already collected or not a valid profile link
                        if not profile_url or "/sales/lead/" not in profile_url or profile_url in collected_urls:
                            continue

                        # Extract Headline and Company
                        headline_element = element.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle")
                        headline_parts = [e.text.strip() for e in headline_element.find_elements(By.TAG_NAME, 'span')]
                        headline = headline_parts[0] if headline_parts else "N/A"
                        company = headline_parts[1] if len(headline_parts) > 1 else "N/A"
                        
                        profiles.append({
                            "name": name,
                            "profile_url": profile_url,
                            "headline": headline,
                            "company": company,
                        })
                        collected_urls.add(profile_url)

                    except NoSuchElementException:
                        continue # Skip elements that are not profiles (e.g., ads, footers)
                    except Exception as e:
                        logger.warning(f"Could not parse a profile element: {e}")

                # Go to next page
                if len(profiles) < max_profiles:
                    try:
                        next_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next']")
                        if not next_button.is_enabled():
                            logger.info("Next button is disabled. Reached the end of search results.")
                            break
                        
                        self.safe_click(driver, next_button)
                        WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".artdeco-list__item"))
                        )
                        time.sleep(random.uniform(3, 5))
                        page_count += 1
                    except NoSuchElementException:
                        logger.info("No 'Next' button found. Reached the end of search results.")
                        break
                else:
                    break

        except TimeoutException:
            logger.error("Timed out waiting for Sales Navigator page to load.")
        except Exception as e:
            logger.error(f"An error occurred during scraping: {e}")
            
        return profiles
    

    def fetch_sales_nav_lists(self, task_id):
        """
        Navigates to Sales Nav, opens Saved Searches > Leads, and scrapes list details.
        """
        self.browser_lock.acquire()
        lists = []
        self.active_sales_nav_fetches[task_id].update({
            "status": "running",
            "stop_requested": False
        })
        try:
            logger.info(f"🔑 Browser lock acquired for fetching Sales Nav lists {task_id}")
            driver = self.get_shared_driver()
            if not driver:
                raise Exception("Failed to get browser")

            # 1. Go to Sales Nav Home
            logger.info("Navigating to Sales Navigator Home...")
            driver.get("https://www.linkedin.com/sales/home")
            time.sleep(4)
            if "premium/switcher" in driver.current_url:
                raise Exception("sales_navigator_required")
            if self.active_sales_nav_fetches[task_id].get("stop_requested"):
                raise RuntimeError("Fetch stopped by user")

            # 2. Open Saved Searches
            # User provided: data-x--link--saved-searches
            logger.info("Opening Saved Searches panel...")
            saved_searches_btn = self.find_element_safe(driver, [
                ("css", "button[data-x--link--saved-searches]"),
                ("xpath", "//button[contains(@class, '_button_ps32ck') and contains(text(), 'Saved searches')]")
            ])
            
            if not saved_searches_btn:
                # If we're supposedly on sales nav but can't find core UI elements,
                # the user probably doesn't have an active Sales Navigator subscription.
                raise Exception("sales_navigator_required")
            
            self.safe_click(driver, saved_searches_btn)
            time.sleep(2)
            if self.active_sales_nav_fetches[task_id].get("stop_requested"):
                raise RuntimeError("Fetch stopped by user")

            # 3. Click "Leads" Tab
            # User provided: aria-label="Lead- View all lead saved searches"
            logger.info("Switching to 'Lead' lists tab...")
            leads_tab = self.find_element_safe(driver, [
                ("css", "button[aria-label*='Lead- View all lead saved searches']"),
                ("xpath", "//button[contains(text(), 'Lead')]")
            ])
            
            if leads_tab:
                self.safe_click(driver, leads_tab)
                time.sleep(2)
                if self.active_sales_nav_fetches[task_id].get("stop_requested"):
                    raise RuntimeError("Fetch stopped by user")

            # 4. Scrape List Titles and URLs
            # User provided list html: class containing _panel-link_yma0zx
            logger.info("Scraping list data...")
            selectors = [
                "a._panel-link_yma0zx[href*='savedSearchId=']",
                "a[href*='/sales/search/people?savedSearchId=']",
                "a[aria-label*='Go to search results for']",
            ]
            lists_by_url = {}
            stable_rounds = 0
            previous_count = -1

            for _ in range(12):
                if self.active_sales_nav_fetches[task_id].get("stop_requested"):
                    raise RuntimeError("Fetch stopped by user")

                found_links = []
                for selector in selectors:
                    try:
                        found_links.extend(driver.find_elements(By.CSS_SELECTOR, selector))
                    except Exception:
                        continue

                for el in found_links:
                    try:
                        url = self._normalize_linkedin_url(el.get_attribute("href"))
                        title = self._extract_sales_nav_list_name(el)
                        if not url or not title:
                            continue
                        lists_by_url[url] = {"name": title, "url": url}
                    except Exception:
                        continue

                current_count = len(lists_by_url)
                if current_count == previous_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    previous_count = current_count

                if stable_rounds >= 2:
                    break

                self._scroll_sales_nav_saved_lists_panel(driver, found_links[-1] if found_links else None)
                time.sleep(1.5)

            lists = list(lists_by_url.values())
            
            logger.info(f"✅ Found {len(lists)} Sales Nav lists.")

            self.active_sales_nav_fetches[task_id]["status"] = "completed"

            # Report results
            self.report_task_result({
                "task_id": task_id,
                "type": "fetch_sales_nav_lists",
                "success": True,
                "payload": {"lists": lists}
            })

        except Exception as e:
            logger.error(f"❌ Error fetching Sales Nav lists: {e}")
            self.report_task_result({
                "task_id": task_id,
                "type": "fetch_sales_nav_lists",
                "success": False,
                "error": str(e),
                "payload": {"lists": [], "stopped": "stopped by user" in str(e).lower()}
            })
        finally:
            if task_id in self.active_sales_nav_fetches:
                del self.active_sales_nav_fetches[task_id]
            self.browser_lock.release()

    def run_sales_nav_outreach_campaign(self, task_id, campaign_id, user_config, campaign_params):
        """
        Iterates a specific Sales Nav saved search and sends connection requests.
        """
        self.browser_lock.acquire()
        try:
            list_url = campaign_params.get('list_url')
            max_contacts = int(campaign_params.get('max_contacts', 10))
            
            # Initialize campaign state in self.active_campaigns
            self.active_campaigns[campaign_id] = {
                'task_id': task_id,
                'status': 'running',
                'progress': 0,
                'total': max_contacts,
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'already_messaged': 0,
                'stop_requested': False,
                'awaiting_confirmation': False,
                'current_contact_preview': None,
                'contacts': [],
                'start_time': datetime.now().isoformat()
            }

            driver = self.get_shared_driver()
            
            logger.info(f"🚀 Starting Sales Nav Outreach on list: {list_url}")
            driver.get(list_url)
            time.sleep(5)
            if "premium/switcher" in driver.current_url:
                raise Exception("sales_navigator_required")

            processed_count = 0
            processed_leads = set()
            exhausted_rounds = 0

            while processed_count < max_contacts:
                if self.active_campaigns[campaign_id].get('stop_requested'):
                    break

                try:
                    candidates = self._get_sales_nav_result_candidates(driver)
                    candidate = next(
                        (item for item in candidates if item['name'] not in processed_leads),
                        None
                    )

                    if not candidate:
                        exhausted_rounds += 1
                        if exhausted_rounds == 2 and self.go_to_next_page(driver):
                            time.sleep(3)
                            continue
                        if exhausted_rounds >= 3:
                            logger.info("Reached end of visible Sales Nav results.")
                            break
                        self._advance_sales_nav_results(driver)
                        continue

                    exhausted_rounds = 0
                    lead_name = candidate['name']
                    processed_leads.add(lead_name)
                    logger.info(f"👉 Processing Sales Nav lead: {lead_name}")

                    outcome = self._connect_with_sales_nav_result(
                        driver,
                        candidate['button'],
                        lead_name
                    )
                    self.active_campaigns[campaign_id][outcome] += 1
                    self.active_campaigns[campaign_id]['contacts'].append({
                        'Name': lead_name,
                        'Company': '',
                        'Role': '',
                        'LinkedIn_profile': list_url,
                        'status': outcome
                    })
                except Exception as e:
                    logger.error(f"Error processing row {processed_count}: {e}")
                    self.active_campaigns[campaign_id]['failed'] += 1

                processed_count += 1
                self.active_campaigns[campaign_id]['progress'] = processed_count
                self.report_progress_to_dashboard(campaign_id, task_id=task_id, task_type='sales_nav_outreach_campaign')
                time.sleep(random.uniform(2, 4))

            self.active_campaigns[campaign_id]['status'] = 'stopped' if self.active_campaigns[campaign_id].get('stop_requested') else 'completed'
            self.active_campaigns[campaign_id]['end_time'] = datetime.now().isoformat()
            self.report_progress_to_dashboard(
                campaign_id,
                final=True,
                task_id=task_id,
                task_type='sales_nav_outreach_campaign'
            )

        except Exception as e:
            logger.error(f"Critical error in Sales Nav campaign: {e}")
            self.active_campaigns[campaign_id]['status'] = 'failed'
            self.active_campaigns[campaign_id]['error'] = str(e)
            self.report_progress_to_dashboard(
                campaign_id,
                final=True,
                task_id=task_id,
                task_type='sales_nav_outreach_campaign'
            )
        finally:
            self.browser_lock.release()

    def _parse_keyword_search_list(self, raw_value):
        """Normalize comma/newline separated filter input into a clean list."""
        if not raw_value:
            return []
        if isinstance(raw_value, (list, tuple, set)):
            parts = raw_value
        else:
            parts = re.split(r'[\r\n,;]+', str(raw_value))
        return [part.strip() for part in parts if part and str(part).strip()]

    def normalize_keyword_search_filters(self, search_filters=None):
        """Return only populated keyword-search filters in a predictable shape."""
        search_filters = search_filters or {}
        normalized = {
            "location": str(search_filters.get("location", "")).strip(),
            "connection_degrees": self._parse_keyword_search_list(search_filters.get("connection_degrees", [])),
            "industries": self._parse_keyword_search_list(search_filters.get("industries", search_filters.get("industry", []))),
            "current_companies": self._parse_keyword_search_list(search_filters.get("current_companies", [])),
            "past_companies": self._parse_keyword_search_list(search_filters.get("past_companies", [])),
            "schools": self._parse_keyword_search_list(search_filters.get("schools", [])),
            "profile_languages": self._parse_keyword_search_list(search_filters.get("profile_languages", [])),
            "service_categories": self._parse_keyword_search_list(search_filters.get("service_categories", [])),
            "filter_keywords": str(search_filters.get("filter_keywords", search_filters.get("keywords_filter", ""))).strip(),
            "first_name": str(search_filters.get("first_name", "")).strip(),
            "last_name": str(search_filters.get("last_name", "")).strip(),
            "title": str(search_filters.get("title", "")).strip(),
            "company": str(search_filters.get("company", "")).strip(),
            "school": str(search_filters.get("school", "")).strip(),
        }
        return {
            key: value for key, value in normalized.items()
            if value not in ("", None, [])
        }

    def _normalize_location_lookup_key(self, location_value):
        return re.sub(r"[^a-z0-9]+", " ", str(location_value).lower()).strip()

    def _find_broader_geo_urn(self, raw_location):
        normalized_key = self._normalize_location_lookup_key(raw_location)
        if not normalized_key:
            return None, None

        # Try suffix candidates so "Paris, France" can fall back to "France"
        # and "Toronto Ontario Canada" can still resolve to "Canada".
        comma_segments = [
            self._normalize_location_lookup_key(part)
            for part in re.split(r"[|,/]+", str(raw_location))
            if self._normalize_location_lookup_key(part)
        ]
        candidates = []

        if comma_segments:
            for index in range(len(comma_segments)):
                candidate = " ".join(comma_segments[index:]).strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

        token_segments = normalized_key.split()
        for index in range(len(token_segments)):
            candidate = " ".join(token_segments[index:]).strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        for candidate in candidates:
            geo_urn = LINKEDIN_GEO_URN_BY_LOCATION.get(candidate)
            if geo_urn:
                return geo_urn, candidate

        return None, None

    def _resolve_geo_urns(self, location_value):
        resolved = []
        unresolved = []

        for location in self._parse_keyword_search_list(location_value):
            raw_location = str(location).strip()
            if not raw_location:
                continue

            urn_match = re.search(r"(\d{6,})", raw_location)
            if urn_match:
                resolved.append(urn_match.group(1))
                continue

            lookup_key = self._normalize_location_lookup_key(raw_location)
            geo_urn = LINKEDIN_GEO_URN_BY_LOCATION.get(lookup_key)
            if geo_urn:
                resolved.append(geo_urn)
            else:
                fallback_geo_urn, matched_candidate = self._find_broader_geo_urn(raw_location)
                if fallback_geo_urn:
                    logger.info(
                        f"Using broader geo fallback '{matched_candidate}' for location '{raw_location}'."
                    )
                    resolved.append(fallback_geo_urn)
                else:
                    unresolved.append(raw_location)

        deduped = []
        seen = set()
        for value in resolved:
            if value not in seen:
                deduped.append(value)
                seen.add(value)

        return deduped, unresolved

    def _resolve_profile_language_codes(self, language_value):
        resolved = []
        unresolved = []

        for language in self._parse_keyword_search_list(language_value):
            raw_language = str(language).strip()
            if not raw_language:
                continue

            lookup_key = self._normalize_location_lookup_key(raw_language)
            language_code = LINKEDIN_PROFILE_LANGUAGE_CODE_BY_NAME.get(lookup_key)
            if language_code:
                resolved.append(language_code)
            else:
                unresolved.append(raw_language)

        deduped = []
        seen = set()
        for value in resolved:
            if value not in seen:
                deduped.append(value)
                seen.add(value)

        return deduped, unresolved

    def _resolve_numeric_filter_values(self, raw_values):
        resolved = []
        unresolved = []

        for raw_value in self._parse_keyword_search_list(raw_values):
            cleaned_value = str(raw_value).strip()
            if not cleaned_value:
                continue

            matched_ids = re.findall(r"(?<!\d)(\d{2,})(?!\d)", cleaned_value)
            if matched_ids:
                for matched_id in matched_ids:
                    if matched_id not in resolved:
                        resolved.append(matched_id)
                continue

            unresolved.append(cleaned_value)

        return resolved, unresolved

    def _merge_keyword_search_terms(self, keywords, normalized_filters, fallback_terms=None):
        terms = [str(keywords).strip()]

        if normalized_filters.get("filter_keywords"):
            terms.append(normalized_filters["filter_keywords"])

        terms.extend(fallback_terms or [])

        merged_terms = []
        seen = set()
        for term in terms:
            cleaned = str(term).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            merged_terms.append(cleaned)
            seen.add(key)

        return " ".join(merged_terms)

    def build_people_search_url(self, keywords, search_filters=None):
        normalized_filters = self.normalize_keyword_search_filters(search_filters)
        fallback_keyword_terms = []

        params = {
            "origin": "FACETED_SEARCH" if normalized_filters else "GLOBAL_SEARCH_HEADER",
        }

        network_codes = []
        for degree in normalized_filters.get("connection_degrees", []):
            code = LINKEDIN_NETWORK_CODE_BY_DEGREE.get(str(degree).strip().lower().replace(" ", ""), None)
            if code and code not in network_codes:
                network_codes.append(code)

        if network_codes:
            params["network"] = json.dumps(network_codes, separators=(",", ":"))

        geo_urns, unresolved_locations = self._resolve_geo_urns(normalized_filters.get("location", ""))
        if geo_urns:
            params["geoUrn"] = json.dumps(geo_urns, separators=(",", ":"))

        if unresolved_locations:
            logger.warning(
                f"⚠️ No geoUrn mapping found for locations {unresolved_locations}. "
                "They were not added as direct LinkedIn location filters."
            )

        profile_language_codes, unresolved_languages = self._resolve_profile_language_codes(
            normalized_filters.get("profile_languages", [])
        )
        if profile_language_codes:
            params["profileLanguage"] = json.dumps(profile_language_codes, separators=(",", ":"))

        if unresolved_languages:
            logger.warning(
                f"⚠️ No profileLanguage mapping found for languages {unresolved_languages}. "
                "They were not added as direct LinkedIn language filters."
            )
            fallback_keyword_terms.extend(unresolved_languages)

        list_filter_param_map = {
            "current_companies": "currentCompany",
            "industries": "industry",
            "schools": "schoolFilter",
            "past_companies": "pastCompany",
            "service_categories": "serviceCategory",
        }
        for filter_name, param_name in list_filter_param_map.items():
            resolved_ids, unresolved_values = self._resolve_numeric_filter_values(
                normalized_filters.get(filter_name, [])
            )
            if resolved_ids:
                params[param_name] = json.dumps(resolved_ids, separators=(",", ":"))
            if unresolved_values:
                fallback_keyword_terms.extend(unresolved_values)
                logger.info(
                    f"ℹ️ Using keyword fallback for unresolved {filter_name}: {unresolved_values}"
                )

        direct_param_map = {
            "first_name": "firstName",
            "last_name": "lastName",
            "title": "title",
            "company": "company",
            "school": "school",
        }
        for filter_name, param_name in direct_param_map.items():
            if normalized_filters.get(filter_name):
                params[param_name] = normalized_filters[filter_name]

        params["keywords"] = self._merge_keyword_search_terms(
            keywords,
            normalized_filters,
            fallback_terms=fallback_keyword_terms
        )

        return f"https://www.linkedin.com/search/results/people/?{urlencode(params, quote_via=quote)}"

    def _find_filter_input_by_labels(self, driver, dialog, labels):
        """Find a visible input/select/textarea whose nearby label matches."""
        if isinstance(labels, str):
            labels = [labels]

        script = """
            const root = arguments[0];
            const labels = arguments[1].map(label =>
                (label || '').replace(/\\s+/g, ' ').trim().toLowerCase()
            ).filter(Boolean);

            function normalize(value) {
                return (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            }

            function isVisible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return style &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    el.offsetParent !== null;
            }

            function labelTextFor(control) {
                const bits = [];
                if (control.labels) {
                    bits.push(...Array.from(control.labels).map(node => node.textContent || ''));
                }

                const labelledBy = (control.getAttribute('aria-labelledby') || '').trim();
                if (labelledBy) {
                    for (const id of labelledBy.split(/\\s+/)) {
                        const node = root.ownerDocument.getElementById(id);
                        if (node) bits.push(node.textContent || '');
                    }
                }

                for (const attr of ['aria-label', 'placeholder', 'name', 'id']) {
                    bits.push(control.getAttribute(attr) || '');
                }

                let node = control.parentElement;
                for (let depth = 0; depth < 4 && node; depth += 1, node = node.parentElement) {
                    bits.push(node.textContent || '');
                }

                return bits.map(normalize).filter(Boolean);
            }

            let best = null;
            let bestScore = 0;
            const controls = Array.from(root.querySelectorAll('input, textarea, select, [contenteditable="true"]'));

            for (const control of controls) {
                if (!isVisible(control)) continue;

                const texts = labelTextFor(control);
                let score = 0;
                for (const text of texts) {
                    for (const wanted of labels) {
                        if (!wanted) continue;
                        if (text === wanted) {
                            score = Math.max(score, 100);
                        } else if (text.includes(wanted)) {
                            score = Math.max(score, 80);
                        } else if (wanted.length > 4 && wanted.includes(text)) {
                            score = Math.max(score, 60);
                        }
                    }
                }

                if (score > bestScore) {
                    best = control;
                    bestScore = score;
                }
            }

            return bestScore >= 60 ? best : null;
        """
        try:
            return driver.execute_script(script, dialog, labels)
        except Exception as exc:
            logger.debug(f"Could not locate filter input for {labels}: {exc}")
            return None

    def _set_filter_input_value(self, driver, element, value, prefer_selection=False):
        """Populate a filter input and optionally confirm an autosuggest selection."""
        from selenium.webdriver.common.keys import Keys

        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        except Exception:
            pass

        try:
            element.click()
        except Exception:
            pass

        try:
            tag_name = (element.tag_name or "").lower()
            is_contenteditable = (element.get_attribute("contenteditable") or "").lower() == "true"

            if is_contenteditable:
                driver.execute_script(
                    "arguments[0].textContent=''; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
                    element
                )
            elif tag_name in {"input", "textarea"}:
                element.send_keys(Keys.CONTROL, "a")
                element.send_keys(Keys.DELETE)
            else:
                driver.execute_script(
                    "arguments[0].value=''; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
                    element
                )
        except Exception:
            logger.debug("Primary input clear failed, falling back to JavaScript clear.")
            try:
                driver.execute_script(
                    """
                    if (arguments[0].isContentEditable) {
                        arguments[0].textContent = '';
                    } else {
                        arguments[0].value = '';
                    }
                    arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
                    arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
                    """,
                    element
                )
            except Exception:
                pass

        try:
            element.send_keys(value)
        except Exception:
            driver.execute_script(
                """
                if (arguments[0].isContentEditable) {
                    arguments[0].textContent = arguments[1];
                } else {
                    arguments[0].value = arguments[1];
                }
                arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
                arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
                """,
                element,
                value
            )

        self.human_delay(0.5, 1.0)

        if prefer_selection:
            for keys in ((Keys.ARROW_DOWN, Keys.ENTER), (Keys.ENTER,), (Keys.TAB,)):
                try:
                    element.send_keys(*keys)
                    self.human_delay(0.3, 0.7)
                    break
                except Exception:
                    continue

    def _find_filter_option(self, driver, dialog, option_labels):
        """Find a clickable option in the filter modal by visible text."""
        if isinstance(option_labels, str):
            option_labels = [option_labels]

        script = """
            const root = arguments[0];
            const labels = arguments[1].map(label =>
                (label || '').replace(/\\s+/g, ' ').trim().toLowerCase()
            ).filter(Boolean);

            function normalize(value) {
                return (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            }

            function isVisible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return style &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    el.offsetParent !== null;
            }

            const selectors = [
                'label',
                'button',
                '[role="checkbox"]',
                '[role="radio"]',
                '.artdeco-pill',
                '.search-reusables__filter-pill-button'
            ];

            for (const selector of selectors) {
                const nodes = Array.from(root.querySelectorAll(selector));
                for (const node of nodes) {
                    if (!isVisible(node)) continue;
                    const text = normalize(node.innerText || node.textContent || '');
                    if (!text) continue;
                    if (!labels.some(label => text === label || text.includes(label))) continue;
                    return node;
                }
            }

            return null;
        """
        try:
            return driver.execute_script(script, dialog, option_labels)
        except Exception as exc:
            logger.debug(f"Could not locate filter option {option_labels}: {exc}")
            return None

    def _is_filter_option_selected(self, driver, option):
        try:
            return bool(driver.execute_script(
                """
                const option = arguments[0];
                const input = option.matches('input') ? option : option.querySelector('input[type="checkbox"], input[type="radio"]');
                if (input) return !!input.checked;

                const ariaChecked = option.getAttribute('aria-checked');
                if (ariaChecked) return ariaChecked === 'true';

                const ariaPressed = option.getAttribute('aria-pressed');
                if (ariaPressed) return ariaPressed === 'true';

                return option.classList.contains('artdeco-pill--selected') ||
                    option.classList.contains('selected') ||
                    option.classList.contains('artdeco-toggle__button--selected');
                """,
                option
            ))
        except Exception:
            return False

    def _apply_people_search_filters(self, driver, search_filters):
        """Apply optional LinkedIn people-search filters from the all-filters modal."""
        normalized_filters = self.normalize_keyword_search_filters(search_filters)
        if not normalized_filters:
            return {}

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        logger.info(f"🔧 Applying keyword search filters: {normalized_filters}")

        try:
            filter_button = None
            filter_selectors = [
                (By.XPATH, "//button[contains(normalize-space(.), 'All filters')]"),
                (By.XPATH, "//button[contains(@aria-label, 'All filters')]"),
                (By.CSS_SELECTOR, "button.search-reusables__all-filters-pill-button"),
            ]

            for by, selector in filter_selectors:
                try:
                    filter_button = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if filter_button:
                        break
                except Exception:
                    continue

            if not filter_button:
                logger.warning("⚠️ Could not find the LinkedIn All filters button. Continuing without optional filters.")
                return normalized_filters

            self.safe_click(driver, filter_button)
            dialog = self._find_active_connect_dialog(driver, timeout=8)
            if not dialog:
                logger.warning("⚠️ LinkedIn filter dialog did not open. Continuing without optional filters.")
                return normalized_filters

            field_configs = [
                ("location", ["Locations", "Location"], "multi"),
                ("industries", ["Industry", "Industries"], "multi"),
                ("current_companies", ["Current company", "Current companies"], "multi"),
                ("past_companies", ["Past company", "Past companies"], "multi"),
                ("schools", ["Schools", "School"], "multi"),
                ("profile_languages", ["Profile language", "Profile languages", "Language"], "multi"),
                ("service_categories", ["Service categories", "Service category", "Services"], "multi"),
                ("filter_keywords", ["Keywords", "Keyword"], "single"),
                ("first_name", ["First name"], "single"),
                ("last_name", ["Last name"], "single"),
                ("title", ["Title"], "single"),
                ("company", ["Company"], "single"),
                ("school", ["School"], "single"),
            ]

            for degree in normalized_filters.get("connection_degrees", []):
                option = self._find_filter_option(driver, dialog, [degree, degree.replace("+", " and beyond")])
                if not option:
                    logger.warning(f"⚠️ Could not find degree filter option '{degree}'.")
                    continue
                if not self._is_filter_option_selected(driver, option):
                    self.safe_click(driver, option)
                    self.human_delay(0.3, 0.7)

            for field_name, labels, field_mode in field_configs:
                field_value = normalized_filters.get(field_name)
                if not field_value:
                    continue

                values = field_value if isinstance(field_value, list) else [field_value]
                input_found = False

                for value in values:
                    input_element = self._find_filter_input_by_labels(driver, dialog, labels)
                    if not input_element:
                        if not input_found:
                            logger.warning(f"⚠️ Could not find filter field for {field_name}.")
                        break

                    input_found = True
                    self._set_filter_input_value(
                        driver,
                        input_element,
                        value,
                        prefer_selection=(field_mode == "multi")
                    )

            submit_button = None
            submit_selectors = [
                (By.XPATH, "//button[contains(normalize-space(.), 'Show results')]"),
                (By.XPATH, "//button[contains(@aria-label, 'Show results')]"),
                (By.XPATH, "//button[contains(normalize-space(.), 'Apply')]"),
            ]
            for by, selector in submit_selectors:
                try:
                    submit_button = WebDriverWait(dialog, 5).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if submit_button:
                        break
                except Exception:
                    continue

            if submit_button:
                self.safe_click(driver, submit_button)
                self.human_delay(2, 4)
            else:
                logger.warning("⚠️ Could not find the filter apply button. Leaving the search as-is.")

        except Exception as exc:
            logger.warning(f"⚠️ Failed while applying LinkedIn search filters: {exc}")

        return normalized_filters

    def search_and_connect(self, driver, keywords, max_invites=20, search_id=None, search_filters=None):
        """Search for profiles and send connection requests"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
        
        logger.info(f"🔍 Searching for: {keywords}")
        normalized_filters = self.normalize_keyword_search_filters(search_filters)
        url = self.build_people_search_url(keywords, normalized_filters)
        logger.info(f"🔗 Search URL: {url}")
        
        driver.get(url)
        self.human_delay(4, 7)
        if normalized_filters:
            logger.info("🧭 Optional search filters were requested for this search.")
        sent_count = 0
        page_loops = 0
        total_attempts = 0
        
        # --- FIX: Main loop now checks for stop_requested flag ---
        while sent_count < max_invites and page_loops < 10:
            if search_id and self.active_searches[search_id].get('stop_requested'):
                logger.info("🛑 Stop requested, halting search.")
                break
                
            logger.info(f"📊 Current status: {sent_count}/{max_invites} invitations sent")
            should_rescan_current_page = False
            
            # Find connect buttons
            self.human_delay(2, 4)
            connect_buttons = self.find_connect_buttons_enhanced(driver)
            
            if not connect_buttons:
                logger.info("No connect buttons found on this page")
                if not self.go_to_next_page(driver):
                    break
                page_loops += 1
                self.human_delay(3, 5)
                continue
            
            for btn in connect_buttons:
                if search_id and self.active_searches[search_id].get('stop_requested'):
                    logger.info("🛑 Stop requested, halting connection loop.")
                    break
                    
                if sent_count >= max_invites:
                    logger.info(f"🎯 Target reached: {sent_count}/{max_invites} invitations sent")
                    return sent_count
                
                total_attempts += 1
                logger.info(f"🔄 Attempting connection #{total_attempts}")
                self.human_delay(1, 3)
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                    self.human_delay(0.5, 1.5)  # Wait after scrolling
                    if self.click_connect_and_validate(driver, btn):
                        sent_count += 1
                        logger.info(f"✅ Success! Sent invitation #{sent_count}/{max_invites}")
                        time.sleep(random.uniform(2, 4))
                        # Re-scan this same page because the DOM may have reloaded or button states changed.
                        should_rescan_current_page = True
                        break
                    else:
                        logger.info(f"❌ Failed to send invitation (attempt #{total_attempts})")
                except StaleElementReferenceException:
                    logger.info("🔄 Button references went stale (page reloaded), re-scanning...")
                    should_rescan_current_page = True
                    break
                except Exception as e:
                    logger.error(f"❌ Exception during connection attempt: {e}", exc_info=True)
                    continue
            
            # Check for stop before navigating to next page
            if search_id and self.active_searches[search_id].get('stop_requested'):
                break

            if should_rescan_current_page:
                logger.info("🔁 Re-scanning the current page for remaining connect buttons.")
                self.human_delay(1, 2)
                continue

            # Navigate to next page
            if not self.go_to_next_page(driver):
                logger.info("No more pages available")
                break
            page_loops += 1
            time.sleep(random.uniform(1, 5))
        
        logger.info(f"🏁 Final results: {sent_count}/{max_invites} invitations sent ({total_attempts} total attempts)")
        return sent_count

    def execute_keyword_search_task(self, search_id, search_params):
        """
        A thread-safe wrapper to execute the keyword search task.
        It handles locking, driver acquisition, execution, and reporting.
        """
        self.browser_lock.acquire()
        try:
            logger.info(f"🔑 Browser lock acquired for search task {search_id}")
            
            # --- FIX: Initialize the search state so it can be stopped ---
            search_filters = self.normalize_keyword_search_filters(search_params.get('filters', {}))
            self.active_searches[search_id] = {
                "status": "running",
                "stop_requested": False,
                "keywords": search_params.get('keywords', ''),
                "max_invites": search_params.get('max_invites', 10),
                "invites_sent": 0,
                "filters": search_filters,
            }
            # --- End of Fix ---

            driver = self.get_shared_driver()
            if not driver:
                raise Exception("Failed to get a valid browser session for the task.")
            
            # Pass the validated driver and search_id to the actual logic function
            self.run_enhanced_keyword_search(driver, search_id, search_params)

        except Exception as e:
            logger.error(f"❌ A critical error occurred in search task {search_id}: {e}")
            self.report_search_results_to_dashboard(search_id, {
                "error": str(e),
                "message": "The search task failed due to a critical error.",
                "success": False
            })
        finally:
            logger.info(f"🔑 Browser lock released for search task {search_id}")
            # Clean up the active search entry
            if search_id in self.active_searches:
                del self.active_searches[search_id]
            self.browser_lock.release()

    def execute_outreach_task(self, task_id, campaign_id, user_config, campaign_data):
        """A thread-safe wrapper to execute an outreach campaign."""
        self.browser_lock.acquire()
        try:
            logger.info(f"🔑 Browser lock acquired for outreach campaign {campaign_id}")
            driver = self.get_shared_driver()
            if not driver:
                raise Exception("Failed to get a valid browser session for the campaign.")
            
            # Pass the shared driver to the campaign logic
            self.run_enhanced_outreach_campaign(driver, task_id, campaign_id, user_config, campaign_data)

        except Exception as e:
            logger.error(f"❌ A critical error occurred in outreach campaign {campaign_id}: {e}", exc_info=True)
            self.active_campaigns[campaign_id]['status'] = 'failed'
            self.active_campaigns[campaign_id]['error'] = str(e)
            self.report_progress_to_dashboard(campaign_id, final=True, task_id=task_id)
        finally:
            logger.info(f"🔑 Browser lock released for outreach campaign {campaign_id}")
            self.browser_lock.release()

    def execute_inbox_task(self, process_id, platform='linkedin'):
        """
        A thread-safe wrapper to execute the inbox processing task.
        Handles locking, driver acquisition, and reporting.
        """
        self.browser_lock.acquire()
        try:
            logger.info(f"🔑 Browser lock acquired for {platform} inbox task {process_id}")
            driver = self.get_shared_driver()
            
            if not driver:
                raise Exception("Failed to get a valid browser session for inbox processing.")

            # Get the user's name if not already cached
            if not hasattr(self, 'user_name') or not self.user_name:
                self.user_name = self.get_user_profile_name(driver)
            
            logger.info(f"👤 Proceeding with user name: {self.user_name}")

            # Execute the inbox processing ONE time with the correct platform
            results = self.enhanced_inbox.process_inbox_enhanced(
                driver, 
                user_name=self.user_name or "Me", 
                session_id=process_id,
                client_instance=self,
                platform_str=platform  # Pass the platform string correctly
            )

            # Report the final results
            self.report_task_result({
                'task_id': process_id,
                'type': 'process_inbox',
                'success': results.get('success', False),
                'payload': results,
                'error': results.get('error')
            })

        except Exception as e:
            logger.error(f"❌ A critical error occurred in inbox task {process_id}: {e}", exc_info=True)
            self.report_task_result({
                'task_id': process_id,
                'type': 'process_inbox',
                'success': False,
                'payload': None,
                'error': f"A critical client-side error occurred: {e}"
            })
        finally:
            logger.info(f"🔑 Browser lock released for inbox task {process_id}")
            self.browser_lock.release()

    def find_connect_buttons_enhanced(self, driver):
        """Find connect buttons with updated 2025 LinkedIn detection.
        
        LinkedIn now uses aria-label='Invite [Name] to connect' on the button
        rather than a visible 'Connect' text node, so we must search by aria-label.
        """
        from selenium.webdriver.common.by import By

        if not self._wait_for_people_results(driver, timeout=10):
            logger.info("People results did not finish rendering before button scan.")

        deadline = time.time() + 8
        last_count = 0

        while time.time() < deadline:
            buttons = []

            # Strategy 1: CSS – fastest, matches aria-label pattern "Invite … to connect"
            css_selectors = [
                "button[aria-label*='to connect']",
                "button[aria-label*='Connect']",
                "a[aria-label*='to connect']",
            ]
            for css in css_selectors:
                try:
                    found = driver.find_elements(By.CSS_SELECTOR, css)
                    for btn in found:
                        if btn.is_displayed() and btn.is_enabled():
                            parent_text = ""
                            try:
                                parent = btn.find_element(
                                    By.XPATH,
                                    "./ancestor::li[1] | ./ancestor::div[contains(@class,'entity-result')][1]"
                                )
                                parent_text = parent.text
                            except Exception:
                                pass
                            if "Pending" not in parent_text and "Following" not in parent_text:
                                buttons.append(btn)
                except Exception as e:
                    logger.debug(f"CSS selector failed: {css}, e: {e}")
                if buttons:
                    break

            # Strategy 2: XPath fallbacks (older LinkedIn UI / "Connect" span text)
            if not buttons:
                xpath_selectors = [
                    "//button[.//span[normalize-space()='Connect']]",
                    "//button[@aria-label and contains(@aria-label, 'connect')]",
                    "//div[@role='button' and .//span[normalize-space()='Connect']]",
                ]
                for xpath in xpath_selectors:
                    try:
                        found = driver.find_elements(By.XPATH, xpath)
                        for btn in found:
                            if btn.is_displayed() and btn.is_enabled():
                                parent_text = ""
                                try:
                                    parent = btn.find_element(By.XPATH, "./ancestor::li[1]")
                                    parent_text = parent.text
                                except Exception:
                                    pass
                                if "Pending" not in parent_text and "Following" not in parent_text:
                                    buttons.append(btn)
                    except Exception as e:
                        logger.debug(f"XPath selector failed: {xpath}, e: {e}")
                    if buttons:
                        break

            seen_ids = set()
            unique_buttons = []
            for btn in buttons:
                try:
                    eid = btn.id
                except Exception:
                    eid = None
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    unique_buttons.append(btn)

            if unique_buttons:
                logger.info(f"Found {len(unique_buttons)} available connect buttons")
                return unique_buttons

            if last_count == 0:
                logger.debug("Results are present but connect buttons have not appeared yet; retrying.")
            last_count = len(unique_buttons)
            time.sleep(0.5)

        logger.info("Found 0 available connect buttons")
        return []

    def _deprecated_click_connect_and_validate(self, driver, button):
        """Deprecated: superseded by reliability-first handler below."""
        import time

        self.human_delay(0.5, 1.5)
        if self._find_active_connect_dialog(driver, timeout=1):
            if not self.dismiss_active_modal(driver, timeout=2):
                logger.warning("⚠️ A previous modal is still blocking the page; skipping this result.")
                return False
        
        # 1. Scroll and hide overlays (like the chat window)
        driver.execute_script("""
            arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});
            let chat = document.querySelector('.msg-overlay-container');
            if (chat) chat.style.display = 'none';
        """, button)
        time.sleep(1)

        # 2. Click the Connect button natively or via JS fallback
        try:
            button.click()
            logger.info("✅ Clicked initial Connect button natively.")
        except Exception:
            driver.execute_script("arguments[0].click();", button)
            logger.info("✅ Clicked initial Connect button via JS.")

        # 3. Wait for the actual invite UI instead of searching the whole page immediately
        dialog = self._find_active_connect_dialog(driver, timeout=8)
        if not dialog:
            if self.click_send_without_note_button(driver, timeout=2):
                return True
            logger.warning("⚠️ Connect modal did not appear after clicking the result.")
            return False

        # 4. Handle only the active modal
        return self.handle_connect_modal(driver, dialog=dialog)

    def _deprecated_handle_connect_modal(self, driver, dialog=None):
        """Deprecated: superseded by reliability-first handler below."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        self.human_delay(1, 2)

        dialog = dialog or self._find_active_connect_dialog(driver, timeout=6)
        if not dialog:
            logger.warning("⚠️ No active connect modal found.")
            return False

        # 1. Attempt to click Send Without Note
        clicked = self.click_send_without_note_button(driver, timeout=8, dialog=dialog)

        if not clicked:
            if self.dismiss_active_modal(driver, timeout=2):
                logger.info("🧹 Dismissed stuck modal.")
            return False
            # If we couldn't click send, dismiss the modal so we can move to the next person cleanly
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                driver.execute_script("arguments[0].click();", close_btn)
                logger.info("🧹 Dismissed stuck modal.")
            except:
                pass
            return False
        
        self.human_delay(1, 2)
        
        # 2. Check for success - Look ONLY for "Pending" state
        try:
            WebDriverWait(driver, 4).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Pending')]")),
                    EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Pending')]")),
                    EC.invisibility_of_element(dialog)
                )
            )
            return True
        except TimeoutException:
            return self._find_active_connect_dialog(driver, timeout=1) is None
            # If it doesn't say Pending but the modal closed on its own, assume success
            try:
                driver.find_element(By.CSS_SELECTOR, ".artdeco-modal")
                return False # Modal still here = failed
            except:
                return True

    def click_connect_and_validate(self, driver, button):
        """Click Connect and handle all LinkedIn outcomes reliably."""
        import time
        from selenium.webdriver.common.action_chains import ActionChains

        self.human_delay(0.5, 1.5)
        # Clean previous modal if any
        if self._find_active_connect_dialog(driver, timeout=1):
            if not self.dismiss_active_modal(driver, timeout=2):
                logger.warning("⚠️ Modal blocking page, skipping.")
                return False

        # Scroll + hide chat overlay + clear any blocking elements including interop-outlet
        driver.execute_script("""
            arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
            let chat = document.querySelector('.msg-overlay-container');
            if (chat) chat.style.display = 'none';
            // Hide premium upsell overlays and the interop-outlet that intercepts clicks
            document.querySelectorAll(
                '.artdeco-toasts, .premium-upsell-link, #interop-outlet, #interop-outlet-main, [id*="interop-outlet"]'
            ).forEach(el => el.style.display = 'none');
        """, button)

        # Extract href for <A> tag fallback (LinkedIn now uses <A> connect buttons)
        connect_href = None
        try:
            connect_href = driver.execute_script("""
                const b = arguments[0];
                if (b.tagName === 'A' && b.href && b.href.includes('search-custom-invite')) {
                    return b.href;
                }
                const parentA = b.closest('a[href*="search-custom-invite"]');
                if (parentA) return parentA.href;
                return null;
            """, button)
            if connect_href:
                logger.info(f"📎 Extracted custom invite href: {connect_href}")
        except Exception:
            pass
        time.sleep(1.0)

        # Log what we're about to click for diagnostics
        try:
            btn_info = driver.execute_script("""
                const b = arguments[0];
                const rect = b.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const elAtPoint = document.elementFromPoint(cx, cy);
                let interceptor = null;
                if (elAtPoint && !b.contains(elAtPoint)) {
                    interceptor = elAtPoint.tagName + (elAtPoint.className ? '.' + elAtPoint.className : '') + (elAtPoint.id ? '#' + elAtPoint.id : '');
                }
                
                return {
                    tag: b.tagName,
                    aria: b.getAttribute('aria-label'),
                    text: (b.innerText || '').trim().substring(0, 50),
                    visible: b.offsetParent !== null,
                    disabled: b.disabled,
                    rect: {top: rect.top, left: rect.left, w: rect.width, h: rect.height},
                    interceptor: interceptor,
                    href: b.href ? b.href : null
                };
            """, button)
            logger.info(f"🔍 Button info before click: {btn_info}")
        except Exception:
            pass

        # Click connect using the real actionable element first.
        from selenium.webdriver.common.by import By
        click_targets = []
        try:
            actionable_target = button
            if (button.tag_name or "").lower() not in {"a", "button"}:
                actionable_target = button.find_element(By.XPATH, "./ancestor-or-self::a[1] | ./ancestor-or-self::button[1]")
            click_targets.append(("primary", actionable_target))
        except Exception:
            click_targets.append(("primary", button))

        try:
            span_target = button.find_element(By.CSS_SELECTOR, "span.artdeco-button__text")
            click_targets.append(("label_span", span_target))
        except Exception:
            pass

        try:
            generic_span_target = button.find_element(By.CSS_SELECTOR, "span")
            if all(target.id != generic_span_target.id for _, target in click_targets):
                click_targets.append(("fallback_span", generic_span_target))
        except Exception:
            pass

        clicked_via_target = None
        for target_name, click_target in click_targets:
            try:
                ActionChains(driver).move_to_element(click_target).pause(0.3).click(click_target).perform()
                logger.info(f"✅ Fired Connect button click via ActionChains on {target_name}.")
                clicked_via_target = click_target
                time.sleep(0.8)
                if self._has_active_invite_modal(driver) or self._button_or_card_indicates_sent(driver, button):
                    break
            except Exception as e:
                logger.debug(f"ActionChains click failed on {target_name}: {e}")

            try:
                click_target.click()
                logger.info(f"✅ Fired native Selenium click on {target_name}.")
                clicked_via_target = click_target
                time.sleep(0.8)
                if self._has_active_invite_modal(driver) or self._button_or_card_indicates_sent(driver, button):
                    break
            except Exception as e:
                logger.debug(f"Native click failed on {target_name}: {e}")

        # ALWAYS fire the deep JS event dispatch as a secondary guarantee!
        # If the primary element did not trigger a state change, also hit inner descendants.
        if not (self._has_active_invite_modal(driver) or self._button_or_card_indicates_sent(driver, button)):
            try:
                driver.execute_script("""
                    const btn = arguments[0];
                    const targets = [
                        btn,
                        btn.querySelector('span.artdeco-button__text'),
                        btn.querySelector('span')
                    ].filter(Boolean);
                    
                    targets.forEach(t => {
                        try {
                            t.focus();
                            t.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true}));
                            t.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                            t.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
                            t.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, cancelable: true}));
                            t.click();
                        } catch(e) {}
                    });
                """, button)
                logger.info("✅ Fired deep JS event dispatch across clickable element and inner labels.")
            except Exception as e:
                logger.warning(f"⚠️ JS click fallback failed (often means click succeeded and button went stale): {e}")

        time.sleep(1.2)
    
        # Detect outcome
        result = self._detect_connect_outcome(driver, button, timeout=9)
    
        if result in ['MODAL', 'OTHER_MODAL']:
            return self.handle_connect_modal(driver)
        elif result == 'SENT':
            logger.info("🎉 Invitation sent (instant or button state change).")
            return True

        if self._has_active_invite_modal(driver) or self._find_active_connect_dialog(driver, timeout=1.5):
            logger.info("✅ Invite modal detected by fallback probe.")
            return self.handle_connect_modal(driver)

        # ── HREF FALLBACK: Navigate directly to the custom invite page ──
        if connect_href:
            logger.info("🔗 Click did not trigger modal — navigating directly to invite href as fallback.")
            return self._handle_custom_invite_page(driver, connect_href)

        self._log_invite_modal_diagnostics(
            driver,
            context="connect_outcome_none",
            selectors=[
                (By.CSS_SELECTOR, "#artdeco-modal-outlet [data-test-modal-id='send-invite-modal']"),
                (By.CSS_SELECTOR, "#artdeco-modal-outlet .artdeco-modal-overlay"),
                (By.CSS_SELECTOR, "button[aria-label='Send without a note']"),
            ]
        )
        logger.warning("❌ No modal or success state detected.")
        return False
    def _handle_custom_invite_page(self, driver, invite_href):
        """Fallback: navigate directly to the custom invite href to trigger the modal.

        LinkedIn's new <A> connect buttons have href like:
            /preload/search-custom-invite/?vanityName=...
        Navigating there loads the invite modal inside the search page.
        """
        import time

        search_url = driver.current_url
        logger.info(f"🔗 Navigating to custom invite page: {invite_href}")

        try:
            # Navigate to the invite href — LinkedIn will load the modal
            driver.get(invite_href)
            time.sleep(2.5)

            # Wait for the send-invite modal to appear (up to 8 seconds)
            deadline = time.time() + 8
            modal_found = False

            while time.time() < deadline:
                modal_found = self._has_active_invite_modal(driver)
                if modal_found:
                    break

                # Also check for the artdeco modal with send button directly
                has_modal = driver.execute_script("""
                    const outlet = document.querySelector('#artdeco-modal-outlet');
                    if (!outlet) return false;
                    const overlay = outlet.querySelector(
                        '[data-test-modal-id="send-invite-modal"][aria-hidden="false"], ' +
                        '.artdeco-modal-overlay:not([aria-hidden="true"])'
                    );
                    if (!overlay) return false;
                    const sendBtn = overlay.querySelector(
                        "button[aria-label='Send without a note'], " +
                        "button[aria-label*='Send without a note'], " +
                        "button.artdeco-button--primary"
                    );
                    return Boolean(sendBtn);
                """)
                if has_modal:
                    modal_found = True
                    break

                time.sleep(0.4)

            if modal_found:
                logger.info("✅ Invite modal appeared after href navigation.")
                success = self.handle_connect_modal(driver)

                # Navigate back to search results
                if driver.current_url != search_url:
                    logger.info("↩️ Navigating back to search results.")
                    driver.get(search_url)
                    time.sleep(2)

                return success
            else:
                # Check if the invitation was sent instantly (no modal)
                sent = driver.execute_script("""
                    const el = Array.from(document.querySelectorAll('span, div, button')).find(n => {
                        const t = (n.innerText || '').trim().toLowerCase();
                        return t === 'pending' || t.includes('invitation sent');
                    });
                    return Boolean(el);
                """)
                if sent:
                    logger.info("🎉 Invitation sent instantly via href navigation (no modal needed).")
                    if driver.current_url != search_url:
                        driver.get(search_url)
                        time.sleep(2)
                    return True

                logger.warning("❌ Modal did not appear even after href navigation.")
                # Navigate back to search results regardless
                if driver.current_url != search_url:
                    driver.get(search_url)
                    time.sleep(2)
                return False

        except Exception as e:
            logger.error(f"❌ Error handling custom invite page: {e}", exc_info=True)
            # Always try to get back to search results
            try:
                if driver.current_url != search_url:
                    driver.get(search_url)
                    time.sleep(2)
            except Exception:
                pass
            return False

    def _detect_connect_outcome(self, driver, button, timeout=6):
        """Detect what happened after clicking Connect (modal or instant send)."""
        import time
     
        deadline = time.time() + timeout
        modal_grace_deadline = time.time() + min(3.5, max(2.0, timeout * 0.45))
     
        while time.time() < deadline:
            try:
                if self._has_active_invite_modal(driver):
                    return 'MODAL'

                # 1. First, check purely for modals regardless of the button state
                result = driver.execute_script("""
                    const pendingBtn = Array.from(document.querySelectorAll('button')).find(b => {
                        const text = (b.innerText || '').trim();
                        return text === 'Pending';
                    });
                    if (pendingBtn) return 'SENT';

                    const pendingSpan = Array.from(document.querySelectorAll('span, div')).find(node => {
                        const text = (node.innerText || '').trim();
                        return text === 'Pending' || text.includes('Invitation sent');
                    });
                    if (pendingSpan) return 'SENT';

                    const outletDialog = document.querySelector(
                        "#artdeco-modal-outlet .artdeco-modal.send-invite, " +
                        "#artdeco-modal-outlet .artdeco-modal[role='dialog'], " +
                        "#artdeco-modal-outlet [data-test-modal][role='dialog'], " +
                        "#artdeco-modal-outlet [role='dialog']"
                    );
                    if (outletDialog) return 'OTHER_MODAL';

                    const anyModal = document.querySelector('.artdeco-modal[role="dialog"]');
                    if (anyModal) return 'OTHER_MODAL';
                    
                    return null;
                """)
                if result in {'MODAL', 'OTHER_MODAL'}:
                    return result

                if time.time() >= modal_grace_deadline:
                    if self._button_or_card_indicates_sent(driver, button):
                        return 'SENT'

                    toast_sent = driver.execute_script("""
                        const successNode = Array.from(document.querySelectorAll('div[role="alert"], div[aria-live], span, div')).find((node) => {
                            const text = (node.innerText || '').trim().toLowerCase();
                            return text.includes('invitation sent');
                        });
                        return Boolean(successNode);
                    """)
                    if toast_sent:
                        return 'SENT'
                    
            except Exception as e:
                logger.error(f"❌ Exception in outcome detection: {e}")
                
            time.sleep(0.4)
     
        return "NONE"
     
     
     
     
    def handle_connect_modal(self, driver, dialog=None):
        """Handle modal and click Send (robust + flexible text match)."""
        import time
    
        self.human_delay(1, 2)
        logger.info("⏳ Handling connect modal...")
    
        deadline = time.time() + 10
        clicked = False
        last_result = None
    
        while time.time() < deadline:
            result = driver.execute_script("""
                try {
                    let overlay = document.querySelector('#artdeco-modal-outlet [data-test-modal-id="send-invite-modal"][aria-hidden="false"]');
                    if (!overlay) {
                        overlay = document.querySelector('#artdeco-modal-outlet [data-test-modal-container][data-test-modal-id="send-invite-modal"]');
                    }
                    
                    // Fallback to any active modal overlay if exact ID is missing
                    if (!overlay || overlay.getAttribute('aria-hidden') === 'true') {
                        overlay = document.querySelector('#artdeco-modal-outlet .artdeco-modal-overlay:not([aria-hidden="true"])');
                        if (!overlay) {
                            return 'NO_ACTIVE_MODAL';
                        }
                    }
    
                    let actionbar = overlay.querySelector('.artdeco-modal__actionbar');
                    let dialog = overlay.querySelector('.artdeco-modal.send-invite, .artdeco-modal[role="dialog"], [data-test-modal][role="dialog"], [role="dialog"]');
                    if (!actionbar) {
                        // Sometimes the dialog itself is separated from the overlay element in the DOM tree depending on the parent
                        dialog = document.querySelector('#artdeco-modal-outlet .artdeco-modal.send-invite, #artdeco-modal-outlet .artdeco-modal[role="dialog"], #artdeco-modal-outlet [role="dialog"], .artdeco-modal[role="dialog"]');
                        if (dialog) {
                            actionbar = dialog.querySelector('.artdeco-modal__actionbar');
                        }
                    }
                    
                    if (!actionbar) return 'NO_ACTIONBAR';
    
                    let btn = null;
                    const selectorTargets = [
                        "button[aria-label='Send without a note']",
                        "button[aria-label*='Send without a note']",
                        "button.artdeco-button--primary",
                        "button[aria-label*='Send']"
                    ];
                    for (const selector of selectorTargets) {
                        btn = actionbar.querySelector(selector)
                            || overlay.querySelector(selector)
                            || (dialog && dialog.querySelector(selector));
                        if (btn) break;
                    }

                    if (!btn) {
                        btn = Array.from(actionbar.querySelectorAll('button')).find(b => {
                            const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                            const text = (b.innerText || '').toLowerCase();
        
                            return aria.includes('send') || text.includes('send');
                        });
                    }

                    if (!btn) return 'NO_BUTTON';

                    if (btn.disabled) return 'BUTTON_DISABLED';

                    const rect = btn.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return 'NOT_VISIBLE';

                    const elAtPoint = document.elementFromPoint(
                        rect.left + rect.width / 2,
                        rect.top + rect.height / 2
                    );

                    if (elAtPoint && !btn.contains(elAtPoint) && !actionbar.contains(elAtPoint)) {
                        return 'CLICK_INTERCEPTED';
                    }

                    btn.scrollIntoView({block: 'center'});
                    btn.focus();

                    btn.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                    btn.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
                    btn.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    btn.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    btn.click();

                    return 'CLICKED_SUCCESS';

                } catch (e) {
                    return 'ERROR: ' + e.toString();
                }
            """)
    
            last_result = result
    
            if result == 'CLICKED_SUCCESS':
                clicked = True
                logger.info("✅ Clicked Send button.")
                break
    
            elif result == 'BUTTON_DISABLED':
                time.sleep(0.3)
    
            elif result in ['NO_ACTIVE_MODAL', 'NO_ACTIONBAR']:
                time.sleep(0.3)
    
            elif result == 'CLICK_INTERCEPTED':
                logger.debug("Click intercepted, retrying...")
                time.sleep(0.4)
    
            else:
                time.sleep(0.4)
    
        if not clicked:
            logger.error(f"❌ Failed to click send button. Last result: {last_result}")
    
            # Fallback
            try:
                fallback = driver.find_element("xpath", "//button[contains(., 'Send')]")
                fallback.click()
                logger.info("✅ Fallback Selenium click worked.")
                clicked = True
            except Exception as e:
                logger.error(f"❌ Fallback failed: {e}")
                self.dismiss_active_modal(driver, timeout=2)
                return False
    
        # Verify submission
        success = self._wait_for_invite_submit_result(driver, timeout=5)
    
        if success:
            logger.info("🎉 Invitation sent successfully!")
        else:
            logger.warning("⚠️ Clicked but verification uncertain.")
    
        self.human_delay(0.8, 1.6)
        return True

    
    def process_inbox_replies_enhanced(self, driver, max_replies=10):
        """Enhanced inbox processing with LinkedIn Helper 2-like features"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        logger.info("🤖 Starting enhanced inbox processing (LinkedIn Helper 2 style)...")
        results = []
        
        if not self.navigate_to_messaging(driver):
            return {"success": False, "error": "Messaging navigation failed"}
        
        try:
            # Find unread conversations with better selectors
            unread_selectors = [
                "li.msg-conversations-container__conversation-list-item--is-unread",
                "li.conversation-list-item--unread",
                "li.msg-conversation-listitem--unread",
                "li[data-test-unread-message='true']"
            ]
            
            unread_items = []
            for selector in unread_selectors:
                try:
                    unread_items = driver.find_elements(By.CSS_SELECTOR, selector)
                    if unread_items:
                        break
                except:
                    continue
            
            logger.info(f"Found {len(unread_items)} unread conversations")
            
            for idx, item in enumerate(unread_items[:max_replies]):
                try:
                    # Extract participant name from list item
                    name_selectors = [
                        ".msg-conversation-listitem__participant-names",
                        ".conversation-list-item__participant-names",
                        ".conversation-list-item__title"
                    ]
                    
                    name = "Unknown"
                    for n_selector in name_selectors:
                        try:
                            name_elem = item.find_element(By.CSS_SELECTOR, n_selector)
                            name = name_elem.text.strip()
                            if name:
                                break
                        except:
                            continue
                    
                    logger.info(f"Processing conversation with {name} ({idx+1}/{len(unread_items)})")
                    
                    # Open conversation
                    driver.execute_script("arguments[0].click();", item)
                    self.human_delay(2, 4)
                    
                    # Wait for conversation to load
                    WebDriverWait(driver, 10).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.msg-s-message-list-content")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.msg-thread"))
                        )
                    )
                    
                    # Extract conversation details
                    conversation_details = self.extract_conversation_details(driver)
                    
                    # Get complete conversation history
                    conversation_history = self.get_complete_conversation_history(driver)
                    
                    if not conversation_history:
                        logger.warning("No messages found, skipping")
                        results.append({"name": name, "status": "skipped", "reason": "empty history"})
                        self.navigate_to_messaging(driver)
                        continue
                    
                    # Check if last message is from user
                    if conversation_history and conversation_history[-1]["sender"] == "You":
                        logger.info("Last message was from user, skipping")
                        results.append({"name": name, "status": "skipped", "reason": "already replied"})
                        self.navigate_to_messaging(driver)
                        continue
                    
                    # Generate AI response with full context
                    ai_reply = self.generate_contextual_ai_response(conversation_history, conversation_details)
                    
                    logger.info(f"Generated AI response: {ai_reply}")
                    
                    # Send response
                    if self.send_chat_message(driver, ai_reply):
                        logger.info(f"✅ Replied to {name}")
                        results.append({
                            "name": name, 
                            "status": "replied", 
                            "message": ai_reply,
                            "context": {
                                "message_count": len(conversation_history),
                                "participant_info": conversation_details
                            }
                        })
                    else:
                        logger.error(f"❌ Failed to reply to {name}")
                        results.append({"name": name, "status": "failed", "reason": "send error"})
                    
                    # Return to inbox with delay
                    self.navigate_to_messaging(driver)
                    self.human_delay(3, 6)  # Longer delay between conversations
                    
                except Exception as e:
                    logger.error(f"Error processing conversation: {e}")
                    results.append({"name": f"Unknown{idx}", "status": "error", "reason": str(e)})
                    try:
                        self.navigate_to_messaging(driver)
                    except:
                        driver.refresh()
                        self.human_delay(3, 5)
            
            return {"success": True, "results": results, "processed_count": len(results)}
            
        except Exception as e:
            logger.error(f"Inbox processing failed: {e}")
            return {"success": False, "error": str(e)}

    

    def generate_contextual_ai_response(self, conversation_history: List[Dict[str, str]], 
                                   conversation_details: Dict[str, Any]) -> str:
        """Generate a highly contextual AI response based on conversation history and details"""
        fallback_msg = "Thank you for your message. I'll review this and respond properly soon."

        # Format conversation history for the prompt
        formatted_history = "\n".join([
            f"{msg['sender']}: {msg['message']}" for msg in conversation_history[-10:]  # Last 10 messages
        ])
        
        # Get participant info for personalization
        participant_name = conversation_details.get('participant_name', 'there')
        participant_headline = conversation_details.get('participant_headline', '')
        
        prompt = f"""You are a professional LinkedIn assistant. Craft a thoughtful response to this conversation.

    Conversation Context:
    - Participant: {participant_name}
    - Headline: {participant_headline}

    Recent Messages:
    {formatted_history}

    Guidelines for your response:
    1. Be professional yet approachable
    2. Match the tone and formality of the conversation
    3. Keep it concise (1-3 sentences max)
    4. Address any questions or points raised
    5. If appropriate, suggest a next step or call to action
    6. Sign with just your first name if needed

    Craft your response:"""
        
        dashboard_url = self.config.get('dashboard_url', 'http://127.0.0.1:5000')
        endpoint = f"{dashboard_url.rstrip('/')}/api/client/ai/generate"

        for attempt in range(3):
            try:
                response = requests.post(
                    endpoint, 
                    json={'prompt': prompt},
                    headers=self._get_auth_headers(),
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        ai_message = data.get('message', '').strip()
                        
                        # Clean up the response
                        ai_message = re.sub(r'^(Response:|AI:|Assistant:)\s*', '', ai_message, flags=re.IGNORECASE)
                        ai_message = ai_message.strip('"\'')
                        
                        # Ensure it's not too long
                        if len(ai_message) > 300:
                            ai_message = ai_message[:297] + "..."
                            
                        return ai_message
                    else:
                        logger.error(f"❌ Backend AI Generation error: {data.get('error')}")
                        break
                elif response.status_code == 429:
                    logger.warning("⏳ Daily AI quota exceeded or rate limit hit. Using fallback message.")
                    return fallback_msg
                else:
                    logger.error(f"❌ AI proxy returned {response.status_code}: {response.text}")
                    break
                    
            except Exception as e:
                logger.error(f"AI response generation failed: {e}")
                time.sleep(2)
                
        return fallback_msg


    # ==============================================
    # ENHANCED CAMPAIGN RUNNERS
    # ==============================================

    # Replace your run_enhanced_outreach_campaign method with this corrected version

    def run_enhanced_outreach_campaign(self, driver, task_id, campaign_id, user_config, campaign_data):
        """
        Run outreach campaign with AI generation, user preview, and confirmation.
        """
        try:
            # Initialize campaign status
            self.active_campaigns[campaign_id] = {
                'task_id': task_id,
                'status': 'running',
                'progress': 0,
                'total': len(campaign_data.get('contacts', [])[:campaign_data.get('max_contacts', 0)]),
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'already_messaged': 0,
                'stop_requested': False,
                'awaiting_confirmation': False,
                'current_contact_preview': None,  # Changed from current_contact
                'start_time': datetime.now().isoformat(),
                'contacts_processed': [],
                'user_action': None
            }

            # Load previously messaged profiles to avoid duplicates
            tracked_profiles = set()
            tracked_profiles_file = 'messaged_profiles.json'
            if os.path.exists(tracked_profiles_file):
                try:
                    with open(tracked_profiles_file, 'r', encoding='utf-8') as f:
                        tracked_profiles = set(json.load(f))
                except Exception:
                    pass

            contacts = campaign_data.get('contacts', [])[:campaign_data.get('max_contacts', 20)]
            
            for idx, contact in enumerate(contacts):
                # Check for stop request
                if self.active_campaigns[campaign_id].get('stop_requested'):
                    self.active_campaigns[campaign_id]['status'] = 'stopped'
                    break

                try:
                    # Basic contact validation
                    linkedin_url = contact.get('LinkedIn_profile', '')
                    if not linkedin_url or 'linkedin.com/in/' not in linkedin_url:
                        self.active_campaigns[campaign_id]['failed'] += 1
                        self.active_campaigns[campaign_id]['progress'] += 1
                        continue

                    # Skip if already messaged
                    if linkedin_url in tracked_profiles:
                        logger.info(f"⭐ Skipping {contact['Name']} - already messaged")
                        self.active_campaigns[campaign_id]['already_messaged'] += 1
                        self.active_campaigns[campaign_id]['progress'] += 1
                        continue

                    # --- AUTOMATION LOGIC ---
                    logger.info(f"🌐 Navigating to {contact['Name']}'s profile...")
                    driver.get(linkedin_url)
                    time.sleep(random.uniform(3, 5))

                    profile_data = self.extract_profile_data(driver)

                    logger.info(f"🤖 Generating personalized message for {contact['Name']}...")
                    message = self.generate_message(
                        contact.get('Name'),
                        contact.get('Company'),
                        contact.get('Role'),
                        contact.get('services and products_1', ''),
                        contact.get('services and products_2', ''),
                        profile_data
                    )

                    # ========== PAUSE & WAIT FOR USER DECISION ==========
                    
                    # 1. Set up awaiting confirmation state
                    self.active_campaigns[campaign_id]['awaiting_confirmation'] = True
                    self.active_campaigns[campaign_id]['current_contact_preview'] = {
                        'contact': contact,
                        'message': message,
                        'contact_index': idx
                    }
                    
                    # 2. Report to dashboard immediately
                    self.report_progress_to_dashboard(campaign_id, task_id=task_id)
                    
                    # 3. Wait for user decision with timeout
                    logger.info(f"⏳ Waiting for user decision for {contact['Name']}... (Timeout: 5 minutes)")
                    start_wait_time = time.time()
                    user_decision = None
                    
                    while time.time() - start_wait_time < 300:  # 5 minute timeout
                        if self.active_campaigns[campaign_id].get('stop_requested'):
                            break
                        
                        try:
                            self.send_heartbeat_ping()
                        except Exception as e:
                            pass

                        user_decision = self.active_campaigns[campaign_id].get('user_action')
                        if user_decision:
                            logger.info(f"👍 Received user action: {user_decision.get('action')}")
                            break
                        time.sleep(2)  # Poll every 2 seconds

                    # 4. Process the decision
                    # Reset state immediately
                    self.active_campaigns[campaign_id]['awaiting_confirmation'] = False
                    self.active_campaigns[campaign_id]['current_contact_preview'] = None
                    self.active_campaigns[campaign_id]['user_action'] = None
                    
                    # Determine action (default to skip on timeout)
                    action_to_take = user_decision.get('action') if user_decision else 'skip'
                    
                    if action_to_take in ['send', 'edit']:
                        final_message = user_decision.get('message', message) if user_decision else message
                        logger.info(f"▶️ Sending message to {contact['Name']} as per user confirmation.")
                        
                        success = self.send_message_with_priority(driver, final_message, 
                                                                contact.get('Name'), contact.get('Company'))
                        
                        if success:
                            self.active_campaigns[campaign_id]['successful'] += 1
                            tracked_profiles.add(linkedin_url)
                            
                            # Save tracked profiles
                            try:
                                with open(tracked_profiles_file, 'w', encoding='utf-8') as f:
                                    json.dump(list(tracked_profiles), f, indent=2)
                            except Exception as e:
                                logger.warning(f"Could not save tracked profile: {e}")
                            
                            logger.info(f"✅ Successfully sent message to {contact['Name']}")
                            time.sleep(random.uniform(45, 90))  # Long delay after successful send
                        else:
                            self.active_campaigns[campaign_id]['failed'] += 1
                            logger.error(f"❌ Failed to send message to {contact['Name']}")
                    else:
                        # Skip action
                        logger.info(f"⏭️ Skipping {contact['Name']} based on user decision or timeout.")
                        self.active_campaigns[campaign_id]['skipped'] += 1

                    # Update progress
                    self.active_campaigns[campaign_id]['progress'] += 1
                    self.report_progress_to_dashboard(campaign_id, task_id=task_id)

                except Exception as e:
                    logger.error(f"❌ Error processing {contact.get('Name', 'Unknown')}: {e}", exc_info=True)
                    self.active_campaigns[campaign_id]['failed'] += 1
                    self.active_campaigns[campaign_id]['progress'] += 1

            # Final campaign status update
            self.active_campaigns[campaign_id]['status'] = 'completed' if not self.active_campaigns[campaign_id].get('stop_requested') else 'stopped'
            self.active_campaigns[campaign_id]['end_time'] = datetime.now().isoformat()
            self.report_progress_to_dashboard(campaign_id, final=True, task_id=task_id)

        except Exception as e:
            logger.error(f"❌ Campaign {campaign_id} failed critically: {e}", exc_info=True)
            self.active_campaigns[campaign_id]['status'] = 'failed'
            self.active_campaigns[campaign_id]['error'] = str(e)
            self.report_progress_to_dashboard(campaign_id, final=True, task_id=task_id)

    def run_enhanced_keyword_search(self, driver, search_id, search_params):
        """
        Run keyword-based LinkedIn search and connect using a shared driver.
        This function now contains only the core automation logic.
        """
        try:
            keywords = search_params.get('keywords', '')
            max_invites = search_params.get('max_invites', 10)
            search_filters = self.normalize_keyword_search_filters(search_params.get('filters', {}))

            logger.info(f"🔍 Starting keyword search for: '{keywords}' with driver {driver.session_id}")
            if search_filters:
                logger.info(f"🧭 Requested keyword search filters: {search_filters}")

            # --- FIX: Pass the search_id to search_and_connect ---
            sent_count = self.search_and_connect(
                driver,
                keywords,
                max_invites=max_invites,
                search_id=search_id,
                search_filters=search_filters
            )

            logger.info(f"✅ Keyword search completed. Invitations sent: {sent_count}/{max_invites}")
            
            # Check if it was stopped
            if self.active_searches.get(search_id, {}).get('stop_requested'):
                 logger.info(f"Search task {search_id} was stopped by user. Final count: {sent_count}")
                 # Report as 'stopped' (which is a form of success)
                 payload = {
                    'keywords': keywords,
                    'max_invites': max_invites,
                    'filters': search_filters,
                    'invites_sent': sent_count,
                    'status': 'stopped',
                    'timestamp': datetime.now().isoformat()
                }
                 self.report_task_result({
                    'task_id': search_id, 'type': 'keyword_search',
                    'success': True, 'payload': payload, 'error': 'Stopped by user.'
                })
            else:
                # Report successful completion
                payload = {
                    'keywords': keywords,
                    'max_invites': max_invites,
                    'filters': search_filters,
                    'invites_sent': sent_count,
                    'status': 'completed',
                    'timestamp': datetime.now().isoformat()
                }
                self.report_task_result({
                    'task_id': search_id,
                    'type': 'keyword_search',
                    'success': True,
                    'payload': payload,
                    'error': None
                })

        except Exception as e:
            logger.error(f"❌ Keyword search logic for {search_id} failed: {e}", exc_info=True)
            self.report_task_result({
                'task_id': search_id,
                'type': 'keyword_search',
                'success': False,
                'payload': None,
                'error': str(e)
            })

        
    # ─── add to client_bot.py – right after run_enhanced_keyword_search() ─────────
    def run_search_connect_campaign(self, task_id: str, user_cfg: dict, params: dict) -> None:
        """
        Full keyword *search & connect* flow with live progress reporting
        and graceful shutdown on user request.
        """
        try:
            kw = params.get("keywords", "")
            max_invites = int(params.get("max_invites", 15))
            search_filters = self.normalize_keyword_search_filters(params.get("filters", {}))
            
            self.active_searches[task_id].update({
                "status": "initializing",
                "keywords": kw,
                "max_invites": max_invites,
                "filters": search_filters,
                "start_time": datetime.now().isoformat(),
                "invites_sent": 0,
                "progress": 0
            })

            logger.info(f"🚀 Starting search-and-connect campaign: {task_id}")
            logger.info(f"🔍 Keywords: {kw}, Max invites: {max_invites}")

            # Initialize LinkedIn automation instance (same as campaign flow)
            automation = LinkedInAutomation(
                email=user_cfg.get('linkedin_email', self.email),
                password=user_cfg.get('linkedin_password', self.password),
                api_key=user_cfg.get('gemini_api_key', self.config.get('gemini_api_key'))
            )

            # Login to LinkedIn
            self.active_searches[task_id]["status"] = "logging_in"
            logger.info("🔐 Attempting LinkedIn login...")
            
            if not automation.login():
                logger.error("❌ LinkedIn login failed")
                self.active_searches[task_id]["status"] = "failed"
                self.active_searches[task_id]["driver_errors"] += 1
                self.report_search_results_to_dashboard(task_id, {
                    "error": "login_failed",
                    "message": "LinkedIn login failed"
                })
                automation.close()
                return

            logger.info("✅ LinkedIn login successful")
            self.active_searches[task_id]["status"] = "running"

            # Perform search and connect
            logger.info(f"🔍 Starting search and connect for: '{kw}'")
            if search_filters:
                logger.info(f"🧭 Requested search-connect filters: {search_filters}")

            sent_count = self.search_and_connect(
                automation.driver,
                kw,
                max_invites=max_invites,
                search_id=task_id,
                search_filters=search_filters
            )

            # Update final status
            self.active_searches[task_id]["invites_sent"] = sent_count
            self.active_searches[task_id]["progress"] = sent_count
            self.active_searches[task_id]["status"] = "completed"
            self.active_searches[task_id]["end_time"] = datetime.now().isoformat()

            logger.info(f"✅ Search-and-connect completed: {sent_count}/{max_invites} invitations sent")

            # Report final results to dashboard
            self.report_search_results_to_dashboard(task_id, {
                "keywords": kw,
                "max_invites": max_invites,
                "filters": search_filters,
                "invites_sent": sent_count,
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "completion_rate": f"{sent_count}/{max_invites}",
                "message": f"Successfully sent {sent_count} connection requests"
            })

            # Clean up
            automation.close()

        except Exception as exc:
            logger.error(f"❌ Search-connect task {task_id} failed: {exc}")
            self.active_searches[task_id]["status"] = "failed"
            self.active_searches[task_id]["end_time"] = datetime.now().isoformat()
            
            self.report_search_results_to_dashboard(task_id, {
                "error": str(exc),
                "keywords": kw,
                "filters": search_filters,
                "timestamp": datetime.now().isoformat(),
                "success": False
            })

            # Ensure cleanup
            try:
                if 'automation' in locals():
                    automation.close()
            except Exception as cleanup_error:
                logger.error(f"❌ Cleanup error: {cleanup_error}")


    def run_enhanced_inbox_processing(self, process_id, user_config):
        """Enhanced inbox processing with LinkedHelper 2 features"""
        try:
            # Initialize LinkedIn automation
            automation = LinkedInAutomation(
                email=user_config.get('linkedin_email', self.email),
                password=user_config.get('linkedin_password', self.password),
                api_key=user_config.get('gemini_api_key', self.config.get('gemini_api_key'))
            )

            # Login to LinkedIn
            logger.info("🔐 Logging into LinkedIn for enhanced inbox processing...")
            if not automation.login():
                logger.error("❌ Login failed - cannot process inbox")
                self.report_inbox_results_to_dashboard(process_id, {
                    "success": False, 
                    "error": "LinkedIn login failed"
                })
                return

            driver = automation.driver

            # Navigate to messaging
            if not automation.navigate_to_messaging():
                logger.warning("⚠️ Messaging did not load properly")
                self.report_inbox_results_to_dashboard(process_id, {
                    "success": False, 
                    "error": "Failed to navigate to messaging"
                })
                return

            # Use the enhanced inbox system
            results = self.enhanced_inbox.process_inbox_enhanced(automation.driver, max_replies=20)

            
            # Add processing ID to results
            results['process_id'] = process_id
            results['processing_completed_at'] = datetime.now().isoformat()

            logger.info(f"📬 Enhanced inbox processing completed:")
            logger.info(f"  - Total processed: {results.get('total_processed', 0)}")
            logger.info(f"  - Auto-replied: {results.get('auto_replied', 0)}")  
            logger.info(f"  - High priority leads: {results.get('high_priority', 0)}")
            logger.info(f"  - Hot leads identified: {results.get('leads_identified', 0)}")
            logger.info(f"  - Average lead score: {results.get('summary', {}).get('avg_lead_score', 0):.1f}")

            # Report comprehensive results to dashboard
            self.report_inbox_results_to_dashboard(process_id, results)

            # Keep browser open for manual inspection
            logger.info("✅ Enhanced inbox processing complete. Browser kept open for inspection.")

        except Exception as e:
            logger.error(f"❌ Enhanced inbox processing failed: {e}")
            self.report_inbox_results_to_dashboard(process_id, {
                "success": False, 
                "error": str(e),
                "process_id": process_id
            })
            
    def extract_conversation_details(self, driver) -> Dict[str, Any]:
        """Extract detailed conversation information including participant info"""
        from selenium.webdriver.common.by import By
        
        conversation_details = {}
        # FIX: Removed the incorrect recursive call to itself
        try:
            name_selectors = [".msg-thread-headline__title-text", ".msg-conversation-container__participant-names", ".thread__header-title", "h1.conversation-title"]
            for selector in name_selectors:
                try:
                    name_element = driver.find_element(By.CSS_SELECTOR, selector)
                    conversation_details['participant_name'] = name_element.text.strip()
                    break
                except: continue
            
            headline_selectors = [".msg-thread-headline__subtitle-text", ".msg-conversation-container__participant-headline", ".thread__header-subtitle"]
            for selector in headline_selectors:
                try:
                    headline_element = driver.find_element(By.CSS_SELECTOR, selector)
                    conversation_details['participant_headline'] = headline_element.text.strip()
                    break
                except: continue
            
            info_selectors = [".msg-thread-headline__info-text", ".thread__header-info"]
            for selector in info_selectors:
                try:
                    info_element = driver.find_element(By.CSS_SELECTOR, selector)
                    conversation_details['additional_info'] = info_element.text.strip()
                    break
                except: continue
                    
        except Exception as e:
            logger.error(f"Error extracting conversation details: {e}")

        return conversation_details
    
    def get_complete_conversation_history(self, driver) -> List[Dict[str, str]]:
        """Get the complete conversation history with improved extraction"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        conversation = []
        
        try:
            # Wait for messages to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-s-message-list-content, .msg-thread"))
            )
            
            # Different selectors for messages in different UI versions
            message_selectors = [
                "li.msg-s-message-list__event",  # New UI
                "div.msg-s-event-listitem",      # Alternate new UI
                "li.message",                    # Old UI
                "div.msg-conversation-container__message"  # Another variant
            ]
            
            for selector in message_selectors:
                try:
                    message_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if message_elements:
                        break
                except:
                    continue
            
            for msg_element in message_elements:
                try:
                    # Extract sender name
                    sender_selectors = [
                        ".msg-s-message-group__name",
                        ".msg-s-event-listitem__sender-name",
                        ".message-sender",
                        ".msg-s-message-group__profile-link"
                    ]
                    
                    sender = "Unknown"
                    for s_selector in sender_selectors:
                        try:
                            sender_elem = msg_element.find_element(By.CSS_SELECTOR, s_selector)
                            sender = sender_elem.text.strip()
                            if sender:
                                break
                        except:
                            continue
                    
                    # Check if message is from current user
                    if "you" in sender.lower() or "your" in sender.lower():
                        sender = "You"
                    
                    # Extract message content
                    content_selectors = [
                        ".msg-s-event-listitem__body",
                        ".msg-s-message-group__message",
                        ".message-content",
                        ".msg-s-message-group__bubble"
                    ]
                    
                    content = ""
                    for c_selector in content_selectors:
                        try:
                            content_elem = msg_element.find_element(By.CSS_SELECTOR, c_selector)
                            content = content_elem.text.strip()
                            if content:
                                break
                        except:
                            continue
                    
                    # Extract timestamp if available
                    time_selectors = [
                        ".msg-s-message-group__timestamp",
                        ".msg-s-event-listitem__timestamp",
                        ".message-time"
                    ]
                    
                    timestamp = ""
                    for t_selector in time_selectors:
                        try:
                            time_elem = msg_element.find_element(By.CSS_SELECTOR, t_selector)
                            timestamp = time_elem.text.strip()
                            if timestamp:
                                break
                        except:
                            continue
                    
                    if content:
                        conversation.append({
                            "sender": sender,
                            "message": content,
                            "timestamp": timestamp
                        })
                        
                except Exception as e:
                    logger.debug(f"Error extracting individual message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
        
        return conversation
    
    def process_non_responders(self, campaign_id):
        """
        Checks for contacts who were messaged >3 days ago and haven't replied.
        Extracts email and sends follow-up via Gmail.
        """
        import json
        from datetime import datetime, timedelta

        # 1. Load Campaign Data
        # (Assuming you are tracking campaign state locally or pulling from server)
        # For this example, we'll assume self.active_campaigns holds the state
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            logger.error("Campaign not found")
            return

        driver = self.get_shared_driver()
        
        for contact in campaign.get('contacts_processed', []):
            # Check criteria: Sent message, No Reply, Time elapsed
            last_msg_time = datetime.fromisoformat(contact.get('last_message_time'))
            days_elapsed = (datetime.now() - last_msg_time).days
            
            has_replied = contact.get('has_replied', False) # You need to update this flag from Inbox scanner
            already_emailed = contact.get('emailed', False)

            if not has_replied and not already_emailed and days_elapsed >= 3:
                logger.info(f"📉 No reply from {contact['Name']} after {days_elapsed} days. Attempting email fallback.")
                
                # 1. Extract Email
                email = self.extract_email_from_profile(driver, contact['LinkedIn_profile'])
                
                if email:
                    # 2. Prepare Email Content
                    subject = f"Following up - {contact['Company']}"
                    body = f"Hi {contact['Name'].split()[0]},\n\nI sent you a note on LinkedIn a few days ago regarding {contact['Company']}..."
                    
                    # 3. Send via Gmail (Server API)
                    details = {
                        "to_email": email,
                        "subject": subject,
                        "body": body
                    }
                    
                    result = self.send_email(details)
                    
                    if result.get('success'):
                        logger.info(f"✅ Cold email sent to {email}")
                        contact['emailed'] = True
                        contact['email_sent_time'] = datetime.now().isoformat()
                        # Update database/server state here
                    else:
                        logger.error(f"❌ Failed to send email: {result.get('error')}")
                else:
                    logger.warning(f"Could not find email for {contact['Name']}")

    def send_chat_message(self, driver, message):
        """Types and sends a message in the currently active chat window"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        
        logger.info(f"Sending message: '{message[:50]}...'")
        
        try:
            # Wait for message box to be ready
            message_box_selector = "div.msg-form__contenteditable[role='textbox']"
            message_box = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, message_box_selector))
            )
            
            # Wait for any previous messages to clear
            self.human_delay(1, 2)
            
            # Clear any existing text
            driver.execute_script("arguments[0].innerText = '';", message_box)
            message_box.send_keys(" ")  # Trigger any required events
            self.human_delay(0.5, 1)
            
            # Type message
            self.type_like_human(message_box, message)
            self.human_delay(1, 2)
            
            # Find and click the send button
            send_button = driver.find_element(
                By.CSS_SELECTOR,
                "button.msg-form__send-button[type='submit'], button.msg-form-send-button"
            )
            
            # Ensure button is enabled
            if send_button.is_enabled():
                self.safe_click(driver, send_button)
                logger.info("Message sent successfully.")
                self.human_delay(2, 4)
                return True
            else:
                logger.error("Send button is disabled.")
                return False
                
        except TimeoutException:
            logger.error("Message input box not found or not interactable.")
            return False
        except NoSuchElementException:
            logger.error("Send button not found.")
            return False
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
        
    def navigate_to_messaging(self, driver, retries=3):
        """Navigate to LinkedIn messaging with retries and broader selectors"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        logger.info("📨 Navigating to LinkedIn messaging...")

        for attempt in range(1, retries + 1):
            try:
                driver.get("https://www.linkedin.com/messaging")
                WebDriverWait(driver, 20).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.msg-conversations-container__conversations-list")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.msg-threads")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-conversation-listitem")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "aside.msg-s-message-list-container"))
                    )
                )
                logger.info("✅ Successfully loaded messaging page.")
                self.human_delay(2, 3)
                return True
            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt}/{retries} failed to load messaging: {e}")
                self.human_delay(3, 6)

        logger.error("❌ Failed to load messaging page after retries. Staying on current page.")
        return False
    

    def report_progress_to_dashboard(self, campaign_id, final=False, task_id=None, task_type="outreach_campaign"):
        """Report campaign progress back to dashboard with better error handling"""
        try:
            dashboard_url = self.config.get('dashboard_url')
            if not dashboard_url:
                logger.debug("No dashboard URL configured")
                return

            progress_data = self.active_campaigns.get(campaign_id, {})
            task_id = task_id or progress_data.get('task_id')
            
            # Include current contact info if awaiting confirmation
            if progress_data.get('awaiting_confirmation') and progress_data.get('current_contact_preview'):
                progress_data['awaiting_action'] = True
            
            endpoint = f"{dashboard_url}/api/campaign_progress"
            
            # Add authentication headers
            headers = self._get_auth_headers()
            
            response = requests.post(endpoint, json={
                'campaign_id': campaign_id,
                'progress': progress_data,
                'final': final
            }, headers=headers, timeout=30, verify=True)
            
            if response.status_code == 200:
                logger.debug(f"✅ Successfully reported progress for campaign {campaign_id}")
            else:
                logger.warning(f"⚠️ Dashboard progress report returned status {response.status_code}")
                logger.warning(f"Response text: {response.text}")

            if final:
                logger.info(f"💾 Saving final campaign results for {campaign_id} to database...")
                self.report_task_result({
                    "task_id": task_id or campaign_id,
                    "type": task_type,
                    "success": progress_data.get('status') in ['completed', 'stopped'],
                    "error": progress_data.get('error'),
                    "payload": progress_data,  # Save the entire progress dict as the result
                    "end_time": datetime.now().isoformat()
                })
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ Timeout reporting progress to dashboard for campaign {campaign_id}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ Connection error reporting progress to dashboard for campaign {campaign_id}")
        except Exception as e:
            logger.error(f"Could not report progress for campaign {campaign_id}: {e}")

    def report_search_results_to_dashboard(self, search_id, results):
        """Report search results back to dashboard with better error handling"""
        try:
            dashboard_url = self.config.get('dashboard_url')
            if not dashboard_url:
                return

            endpoint = f"{dashboard_url}/api/search_results"
            
            response = requests.post(endpoint, json={
                'search_id': search_id,
                'results': results
            }, timeout=30, verify=True)
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully reported search results for {search_id}")
            else:
                logger.warning(f"⚠️ Dashboard search report returned status {response.status_code}")

        except Exception as e:
            logger.debug(f"Could not report search results for {search_id}: {e}")



    def get_calendar_slots(self, duration_minutes: int = 30, days_ahead: int = 7) -> List[str]:
        """Fetch available calendar slots from the server."""
        try:
            SERVER_BASE = self.config.get('dashboard_url')
            if not SERVER_BASE:
                logger.warning("No dashboard URL, cannot fetch calendar slots.")
                return []
                
            endpoint = f"{SERVER_BASE.rstrip('/')}/api/google/free-slots"
            params = {'duration_minutes': duration_minutes, 'days_ahead': days_ahead}
            
            resp = requests.get(
                endpoint, 
                headers=self._get_auth_headers(), 
                params=params, 
                timeout=20
            )
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Successfully fetched {len(data.get('slots', []))} free slots.")
                return data.get('slots', [])
            else:
                logger.error(f"Error fetching calendar slots: {resp.status_code} - {resp.text}")
                return []
        except Exception as e:
            logger.error(f"Exception fetching calendar slots: {e}")
            return []

    def book_calendar_event(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Request the server to book a calendar event."""
        try:
            SERVER_BASE = self.config.get('dashboard_url')
            if not SERVER_BASE:
                return {'success': False, 'error': 'No dashboard URL configured'}
                
            endpoint = f"{SERVER_BASE.rstrip('/')}/api/google/book-meeting"
            
            resp = requests.post(
                endpoint, 
                headers=self._get_auth_headers(), 
                json=details, 
                timeout=30
            )
            
            if resp.status_code == 200:
                logger.info("Successfully booked meeting.")
                return resp.json()
            else:
                logger.error(f"Error booking meeting: {resp.status_code} - {resp.text}")
                return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Exception booking meeting: {e}")
            return {'success': False, 'error': str(e)}
    

    def extract_email_from_profile(self, driver, profile_url):
        """
        Navigates to profile, clicks Contact Info, and scrapes email.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import re

        email = None
        try:
            if driver.current_url != profile_url:
                driver.get(profile_url)
                time.sleep(3)

            # Click "Contact info" link
            try:
                contact_info_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "top-card-text-details-contact-info"))
                )
                contact_info_btn.click()
                time.sleep(2)
            except Exception:
                logger.warning("Could not find or click Contact Info button")
                return None

            # Scrape Email from the modal
            try:
                # Look for the email section in the modal
                email_section = driver.find_element(By.CSS_SELECTOR, ".pv-contact-info__contact-type--email")
                email_link = email_section.find_element(By.TAG_NAME, "a")
                email = email_link.text.strip()
                logger.info(f"📧 Extracted email: {email}")
            except Exception:
                logger.info("No email listed in Contact Info")

            # Close modal
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                close_btn.click()
            except:
                driver.find_element(By.TAG_NAME, "body").click()

        except Exception as e:
            logger.error(f"Error extracting email: {e}")

        return email

    def send_email(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Request the server to send an email."""
        try:
            SERVER_BASE = self.config.get('dashboard_url')
            if not SERVER_BASE:
                return {'success': False, 'error': 'No dashboard URL configured'}
                
            endpoint = f"{SERVER_BASE.rstrip('/')}/api/google/send-email"
            
            resp = requests.post(
                endpoint, 
                headers=self._get_auth_headers(), 
                json=details, 
                timeout=30
            )
            
            if resp.status_code == 200:
                logger.info("Successfully sent email.")
                return resp.json()
            else:
                logger.error(f"Error sending email: {resp.status_code} - {resp.text}")
                return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Exception sending email: {e}")
            return {'success': False, 'error': str(e)}
                
    def show_profile_info(self):
        """Show information about the persistent profile"""
        if hasattr(self, 'persistent_profile_dir'):
            profile_size = 0
            try:
                for dirpath, dirnames, filenames in os.walk(self.persistent_profile_dir):
                    for filename in filenames:
                        profile_size += os.path.getsize(os.path.join(dirpath, filename))
                profile_size_mb = profile_size / (1024 * 1024)
                
                logger.info(f"📁 Profile directory: {self.persistent_profile_dir}")
                logger.info(f"💾 Profile size: {profile_size_mb:.1f} MB")
                logger.info("🔄 This profile will be reused for future sessions")
            except Exception as e:
                logger.debug(f"Could not calculate profile size: {e}")

    
    def add_contact_to_hubspot(self, contact):
        """
        Adds a contact to HubSpot CRM when a positive reply is detected.
        Requires 'hubspot_api_key' in client_config.json.
        """
        api_key = self.config.get('hubspot_api_key')
        if not api_key:
            logger.warning("⚠️ HubSpot API key not found in config. Skipping sync.")
            return False

        endpoint = "https://api.hubapi.com/crm/v3/objects/contacts"
        
        # Split name into First/Last
        names = contact.name.split(' ')
        first_name = names[0]
        last_name = ' '.join(names[1:]) if len(names) > 1 else ''

        # Extract email if available in profile_data
        email = contact.profile_data.get('email', '')
        
        # Prepare payload
        properties = {
            "firstname": first_name,
            "lastname": last_name,
            "company": contact.company,
            "jobtitle": contact.title,
            "linkedinbio": contact.linkedin_url, # Standard HubSpot property for LinkedIn
            "lifecyclestage": "lead",            # Mark as Lead
            "lead_status": "New"
        }
        
        # Only add email if we actually found one (avoids validation errors)
        if email:
            properties["email"] = email

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"🚀 Syncing {contact.name} to HubSpot...")
            response = requests.post(endpoint, json={"properties": properties}, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Successfully added {contact.name} to HubSpot as a Lead.")
                return True
            elif response.status_code == 409:
                logger.info(f"⚠️ Contact {contact.name} already exists in HubSpot. (Duplicate)")
                return True
            else:
                logger.error(f"❌ HubSpot Sync Failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error syncing to HubSpot: {e}")
            return False
                
    def _run_flask_app(self):
        """Run Flask app"""
        try:
            self.flask_app.run(
                host='127.0.0.1',
                port=self.config['local_port'],
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"❌ Flask app error: {e}")

    def cleanup_safe(self):
        """Safe cleanup method - DON'T delete persistent profile"""
        try:
            if hasattr(self, 'driver') and self.driver:
                logger.info("🔧 Closing browser (keeping profile for next session)")
                self.driver.quit()
        except Exception as e:
            logger.error(f"Error during driver cleanup: {e}")
        
        # DON'T delete persistent_profile_dir - we want to keep it!
        # Only clean up if it was actually a temp directory
        if hasattr(self, 'temp_profile_dir') and self.temp_profile_dir and os.path.exists(self.temp_profile_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_profile_dir, ignore_errors=True)
                logger.info("🧹 Cleaned up temporary files")
            except Exception as e:
                logger.error(f"Error during temp cleanup: {e}")

    def cleanup(self):
        """Cleanup resources"""
        self.running = False

        # Close any active automation instances
        for automation in self.automation_instances.values():
            try:
                automation.close()
            except:
                pass
