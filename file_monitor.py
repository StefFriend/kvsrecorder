"""
File Monitor Module

Monitors the recording file status and size during recording.
"""

import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

class FileMonitorThread(QThread):
    """
    Thread for monitoring file size and status during recording.
    Emits signals with the current recording status and file size.
    """
    file_status = pyqtSignal(bool, int)  # (is_recording, file_size_kb)
    
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.is_running = True
    
    def run(self):
        """Main thread loop to monitor file size and status"""
        while self.is_running:
            try:
                if os.path.exists(self.filename):
                    size_kb = os.path.getsize(self.filename) / 1024
                    self.file_status.emit(True, int(size_kb))
                else:
                    self.file_status.emit(False, 0)
            except Exception:
                self.file_status.emit(False, 0)
            
            # Check every 200ms
            time.sleep(0.2)
    
    def stop(self):
        """Stop the monitoring thread"""
        self.is_running = False