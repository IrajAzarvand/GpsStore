#!/usr/bin/env python3
"""
GPS Receiver Monitor and Auto-Restart Script
Monitors the GPS receiver process and automatically restarts it if it crashes.
"""

import os
import sys
import time
import logging
import subprocess
import signal
from datetime import datetime
import psutil

# Setup logging
logging.basicConfig(
    filename='logs/gps_receiver_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)

class GPSReceiverMonitor:
    def __init__(self):
        self.project_dir = r'c:\Users\iraj\Desktop\GpsStore'
        self.process = None
        self.running = True
        self.check_interval = 5  # seconds
        self.max_restart_attempts = 3
        self.restart_count = 0
        self.last_restart_time = None

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False
            self.stop_process()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def is_process_running(self):
        """Check if GPS receiver process is running"""
        try:
            # Check for python processes running gps_receiver command
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'python.exe':
                        cmdline = proc.info['cmdline']
                        if cmdline and len(cmdline) >= 3:
                            if 'manage.py' in cmdline and 'gps_receiver' in cmdline:
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            logger.error(f"Error checking process status: {e}")
            return False

    def start_process(self):
        """Start the GPS receiver process"""
        try:
            if self.is_process_running():
                logger.info("GPS receiver is already running")
                return True

            logger.info("Starting GPS receiver process...")

            # Change to project directory
            os.chdir(self.project_dir)

            # Start the process
            self.process = subprocess.Popen(
                [sys.executable, 'manage.py', 'gps_receiver'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.project_dir,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Wait a moment for the process to start
            time.sleep(2)

            if self.process.poll() is None:
                logger.info(f"GPS receiver started successfully (PID: {self.process.pid})")
                self.restart_count = 0
                self.last_restart_time = datetime.now()
                return True
            else:
                stdout, stderr = self.process.communicate()
                logger.error(f"Failed to start GPS receiver. STDOUT: {stdout.decode()}, STDERR: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Error starting GPS receiver: {e}")
            return False

    def stop_process(self):
        """Stop the GPS receiver process"""
        if self.process:
            try:
                logger.info("Stopping GPS receiver process...")
                self.process.terminate()

                # Wait for process to terminate
                try:
                    self.process.wait(timeout=10)
                    logger.info("GPS receiver stopped successfully")
                except subprocess.TimeoutExpired:
                    logger.warning("GPS receiver didn't terminate gracefully, forcing kill...")
                    self.process.kill()
                    self.process.wait()
                    logger.info("GPS receiver force killed")

            except Exception as e:
                logger.error(f"Error stopping GPS receiver: {e}")
        else:
            # Try to kill any existing processes
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] == 'python.exe':
                            cmdline = proc.info['cmdline']
                            if cmdline and 'manage.py' in cmdline and 'gps_receiver' in cmdline:
                                proc.kill()
                                logger.info(f"Killed existing GPS receiver process (PID: {proc.pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as e:
                logger.error(f"Error killing existing processes: {e}")

    def monitor(self):
        """Main monitoring loop"""
        logger.info("GPS Receiver Monitor started")

        while self.running:
            try:
                if not self.is_process_running():
                    logger.warning("GPS receiver process not found, attempting to restart...")

                    # Check restart limits
                    if self.restart_count >= self.max_restart_attempts:
                        if self.last_restart_time:
                            time_diff = (datetime.now() - self.last_restart_time).total_seconds()
                            if time_diff < 300:  # 5 minutes
                                logger.error("Too many restart attempts in short time, waiting...")
                                time.sleep(60)
                                continue

                    if self.start_process():
                        logger.info("GPS receiver restarted successfully")
                    else:
                        logger.error("Failed to restart GPS receiver")
                        time.sleep(30)  # Wait before next attempt
                else:
                    # Process is running, reset restart count
                    if self.restart_count > 0:
                        logger.info("GPS receiver is running normally")
                        self.restart_count = 0

                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

        logger.info("GPS Receiver Monitor stopped")

def main():
    """Main function"""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    monitor = GPSReceiverMonitor()
    monitor.setup_signal_handlers()

    try:
        # Start the process initially
        if not monitor.start_process():
            logger.error("Failed to start GPS receiver initially")
            sys.exit(1)

        # Start monitoring
        monitor.monitor()

    except KeyboardInterrupt:
        logger.info("Monitor interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        monitor.stop_process()

if __name__ == "__main__":
    main()