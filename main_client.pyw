import json
import time
import threading
import csv
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import os
from linkedin_automation import LinkedInAutomation
import logging
import uuid
from collections import defaultdict
from tkinter import ttk, messagebox, scrolledtext
import signal
import atexit
import random
import google.generativeai as genai
import re
from typing import List, Dict, Any
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional
# Import all functions from LinkedIn_automation_script.py
from urllib.parse import quote_plus
import tempfile
import platform
import shutil
from typing import List, Dict, Any
import sys
from client_logic import EnhancedLinkedInAutomationClient
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure logging
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler(sys.stdout),
        logging.FileHandler('client.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)



def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown"""
    logger.info("🛑 Received shutdown signal")
    sys.exit(0)

def main():
    """Main entry point with enhanced error handling and heartbeat"""
    import signal
    import atexit
    from tkinter import Tk, Label, Button, messagebox, StringVar

    client = None
    status_var = None

    def update_status_display():
        """Update status display in GUI"""
        if client and status_var:
            if client._stop_polling:
                status_var.set("❌ Client stopped")
            elif getattr(client, '_polling_thread', None) and client._polling_thread.is_alive():
                status_var.set("✅ Client running - polling for tasks")
            else:
                status_var.set("⚠️ Client starting...")

    def on_close():
        """Handle window close"""
        if client:
            client.stop_polling()
        root.destroy()

    def signal_handler(sig, frame):
        """Handle system signals"""
        if client:
            client.stop_polling()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start client with enhanced features
        client = EnhancedLinkedInAutomationClient()
        atexit.register(client.cleanup)

        logger.info("🚀 Starting Enhanced LinkedIn Automation Client")

        # Build GUI with status updates
        root = Tk()
        root.title("LinkedIn Automation Client")
        root.geometry("400x200")

        status_var = StringVar()
        status_var.set("⏳ Initializing...")

        Label(root, textvariable=status_var, padx=20, pady=20, font=('Arial', 12)).pack()
        Button(root, text="Quit", command=on_close, font=('Arial', 10)).pack(pady=10)

        # Update status periodically
        def periodic_status_update():
            update_status_display()
            root.after(2000, periodic_status_update)  # Update every 2 seconds

        root.after(1000, periodic_status_update)
        root.protocol("WM_DELETE_WINDOW", on_close)

        # Start the GUI
        root.mainloop()

    except KeyboardInterrupt:
        logger.info("👋 Client stopped by user")
    except Exception as e:
        logger.error(f"❌ Client error: {e}", exc_info=True)
        if 'messagebox' in locals():
            messagebox.showerror("Client Error", f"Error: {str(e)}")
    finally:
        if client:
            client.stop_polling()
        logger.info("🔚 Client application terminated")


if __name__ == "__main__":
    main()
