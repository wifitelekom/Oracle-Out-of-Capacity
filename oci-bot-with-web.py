#!/usr/bin/env python3
"""
OCI OCC Fix Bot with Integrated Web Dashboard
Complete solution for OCI instance creation with web monitoring
"""

import oci
import logging
import time
import sys
import os
import telebot
import datetime
import configparser
import json
import threading
import secrets
import hashlib
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional, List, Any
from functools import wraps

# Flask imports - optional
try:
    from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Warning: Flask not installed. Web dashboard disabled.")
    print("Install with: pip install flask flask-cors")

# Constants
CONFIG_FILE = 'configuration.ini'
LOG_FILE = 'oci_occ.log'
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3

# Global variables for web dashboard
app = None
dashboard_data = {
    'bot_status': 'stopped',
    'start_time': None,
    'total_attempts': 0,
    'last_attempt_time': None,
    'last_error': None,
    'current_ad': None,
    'retry_interval': 0,
    'instances_created': [],
    'logs': [],
    'statistics': {
        'success_rate': 0,
        'errors_by_type': {}
    }
}

# HTML Templates
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCI Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .dashboard-container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
            margin: 30px auto;
            max-width: 1400px;
        }
        .status-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .status-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }
        .status-running {
            border-left: 5px solid #28a745;
            background: linear-gradient(90deg, rgba(40,167,69,0.1) 0%, rgba(255,255,255,1) 10%);
        }
        .status-stopped {
            border-left: 5px solid #dc3545;
            background: linear-gradient(90deg, rgba(220,53,69,0.1) 0%, rgba(255,255,255,1) 10%);
        }
        .metric-box {
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .metric-box:hover {
            transform: scale(1.05);
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .metric-label {
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .log-container {
            background: #1e1e1e;
            color: #d4d4d4;
            border-radius: 10px;
            padding: 20px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
        }
        .log-entry {
            padding: 5px 10px;
            margin: 2px 0;
            border-radius: 3px;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        .log-INFO { 
            background: rgba(13, 202, 240, 0.2);
            border-left: 3px solid #0dcaf0;
        }
        .log-WARNING { 
            background: rgba(255, 193, 7, 0.2);
            border-left: 3px solid #ffc107;
        }
        .log-ERROR { 
            background: rgba(220, 53, 69, 0.2);
            border-left: 3px solid #dc3545;
        }
        .control-btn {
            margin: 5px;
            min-width: 120px;
            border-radius: 25px;
            padding: 10px 25px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .control-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .status-indicator {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(40, 167, 69, 0); }
            100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); }
        }
        .status-indicator.running {
            background: #28a745;
        }
        .status-indicator.stopped {
            background: #dc3545;
            animation: none;
        }
        .header-title {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: bold;
        }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .refresh-btn:hover {
            transform: rotate(180deg) scale(1.1);
        }
        .config-item {
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        .config-label {
            font-weight: 600;
            color: #495057;
        }
        .config-value {
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container dashboard-container">
        <!-- Header -->
        <div class="row mb-4">
            <div class="col-md-12">
                <h1 class="header-title">
                    <i class="fas fa-cloud"></i> OCI Bot Dashboard
                </h1>
            </div>
        </div>
        
        <!-- Status Overview -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="status-card" id="main-status">
                    <h4>
                        <span class="status-indicator stopped" id="status-indicator"></span>
                        Bot Status: <span id="bot-status" class="text-danger">Stopped</span>
                    </h4>
                    <div class="row mt-3">
                        <div class="col-md-3">
                            <small class="text-muted">Started:</small><br>
                            <strong id="start-time">-</strong>
                        </div>
                        <div class="col-md-3">
                            <small class="text-muted">Current AD:</small><br>
                            <strong id="current-ad">-</strong>
                        </div>
                        <div class="col-md-3">
                            <small class="text-muted">Retry Interval:</small><br>
                            <strong><span id="retry-interval">-</span>s</strong>
                        </div>
                        <div class="col-md-3">
                            <small class="text-muted">Last Error:</small><br>
                            <strong id="last-error" class="text-danger">-</strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Metrics -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="metric-box">
                    <i class="fas fa-sync-alt fa-2x text-primary mb-3"></i>
                    <div class="metric-value" id="total-attempts">0</div>
                    <div class="metric-label">Total Attempts</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-box">
                    <i class="fas fa-server fa-2x text-success mb-3"></i>
                    <div class="metric-value" id="instances-created">0</div>
                    <div class="metric-label">Instances Created</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-box">
                    <i class="fas fa-chart-line fa-2x text-info mb-3"></i>
                    <div class="metric-value" id="success-rate">0%</div>
                    <div class="metric-label">Success Rate</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-box">
                    <i class="fas fa-clock fa-2x text-warning mb-3"></i>
                    <div class="metric-value" id="uptime">0h</div>
                    <div class="metric-label">Uptime</div>
                </div>
            </div>
        </div>
        
        <!-- Control and Config -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="status-card">
                    <h5><i class="fas fa-gamepad"></i> Control Panel</h5>
                    <div class="mt-3">
                        <button class="btn btn-success control-btn" onclick="controlBot('start')">
                            <i class="fas fa-play"></i> Start
                        </button>
                        <button class="btn btn-danger control-btn" onclick="controlBot('stop')">
                            <i class="fas fa-stop"></i> Stop
                        </button>
                        <button class="btn btn-warning control-btn" onclick="controlBot('restart')">
                            <i class="fas fa-redo"></i> Restart
                        </button>
                    </div>
                    <div class="mt-3">
                        <small class="text-muted">
                            <i class="fas fa-info-circle"></i> 
                            Use these controls to manage the bot lifecycle
                        </small>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="status-card">
                    <h5><i class="fas fa-cog"></i> Configuration</h5>
                    <div class="mt-3" id="config-info">
                        <div class="config-item">
                            <span class="config-label">Shape:</span>
                            <span class="config-value" id="config-shape">-</span>
                        </div>
                        <div class="config-item">
                            <span class="config-label">Type:</span>
                            <span class="config-value" id="config-type">-</span>
                        </div>
                        <div class="config-item">
                            <span class="config-label">OCPUs:</span>
                            <span class="config-value" id="config-ocpus">-</span>
                        </div>
                        <div class="config-item">
                            <span class="config-label">Memory:</span>
                            <span class="config-value" id="config-memory">-</span> GB
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Error Statistics -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="status-card">
                    <h5><i class="fas fa-chart-bar"></i> Error Statistics</h5>
                    <div class="row mt-3" id="error-stats">
                        <div class="col-md-12 text-center text-muted">
                            No errors recorded yet
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="row">
            <div class="col-md-12">
                <div class="status-card">
                    <h5><i class="fas fa-terminal"></i> Live Logs</h5>
                    <div class="log-container" id="log-container">
                        <div class="text-muted">Waiting for logs...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Refresh Button -->
    <button class="refresh-btn" onclick="refreshData()">
        <i class="fas fa-sync-alt"></i>
    </button>
    
    <script>
        let autoRefresh = true;
        let refreshInterval = null;
        
        // Load configuration
        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                const config = await response.json();
                
                document.getElementById('config-shape').textContent = config.machine.shape || '-';
                document.getElementById('config-type').textContent = config.machine.type || '-';
                document.getElementById('config-ocpus').textContent = config.machine.ocpus || '-';
                document.getElementById('config-memory').textContent = config.machine.memory || '-';
            } catch (error) {
                console.error('Failed to load config:', error);
            }
        }
        
        // Refresh data
        async function refreshData() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateUI(data);
            } catch (error) {
                console.error('Failed to refresh data:', error);
            }
        }
        
        // Update UI
        function updateUI(data) {
            // Update status
            const statusElem = document.getElementById('bot-status');
            const indicatorElem = document.getElementById('status-indicator');
            const mainStatusCard = document.getElementById('main-status');
            
            if (data.bot_status === 'running') {
                statusElem.textContent = 'Running';
                statusElem.className = 'text-success';
                indicatorElem.className = 'status-indicator running';
                mainStatusCard.className = 'status-card status-running';
            } else {
                statusElem.textContent = 'Stopped';
                statusElem.className = 'text-danger';
                indicatorElem.className = 'status-indicator stopped';
                mainStatusCard.className = 'status-card status-stopped';
            }
            
            // Update metrics
            document.getElementById('total-attempts').textContent = data.total_attempts || 0;
            document.getElementById('instances-created').textContent = (data.instances_created || []).length;
            document.getElementById('success-rate').textContent = 
                ((data.statistics?.success_rate || 0).toFixed(1)) + '%';
            
            // Update info
            document.getElementById('start-time').textContent = 
                data.start_time ? new Date(data.start_time).toLocaleString() : '-';
            document.getElementById('current-ad').textContent = data.current_ad || '-';
            document.getElementById('retry-interval').textContent = 
                data.retry_interval ? data.retry_interval.toFixed(1) : '-';
            document.getElementById('last-error').textContent = data.last_error || '-';
            
            // Calculate uptime
            if (data.start_time && data.bot_status === 'running') {
                const uptime = Date.now() - new Date(data.start_time).getTime();
                const hours = Math.floor(uptime / 3600000);
                const minutes = Math.floor((uptime % 3600000) / 60000);
                document.getElementById('uptime').textContent = hours + 'h ' + minutes + 'm';
            } else {
                document.getElementById('uptime').textContent = '0h';
            }
            
            // Update error statistics
            if (data.statistics && data.statistics.errors_by_type) {
                const errorStats = document.getElementById('error-stats');
                const errors = data.statistics.errors_by_type;
                
                if (Object.keys(errors).length > 0) {
                    let html = '';
                    for (const [error, count] of Object.entries(errors)) {
                        html += `
                            <div class="col-md-3 mb-2">
                                <div class="text-center">
                                    <strong>${error}</strong><br>
                                    <span class="badge bg-danger">${count}</span>
                                </div>
                            </div>
                        `;
                    }
                    errorStats.innerHTML = html;
                }
            }
            
            // Update logs
            if (data.logs && data.logs.length > 0) {
                const logContainer = document.getElementById('log-container');
                logContainer.innerHTML = '';
                
                // Show last 50 logs
                const recentLogs = data.logs.slice(-50);
                recentLogs.forEach(log => {
                    const entry = document.createElement('div');
                    entry.className = 'log-entry log-' + log.level;
                    const timestamp = new Date(log.timestamp).toLocaleTimeString();
                    entry.textContent = '[' + timestamp + '] [' + log.level + '] ' + log.message;
                    logContainer.appendChild(entry);
                });
                
                // Auto-scroll to bottom
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }
        
        // Control bot
        async function controlBot(action) {
            if (!confirm('Are you sure you want to ' + action + ' the bot?')) {
                return;
            }
            
            try {
                const response = await fetch('/api/control/' + action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert('Bot ' + action + ' command sent successfully');
                    setTimeout(refreshData, 1000);
                } else {
                    alert('Error: ' + (result.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            loadConfig();
            refreshData();
            
            // Auto-refresh every 5 seconds
            refreshInterval = setInterval(refreshData, 5000);
        });
    </script>
</body>
</html>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCI Bot Dashboard - Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 400px;
            width: 100%;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header i {
            font-size: 48px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
        }
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .btn-login {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
            padding: 12px;
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <i class="fas fa-cloud"></i>
            <h3>OCI Bot Dashboard</h3>
            <p class="text-muted">Please login to continue</p>
        </div>
        
        {% if error %}
        <div class="alert alert-danger" role="alert">
            <i class="fas fa-exclamation-circle"></i> {{ error }}
        </div>
        {% endif %}
        
        <form method="POST">
            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <div class="input-group">
                    <span class="input-group-text"><i class="fas fa-user"></i></span>
                    <input type="text" class="form-control" id="username" name="username" required autofocus>
                </div>
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <div class="input-group">
                    <span class="input-group-text"><i class="fas fa-lock"></i></span>
                    <input type="password" class="form-control" id="password" name="password" required>
                </div>
            </div>
            <button type="submit" class="btn btn-login w-100">
                <i class="fas fa-sign-in-alt"></i> Login
            </button>
        </form>
    </div>
</body>
</html>
'''

class OciOccFix:
    def __init__(self):
        """Initialize OCI OCC Fix bot with proper configuration"""
        try:
            # Phase 1: Core configuration
            self.config = self.load_config()
            self.setup_logging()
            
            # Phase 2: Initialize critical parameters
            try:
                self.wait_seconds = float(self.config.get('Retry', 'initial_retry_interval'))
            except:
                self.wait_seconds = 1.0
            
            # Phase 3: Service clients (OCI config from INI file)
            self.clients = self.initialize_oci_clients()
            
            # Phase 4: Telegram integration
            self.tg_message_id = None
            try:
                self.tg_chat_id = self.config.get('Telegram', 'uid')
            except:
                self.tg_chat_id = ''
            self.tg_bot = self.initialize_telegram()
            
            # Phase 5: Runtime state
            self.total_retries = 0
            self.retry_counter = 0
            self.last_error_code = None
            self.start_time = None
            self.current_ad = None
            self.instances_created = []
            self.is_running = False
            
            # Phase 6: Web Dashboard
            dashboard_enabled = False
            try:
                dashboard_enabled = self.config.get('Dashboard', 'enabled').lower() == 'true'
            except:
                pass
            
            if FLASK_AVAILABLE and dashboard_enabled:
                self.initialize_web_dashboard()
            
            logging.info("✅ OCI OCC Fix bot initialized successfully")
            
            # Test Telegram connection
            if self.tg_bot and self.tg_chat_id:
                try:
                    self.tg_bot.send_message(
                        chat_id=self.tg_chat_id,
                        text="🤖 OCI Bot başlatıldı ve hazır!",
                        parse_mode='HTML'
                    )
                    logging.info("✅ Telegram test mesajı gönderildi")
                except Exception as e:
                    logging.warning(f"Telegram test mesajı gönderilemedi: {e}")
            
        except Exception as e:
            logging.critical(f"Failed to initialize bot: {str(e)}")
            raise

    @staticmethod
    def load_config() -> configparser.ConfigParser:
        """Load and validate configuration from INI file"""
        config = configparser.ConfigParser()
        
        if not Path(CONFIG_FILE).exists():
            raise FileNotFoundError(f"Configuration file {CONFIG_FILE} not found")
        
        config.read(CONFIG_FILE, encoding='utf-8')
        
        # Validate required sections
        required_sections = ['OCI', 'Instance', 'Telegram', 'Machine', 'Retry']
        missing_sections = [s for s in required_sections if not config.has_section(s)]
        
        if missing_sections:
            raise ValueError(f"Missing required sections: {', '.join(missing_sections)}")

        return config

    def setup_logging(self):
        """Configure logging with rotation and proper formatting"""
        # Get log directory, with fallback
        try:
            log_dir = self.config.get('Logging', 'log_directory')
        except (configparser.NoSectionError, configparser.NoOptionError):
            log_dir = 'logs'
        
        Path(log_dir).mkdir(exist_ok=True)
        
        log_file_path = Path(log_dir) / LOG_FILE
        
        # Get log level with fallback
        try:
            log_level = self.config.get('Logging', 'log_level').upper()
        except (configparser.NoSectionError, configparser.NoOptionError):
            log_level = 'INFO'  # Default to INFO level
        
        formatter = logging.Formatter(
            '[%(levelname)s] %(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=MAX_LOG_SIZE,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    def initialize_web_dashboard(self):
        """Initialize Flask web dashboard"""
        global app
        app = Flask(__name__)
        app.config['SECRET_KEY'] = secrets.token_hex(32)
        CORS(app)
        
        # Store bot instance reference
        app.bot_instance = self
        
        # Setup routes
        self.setup_web_routes()
        
        # Start Flask in background thread
        dashboard_thread = threading.Thread(target=self.run_flask_app)
        dashboard_thread.daemon = True
        dashboard_thread.start()
        
        try:
            dashboard_host = self.config.get('Dashboard', 'host')
        except:
            dashboard_host = '0.0.0.0'
        
        try:
            dashboard_port = int(self.config.get('Dashboard', 'port'))
        except:
            dashboard_port = 5000
        
        dashboard_url = f"http://{dashboard_host}:{dashboard_port}"
        logging.info(f"✅ Web dashboard started at {dashboard_url}")
        
        try:
            username = self.config.get('Dashboard', 'username')
        except:
            username = 'admin'
        
        try:
            password = self.config.get('Dashboard', 'password')
        except:
            password = 'admin123'
        
        print(f"\n{'='*50}")
        print(f"🌐 Web Dashboard: {dashboard_url}")
        print(f"👤 Username: {username}")
        print(f"🔑 Password: {password}")
        print(f"{'='*50}\n")

    def setup_web_routes(self):
        """Setup Flask routes"""
        
        @app.route('/')
        def index():
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            return render_template_string(DASHBOARD_HTML)
        
        @app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                config_username = app.bot_instance.config.get('Dashboard', 'username', fallback='admin')
                config_password = app.bot_instance.config.get('Dashboard', 'password', fallback='admin123')
                
                if username == config_username and password == config_password:
                    session['logged_in'] = True
                    return redirect(url_for('index'))
                else:
                    return render_template_string(LOGIN_HTML, error='Invalid credentials')
            
            return render_template_string(LOGIN_HTML)
        
        @app.route('/logout')
        def logout():
            session.pop('logged_in', None)
            return redirect(url_for('login'))
        
        @app.route('/api/status')
        def api_status():
            return jsonify(dashboard_data)
        
        @app.route('/api/config')
        def api_config():
            safe_config = {
                'machine': {
                    'shape': app.bot_instance.config.get('Machine', 'shape', fallback=''),
                    'type': app.bot_instance.config.get('Machine', 'type', fallback=''),
                    'ocpus': app.bot_instance.config.get('Machine', 'ocpus', fallback=''),
                    'memory': app.bot_instance.config.get('Machine', 'memory', fallback='')
                },
                'instance': {
                    'display_name': app.bot_instance.config.get('Instance', 'display_name', fallback=''),
                    'boot_volume_size': app.bot_instance.config.get('Instance', 'boot_volume_size', fallback='')
                },
                'region': app.bot_instance.config.get('DEFAULT', 'region', fallback='')
            }
            return jsonify(safe_config)
        
        @app.route('/api/control/<action>', methods=['POST'])
        def api_control(action):
            if not session.get('logged_in'):
                return jsonify({'error': 'Unauthorized'}), 401
            
            if action == 'start':
                if not app.bot_instance.is_running:
                    thread = threading.Thread(target=app.bot_instance.run)
                    thread.daemon = True
                    thread.start()
                    return jsonify({'status': 'started'})
                else:
                    return jsonify({'error': 'Bot is already running'}), 400
            
            elif action == 'stop':
                app.bot_instance.is_running = False
                dashboard_data['bot_status'] = 'stopped'
                return jsonify({'status': 'stopped'})
            
            elif action == 'restart':
                app.bot_instance.is_running = False
                time.sleep(2)
                thread = threading.Thread(target=app.bot_instance.run)
                thread.daemon = True
                thread.start()
                return jsonify({'status': 'restarting'})
            
            return jsonify({'error': 'Invalid action'}), 400

    def run_flask_app(self):
        """Run Flask application"""
        try:
            host = self.config.get('Dashboard', 'host')
        except:
            host = '0.0.0.0'
        
        try:
            port = int(self.config.get('Dashboard', 'port'))
        except:
            port = 5000
        
        app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False
        )

    def update_dashboard(self, **kwargs):
        """Update dashboard data"""
        dashboard_data.update(kwargs)
        
        # Update statistics
        if self.total_retries > 0:
            success_rate = (len(self.instances_created) / self.total_retries) * 100
            dashboard_data['statistics']['success_rate'] = success_rate

    def add_dashboard_log(self, level: str, message: str):
        """Add log entry to dashboard"""
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        
        dashboard_data['logs'].append(log_entry)
        
        # Keep only last 200 logs
        if len(dashboard_data['logs']) > 200:
            dashboard_data['logs'] = dashboard_data['logs'][-200:]

    def initialize_oci_clients(self) -> Dict[str, Any]:
        """Initialize OCI service clients using configuration from INI file"""
        try:
            oci_config = self.build_oci_config()
            oci.config.validate_config(oci_config)
            
            clients = {
                'compute': oci.core.ComputeClient(oci_config),
                'identity': oci.identity.IdentityClient(oci_config),
                'network': oci.core.VirtualNetworkClient(oci_config),
                'blockstorage': oci.core.BlockstorageClient(oci_config)
            }
            
            logging.info("OCI clients initialized successfully")
            return clients
            
        except Exception as e:
            logging.error(f"Failed to initialize OCI clients: {str(e)}")
            raise

    def build_oci_config(self) -> dict:
        """Build OCI configuration dictionary from INI file"""
        try:
            # Try to read from DEFAULT section (ConfigParser default behavior)
            oci_config = {}
            
            # Check for OCI credentials in DEFAULT section or root level
            required_keys = ['user', 'fingerprint', 'key_file', 'tenancy', 'region']
            
            # Try DEFAULT section first
            for key in required_keys:
                try:
                    value = self.config.get('DEFAULT', key)
                    if value:
                        oci_config[key] = value
                except (configparser.NoSectionError, configparser.NoOptionError):
                    pass
            
            # If not all keys found, try without section
            if len(oci_config) != len(required_keys):
                oci_config = {}
                for key in required_keys:
                    for section in self.config.sections() + ['DEFAULT']:
                        try:
                            value = self.config.get(section, key)
                            if value and key not in oci_config:
                                oci_config[key] = value
                                break
                        except (configparser.NoSectionError, configparser.NoOptionError):
                            continue
            
            # Validate we have all required keys
            missing_keys = [k for k in required_keys if k not in oci_config]
            if missing_keys:
                # Log current configuration for debugging
                logging.error(f"Missing OCI keys: {missing_keys}")
                logging.error(f"Available sections: {self.config.sections()}")
                
                # Try to show what's in DEFAULT section
                if self.config.defaults():
                    logging.info(f"DEFAULT section keys: {list(self.config.defaults().keys())}")
                
                raise ValueError(f"Missing required OCI configuration keys: {', '.join(missing_keys)}")
            
            # Validate and expand key file path
            key_file = Path(oci_config['key_file']).expanduser()
            if not key_file.exists():
                # Try absolute path
                if not key_file.is_absolute():
                    # Try relative to current directory
                    key_file = Path.cwd() / oci_config['key_file']
                    if not key_file.exists():
                        raise FileNotFoundError(f"OCI key file not found: {oci_config['key_file']}")
            
            oci_config['key_file'] = str(key_file)
            
            logging.info(f"OCI config loaded - Region: {oci_config['region']}, User: {oci_config['user'][:20]}...")
            return oci_config
            
        except Exception as e:
            logging.error(f"Failed to build OCI configuration: {str(e)}")
            raise

    def initialize_telegram(self) -> Optional[telebot.TeleBot]:
        """Initialize Telegram bot if configured"""
        try:
            bot_token = self.config.get('Telegram', 'bot_token')
        except (configparser.NoSectionError, configparser.NoOptionError):
            bot_token = ''
        
        try:
            chat_id = self.config.get('Telegram', 'uid')
        except (configparser.NoSectionError, configparser.NoOptionError):
            chat_id = ''
        
        if not bot_token or bot_token == 'xxxx':
            logging.info("Telegram bot token not configured")
            return None
            
        if not chat_id or chat_id == 'xxxx':
            logging.info("Telegram chat ID not configured")
            return None
            
        try:
            bot = telebot.TeleBot(bot_token, parse_mode='HTML')
            bot.get_me()
            self.tg_chat_id = chat_id
            logging.info("Telegram bot initialized successfully")
            return bot
        except Exception as e:
            logging.warning(f"Failed to initialize Telegram bot: {str(e)}")
            return None

    # TELEGRAM NOTIFICATION FUNCTIONS - YENİ EKLENDİ
    def send_telegram_message(self, message: str, update_existing: bool = False):
        """Send or update Telegram message"""
        if not self.tg_bot or not self.tg_chat_id:
            return
        
        try:
            # HTML formatında mesaj
            formatted_message = f"🤖 <b>OCI Bot Status</b>\n\n{message}"
            
            if update_existing and self.tg_message_id:
                # Mevcut mesajı güncelle
                self.tg_bot.edit_message_text(
                    chat_id=self.tg_chat_id,
                    message_id=self.tg_message_id,
                    text=formatted_message,
                    parse_mode='HTML'
                )
            else:
                # Yeni mesaj gönder
                msg = self.tg_bot.send_message(
                    chat_id=self.tg_chat_id,
                    text=formatted_message,
                    parse_mode='HTML'
                )
                self.tg_message_id = msg.message_id
                
        except Exception as e:
            logging.warning(f"Failed to send Telegram message: {str(e)}")

    def format_status_message(self) -> str:
        """Format status message for Telegram"""
        uptime = datetime.datetime.now() - self.start_time if self.start_time else datetime.timedelta(0)
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        
        message = f"""📊 <b>Statistics:</b>
• Total Attempts: {self.total_retries}
• Current AD: {self.current_ad or 'N/A'}
• Retry Interval: {self.wait_seconds:.1f}s
• Uptime: {hours}h {minutes}m

🔄 <b>Last Error:</b> {self.last_error_code or 'None'}
✅ <b>Instances Created:</b> {len(self.instances_created)}
"""
        
        if self.instances_created:
            message += "\n📝 <b>Instance IDs:</b>\n"
            for instance_id in self.instances_created[-3:]:  # Son 3 instance
                message += f"• <code>{instance_id}</code>\n"
        
        return message

    def send_periodic_update(self):
        """Send periodic status update to Telegram"""
        try:
            update_interval = int(self.config.get('Telegram', 'update_interval', fallback=10))
        except:
            update_interval = 10
        
        if self.total_retries % update_interval == 0 and self.total_retries > 0:
            self.send_telegram_message(self.format_status_message(), update_existing=True)

    def create_instance(self, availability_domain: str) -> Optional[str]:
        """Attempt to create an instance"""
        try:
            self.current_ad = availability_domain
            self.update_dashboard(
                current_ad=availability_domain,
                retry_interval=self.wait_seconds
            )
            
            launch_details = self.build_launch_details(availability_domain)
            
            logging.info(f"Attempting to create instance in {availability_domain}")
            self.add_dashboard_log('INFO', f"Attempting to create instance in {availability_domain}")
            
            response = self.clients['compute'].launch_instance(
                launch_instance_details=launch_details
            )
            
            instance_id = response.data.id
            logging.info(f"✅ Instance created successfully: {instance_id}")
            self.add_dashboard_log('INFO', f"Instance created: {instance_id}")
            
            self.instances_created.append(instance_id)
            self.update_dashboard(instances_created=self.instances_created)
            
            # TELEGRAM BAŞARI BİLDİRİMİ - YENİ EKLENDİ
            success_message = f"""
🎉 <b>SUCCESS!</b> 🎉

✅ Instance created successfully!

📋 <b>Details:</b>
• Instance ID: <code>{instance_id}</code>
• AD: {availability_domain}
• Shape: {self.config.get('Machine', 'shape')}
• Display Name: {self.config.get('Instance', 'display_name')}
• Total Attempts: {self.total_retries}

⏱ Time taken: {datetime.datetime.now() - self.start_time if self.start_time else 'N/A'}
"""
            self.send_telegram_message(success_message)
            
            return instance_id
            
        except oci.exceptions.ServiceError as e:
            self.last_error_code = e.code
            
            # Check if it's actually "Out of host capacity" disguised as InternalError
            if e.code == 'InternalError' and 'Out of host capacity' in str(e.message):
                # This is actually an out of capacity error
                self.last_error_code = 'OutOfHostCapacity'
                
                if 'OutOfHostCapacity' in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type']['OutOfHostCapacity'] += 1
                else:
                    dashboard_data['statistics']['errors_by_type']['OutOfHostCapacity'] = 1
                
                self.update_dashboard(last_error='OutOfHostCapacity')
                
                # Don't log as warning, this is expected
                logging.debug(f"Out of capacity in {availability_domain}")
                self.add_dashboard_log('INFO', f"Out of capacity in {availability_domain}")
                
            elif e.code == 'InternalError':
                # Real internal error (not capacity related)
                if e.code in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type'][e.code] += 1
                else:
                    dashboard_data['statistics']['errors_by_type'][e.code] = 1
                
                self.update_dashboard(last_error=e.code)
                
                logging.warning(f"Internal error in {availability_domain}")
                logging.debug(f"Full error message: {e.message}")
                logging.debug(f"Request ID: {e.request_id if hasattr(e, 'request_id') else 'N/A'}")
                self.add_dashboard_log('WARNING', f"Internal error (not capacity related)")
                
            elif e.code in ['OutOfCapacity', 'OutOfBareMetalCapacity', 'OutOfHostCapacity']:
                if e.code in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type'][e.code] += 1
                else:
                    dashboard_data['statistics']['errors_by_type'][e.code] = 1
                
                self.update_dashboard(last_error=e.code)
                
                logging.debug(f"Out of capacity in {availability_domain}")
                self.add_dashboard_log('INFO', f"Out of capacity in {availability_domain}")
                
            elif e.code == 'TooManyRequests':
                if e.code in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type'][e.code] += 1
                else:
                    dashboard_data['statistics']['errors_by_type'][e.code] = 1
                
                self.update_dashboard(last_error=e.code)
                
                logging.warning(f"Too many requests - slowing down")
                self.add_dashboard_log('WARNING', "Too many requests - slowing down")
                
            elif e.code == 'LimitExceeded':
                if e.code in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type'][e.code] += 1
                else:
                    dashboard_data['statistics']['errors_by_type'][e.code] = 1
                
                self.update_dashboard(last_error=e.code)
                
                logging.error(f"Limit exceeded: {e.message}")
                self.add_dashboard_log('ERROR', f"Limit exceeded - check your quotas")
                
                # TELEGRAM KRİTİK HATA BİLDİRİMİ - YENİ EKLENDİ
                error_msg = f"""
⚠️ <b>Critical Error!</b>

❌ Error Code: {e.code}
📝 Message: {e.message}

🔧 Bot may need configuration check!
"""
                self.send_telegram_message(error_msg)
                
            elif e.code == 'InvalidParameter':
                if e.code in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type'][e.code] += 1
                else:
                    dashboard_data['statistics']['errors_by_type'][e.code] = 1
                
                self.update_dashboard(last_error=e.code)
                
                logging.error(f"Invalid parameter: {e.message}")
                self.add_dashboard_log('ERROR', f"Invalid parameter in request")
                
                # TELEGRAM KRİTİK HATA BİLDİRİMİ - YENİ EKLENDİ
                error_msg = f"""
⚠️ <b>Critical Error!</b>

❌ Error Code: {e.code}
📝 Message: {e.message}

🔧 Bot may need configuration check!
"""
                self.send_telegram_message(error_msg)
                
            else:
                if e.code in dashboard_data['statistics']['errors_by_type']:
                    dashboard_data['statistics']['errors_by_type'][e.code] += 1
                else:
                    dashboard_data['statistics']['errors_by_type'][e.code] = 1
                
                self.update_dashboard(last_error=e.code)
                
                logging.warning(f"Service error in {availability_domain}: {e.code} - {e.message}")
                self.add_dashboard_log('WARNING', f"Service error: {e.code}")
            
            return None
            
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            logging.error(f"Error type: {type(e).__name__}")
            self.add_dashboard_log('ERROR', f"Unexpected error: {str(e)}")
            return None

    def build_launch_details(self, availability_domain: str):
        """Build instance launch configuration"""
        try:
            # Get and validate SSH keys
            ssh_keys = self.config.get('Instance', 'ssh_keys').strip()
            
            if not ssh_keys or ssh_keys == 'xxxx':
                raise ValueError("SSH keys not configured properly")
            
            # If ssh_keys starts with 'file:', read from file
            if ssh_keys.startswith('file:'):
                ssh_key_file = ssh_keys.replace('file:', '').strip()
                ssh_key_path = Path(ssh_key_file).expanduser()
                if ssh_key_path.exists():
                    with open(ssh_key_path, 'r') as f:
                        ssh_keys = f.read().strip()
                else:
                    logging.error(f"SSH key file not found: {ssh_key_file}")
                    raise FileNotFoundError(f"SSH key file not found: {ssh_key_file}")
            
            # Validate SSH key format
            if not ssh_keys.startswith(('ssh-rsa', 'ssh-ed25519', 'ecdsa-sha2')):
                logging.error("Invalid SSH key format")
                raise ValueError("SSH key must start with ssh-rsa, ssh-ed25519, or ecdsa-sha2")
            
            # Clean up availability domain
            ad_clean = availability_domain.strip()
            
            # Log configuration for debugging
            logging.debug(f"Building launch config:")
            logging.debug(f"  AD: {ad_clean}")
            logging.debug(f"  Compartment: {self.config.get('OCI', 'compartment_id')[:30]}...")
            logging.debug(f"  Shape: {self.config.get('Machine', 'shape')}")
            logging.debug(f"  Subnet: {self.config.get('OCI', 'subnet_id')[:30]}...")
            
            # Get assign_public_ip setting
            try:
                assign_public_ip = self.config.get('Instance', 'assign_public_ip').lower() == 'true'
            except:
                assign_public_ip = True
            
            # Build launch details
            launch_details = oci.core.models.LaunchInstanceDetails(
                metadata={
                    "ssh_authorized_keys": ssh_keys
                },
                availability_domain=ad_clean,
                compartment_id=self.config.get('OCI', 'compartment_id').strip(),
                shape=self.config.get('Machine', 'shape').strip(),
                display_name=self.config.get('Instance', 'display_name').strip(),
                source_details=self.get_source_details(),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=self.config.get('OCI', 'subnet_id').strip(),
                    assign_public_ip=assign_public_ip
                )
            )
            
            # Add shape configuration for flexible shapes
            if "Flex" in self.config.get('Machine', 'shape'):
                ocpus = float(self.config.get('Machine', 'ocpus'))
                memory = float(self.config.get('Machine', 'memory'))
                
                # Validate ARM limits
                machine_type = self.config.get('Machine', 'type').upper()
                if machine_type == 'ARM':
                    if ocpus > 4:
                        logging.warning(f"OCPUs {ocpus} exceeds ARM limit of 4, setting to 4")
                        ocpus = 4
                    if memory > 24:
                        logging.warning(f"Memory {memory}GB exceeds ARM limit of 24GB, setting to 24")
                        memory = 24
                    # ARM memory must be 6GB per OCPU
                    expected_memory = ocpus * 6
                    if memory != expected_memory:
                        logging.warning(f"ARM memory should be {expected_memory}GB for {ocpus} OCPUs, adjusting")
                        memory = expected_memory
                
                launch_details.shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
                    ocpus=ocpus,
                    memory_in_gbs=memory
                )
                
                logging.debug(f"  Shape config: {ocpus} OCPUs, {memory}GB RAM")
            
            return launch_details
            
        except Exception as e:
            logging.error(f"Failed to build launch details: {str(e)}")
            raise

    def get_source_details(self):
        """Get instance source configuration"""
        try:
            boot_volume_id = self.config.get('OCI', 'boot_volume_id')
        except:
            boot_volume_id = ''
        
        if boot_volume_id and boot_volume_id != 'xxxx':
            return oci.core.models.InstanceSourceViaBootVolumeDetails(
                source_type="bootVolume",
                boot_volume_id=boot_volume_id
            )
        
        try:
            boot_volume_size = int(self.config.get('Instance', 'boot_volume_size'))
        except:
            boot_volume_size = 47
        
        return oci.core.models.InstanceSourceViaImageDetails(
            source_type="image",
            image_id=self.config.get('OCI', 'image_id'),
            boot_volume_size_in_gbs=boot_volume_size
        )

    def adaptive_retry_wait(self):
        """Adjust retry interval based on errors"""
        try:
            min_interval = float(self.config.get('Retry', 'min_interval'))
        except:
            min_interval = 1.0
        
        try:
            max_interval = float(self.config.get('Retry', 'max_interval'))
        except:
            max_interval = 60.0
        
        try:
            backoff_factor = float(self.config.get('Retry', 'backoff_factor'))
        except:
            backoff_factor = 1.5
        
        if self.last_error_code == 'TooManyRequests':
            self.wait_seconds = min(self.wait_seconds * backoff_factor, max_interval)
        else:
            self.wait_seconds = max(self.wait_seconds / 1.2, min_interval)
        
        self.wait_seconds = max(min(self.wait_seconds, max_interval), min_interval)

    def run(self):
        """Main execution loop"""
        logging.info("Starting OCI instance creation bot...")
        self.is_running = True
        self.start_time = datetime.datetime.now()
        
        # TELEGRAM BAŞLANGIÇ BİLDİRİMİ - YENİ EKLENDİ
        startup_message = f"""
🚀 <b>Bot Started!</b>

⚙️ <b>Configuration:</b>
• Region: {self.config.get('DEFAULT', 'region')}
• Shape: {self.config.get('Machine', 'shape')}
• Type: {self.config.get('Machine', 'type')}
• OCPUs: {self.config.get('Machine', 'ocpus')}
• Memory: {self.config.get('Machine', 'memory')} GB
• Display Name: {self.config.get('Instance', 'display_name')}

📍 <b>Availability Domains:</b>
{chr(10).join(['• ' + ad for ad in json.loads(self.config.get('OCI', 'availability_domains'))])}

⏰ Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_telegram_message(startup_message)
        
        self.update_dashboard(
            bot_status='running',
            start_time=self.start_time.isoformat()
        )
        
        try:
            ads = json.loads(self.config.get('OCI', 'availability_domains'))
        except json.JSONDecodeError:
            logging.critical("Invalid availability_domains format")
            self.send_telegram_message("❌ Bot failed to start: Invalid availability_domains format")
            return
        
        consecutive_errors = 0
        try:
            max_consecutive_errors = int(self.config.get('Retry', 'max_consecutive_errors'))
        except:
            max_consecutive_errors = 10
        
        while self.is_running:
            try:
                for ad in ads:
                    if not self.is_running:
                        break
                        
                    self.total_retries += 1
                    
                    # TELEGRAM PERİYODİK GÜNCELLEME - YENİ EKLENDİ
                    self.send_periodic_update()
                    
                    self.update_dashboard(
                        total_attempts=self.total_retries,
                        last_attempt_time=datetime.datetime.now().isoformat()
                    )
                    
                    instance_id = self.create_instance(ad)
                    
                    if instance_id:
                        consecutive_errors = 0
                        logging.info(f"✅ Success! Instance created: {instance_id}")
                        self.add_dashboard_log('INFO', f"SUCCESS! Instance created: {instance_id}")
                        self.update_dashboard(bot_status='stopped')
                        self.is_running = False
                        break
                    else:
                        consecutive_errors += 1
                    
                    if consecutive_errors >= max_consecutive_errors:
                        self.adaptive_retry_wait()
                        consecutive_errors = 0
                    
                    time.sleep(self.wait_seconds)
                    
                    if self.total_retries % 5 == 0:
                        self.adaptive_retry_wait()
                
            except KeyboardInterrupt:
                logging.info("Process interrupted by user")
                self.send_telegram_message("⏹ Bot stopped by user")
                self.is_running = False
                break
            except Exception as e:
                logging.error(f"Error in main loop: {str(e)}")
                self.send_telegram_message(f"❌ Bot error: {str(e)}")
                time.sleep(self.wait_seconds)
        
        # TELEGRAM SONLANMA BİLDİRİMİ - YENİ EKLENDİ
        final_message = f"""
🛑 <b>Bot Stopped</b>

📊 Final Statistics:
• Total Attempts: {self.total_retries}
• Instances Created: {len(self.instances_created)}
• Runtime: {datetime.datetime.now() - self.start_time if self.start_time else 'N/A'}
"""
        self.send_telegram_message(final_message)
        
        self.update_dashboard(bot_status='stopped')

def main():
    """Main entry point"""
    try:
        bot = OciOccFix()
        
        # If dashboard is disabled, run bot directly
        if not FLASK_AVAILABLE or not bot.config.getboolean('Dashboard', 'enabled', fallback=False):
            bot.run()
        else:
            # Keep main thread alive while dashboard runs
            print("\n✅ Bot initialized. Use web dashboard to control.")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
