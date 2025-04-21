"""
UI Components Module

Contains the main application UI class and related components.
"""

import os
import time
import shutil
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
import pyaudio
import warnings
import subprocess

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer

from audio_recorder import AudioRecorder
from report_generator import ReportGeneratorThread
from file_monitor import FileMonitorThread
from utils import create_temp_directory, clean_temp_directory, open_file_with_default_app, format_time

# Filter librosa warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message="PySoundFile failed")
warnings.filterwarnings("ignore", message="amplitude_to_db was called on complex input")

# Software version - easy to modify in one place
SOFTWARE_VERSION = "1.0.2"

class AudioProAdvanced(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KVSrecorder {SOFTWARE_VERSION}")
        self.resize(900, 700)
        
        # Apply white and blue theme
        self.apply_white_blue_theme()

        # Main variables
        self.recorder = AudioRecorder(self)
        self.stream = None
        self.ffmpeg_process = None
        self.frames = []
        self.recording_start_time = 0
        self.temp_dir = "temp"
        self.last_recorded_file = None
        self.last_recorded_file2 = None  # Second format recording
        
        # Create temporary directory
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            
        # Check for optional packages
        try:
            import soundfile
            self.has_soundfile = True
        except ImportError:
            self.has_soundfile = False
            print("SoundFile not found. Will use audioread to load audio files.")

        self.setup_ui()
        self.populate_input_devices()
        self.setup_menu()
        
    def apply_white_blue_theme(self):
        """Apply the white and blue theme to the application"""
        # Theme color definitions
        self.primary_blue = "#1a73e8"       # Primary blue
        self.light_blue = "#e8f0fe"         # Light blue for backgrounds
        self.dark_blue = "#174ea6"          # Dark blue for hover
        self.white = "#ffffff"              # White for general background
        self.text_color = "#202124"         # Almost black text color
        
        # Apply style to the entire application
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {self.white};
                color: {self.text_color};
            }}
            
            QGroupBox {{
                border: 1px solid #dadce0;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                background-color: {self.white};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                color: {self.primary_blue};
            }}
            
            QPushButton {{
                background-color: {self.primary_blue};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {self.dark_blue};
            }}
            
            QPushButton:disabled {{
                background-color: #dadce0;
                color: #9aa0a6;
            }}
            
            QComboBox {{
                border: 1px solid #dadce0;
                border-radius: 4px;
                padding: 5px;
                background-color: {self.white};
                selection-background-color: {self.light_blue};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QProgressBar {{
                border: 1px solid #dadce0;
                border-radius: 4px;
                background-color: {self.white};
                text-align: center;
            }}
            
            QProgressBar::chunk {{
                background-color: {self.primary_blue};
                width: 10px;
            }}
            
            QLineEdit {{
                border: 1px solid #dadce0;
                border-radius: 4px;
                padding: 5px;
                background-color: {self.white};
            }}
            
            QLabel {{
                color: {self.text_color};
            }}
            
            QMenuBar {{
                background-color: {self.white};
                color: {self.text_color};
            }}
            
            QMenuBar::item:selected {{
                background-color: {self.light_blue};
            }}
            
            QMenu {{
                background-color: {self.white};
                color: {self.text_color};
                border: 1px solid #dadce0;
            }}
            
            QMenu::item:selected {{
                background-color: {self.light_blue};
            }}
        """)

    def setup_menu(self):
        """Setup application menu"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        # Generate report action
        generate_report_action = QAction("Generate Report...", self)
        generate_report_action.triggered.connect(self.show_report_dialog)
        file_menu.addAction(generate_report_action)
        
        # Play second format action
        self.play_second_format_action = QAction("Play Second Format Recording", self)
        self.play_second_format_action.triggered.connect(self.play_second_format)
        self.play_second_format_action.setEnabled(False)
        file_menu.addAction(self.play_second_format_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        # About action
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)

        # Input device selection
        device_layout = QtWidgets.QHBoxLayout()
        device_label = QtWidgets.QLabel("Input Device:")
        self.device_combo = QtWidgets.QComboBox()
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.populate_input_devices)
        device_layout.addWidget(refresh_btn)
        layout.addLayout(device_layout)

        # Advanced audio settings
        settings_group = QtWidgets.QGroupBox("Audio Settings")
        form_layout = QtWidgets.QFormLayout(settings_group)
        
        self.format_sel = QtWidgets.QComboBox()
        self.format_sel.addItems(["wav", "mp3", "ogg", "flac", "m4a"])
        self.format_sel.currentIndexChanged.connect(self.update_codec_selection)
        
        self.codec_sel = QtWidgets.QComboBox()
        
        self.bitrate_sel = QtWidgets.QComboBox()
        self.bitrate_sel.addItems(["128k", "192k", "256k", "320k"])
        
        self.sample_rate_sel = QtWidgets.QComboBox()
        self.sample_rate_sel.addItems(["8000", "44100", "48000", "96000"])  # 8000 for alaw/mulaw
        self.sample_rate_sel.setCurrentText("48000")
        self.sample_rate_sel.currentTextChanged.connect(self.update_sample_rate)
        
        form_layout.addRow("Format:", self.format_sel)
        form_layout.addRow("Codec:", self.codec_sel)
        form_layout.addRow("Bitrate:", self.bitrate_sel)
        form_layout.addRow("Sample Rate:", self.sample_rate_sel)
        
        layout.addWidget(settings_group)
        
        # Dual format settings
        dual_group = QtWidgets.QGroupBox("Dual Format Recording")
        dual_group.setCheckable(True)
        dual_group.setChecked(False)
        dual_layout = QtWidgets.QFormLayout(dual_group)
        
        self.format_sel2 = QtWidgets.QComboBox()
        self.format_sel2.addItems(["wav", "mp3", "ogg", "flac", "m4a"])
        self.format_sel2.currentIndexChanged.connect(self.update_codec_selection2)
        
        self.codec_sel2 = QtWidgets.QComboBox()
        
        self.bitrate_sel2 = QtWidgets.QComboBox()
        self.bitrate_sel2.addItems(["128k", "192k", "256k", "320k"])
        
        dual_layout.addRow("Second Format:", self.format_sel2)
        dual_layout.addRow("Second Codec:", self.codec_sel2)
        dual_layout.addRow("Second Bitrate:", self.bitrate_sel2)
        
        # Set second format to different default (e.g., if first is wav, second is mp3)
        self.format_sel2.setCurrentText("mp3")
        self.update_codec_selection2()
        
        layout.addWidget(dual_group)
        
        # Store the dual format groupbox for checking its state
        self.dual_format_group = dual_group
        
        # Initialize codec menu based on selected format
        self.update_codec_selection()

        # Output path
        output_layout = QtWidgets.QHBoxLayout()
        self.output_path = QtWidgets.QLineEdit(os.path.join(os.getcwd(), "recordings"))
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_output_folder)
        output_layout.addWidget(QtWidgets.QLabel("Save to:"))
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout)

        # Recording timer and status
        timer_layout = QtWidgets.QHBoxLayout()
        
        # Timer display
        self.time_display = QtWidgets.QLabel("00:00:00.000")
        self.time_display.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.time_display.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Recording indicator
        self.recording_indicator = QtWidgets.QLabel("●")
        self.recording_indicator.setStyleSheet("font-size: 24px; color: gray;")
        self.recording_indicator.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.recording_indicator.setFixedWidth(30)
        
        # File status
        self.file_status = QtWidgets.QLabel("Not recording")
        self.file_status.setStyleSheet("font-style: italic;")
        
        timer_layout.addWidget(self.recording_indicator)
        timer_layout.addWidget(self.time_display)
        timer_layout.addWidget(self.file_status)
        layout.addLayout(timer_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.record_btn = QtWidgets.QPushButton("Start Recording")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setStyleSheet("font-size: 16px; padding: 8px;")
        
        self.play_btn = QtWidgets.QPushButton("Play")
        self.play_btn.clicked.connect(self.play_recording)
        self.play_btn.setEnabled(False)
        
        button_layout.addWidget(self.record_btn)
        button_layout.addWidget(self.play_btn)
        layout.addLayout(button_layout)

        # Real-Time Visualizations
        viz_group = QtWidgets.QGroupBox("Real-Time Visualization")
        viz_layout = QtWidgets.QVBoxLayout(viz_group)
        
        self.waveform_label = QtWidgets.QLabel()
        self.waveform_label.setFixedHeight(200)
        self.waveform_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.waveform_label.setText("Waveform will appear here during recording")
        
        # VU Meter with green progressbar
        self.vu_meter = QtWidgets.QProgressBar()
        self.vu_meter.setMaximum(100)
        self.vu_meter.setMinimum(0)
        self.vu_meter.setStyleSheet("""
            QProgressBar {
                border: 1px solid #dadce0;
                border-radius: 4px;
                background-color: white;
                text-align: center;
            }
            
            QProgressBar::chunk {
                background-color: #4CAF50;  /* Green instead of blue */
                width: 10px;
            }
        """)
        
        viz_layout.addWidget(self.waveform_label)
        viz_layout.addWidget(self.vu_meter)
        
        layout.addWidget(viz_group)

        # Report progress
        self.report_progress_bar = QtWidgets.QProgressBar()
        self.report_progress_bar.setRange(0, 0)  # Indeterminate mode
        self.report_progress_bar.setVisible(False)
        self.report_status = QtWidgets.QLabel("")
        
        report_layout = QtWidgets.QVBoxLayout()
        report_layout.addWidget(self.report_progress_bar)
        report_layout.addWidget(self.report_status)
        layout.addLayout(report_layout)

        # Status bar
        self.statusBar().showMessage("Ready for recording")

        self.setCentralWidget(central_widget)

        # Timer for real-time updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_visualization)
        
        # Timer for time display updates
        self.time_timer = QtCore.QTimer()
        self.time_timer.timeout.connect(self.update_time_display)
        
        # Timer for blinking recording indicator
        self.blink_timer = QtCore.QTimer()
        self.blink_timer.timeout.connect(self.blink_recording_indicator)
        self.blink_state = False
        
        # File monitoring thread
        self.file_monitor = None
        
        # Report generator thread
        self.report_generator = None

    def update_codec_selection(self, index=None):
        """Update codec options based on selected format"""
        self.codec_sel.clear()
        fmt = self.format_sel.currentText()
        
        if fmt == "wav":
            # Add bit depth information for each codec
            self.codec_sel.addItems([
                "pcm_s16le (16-bit)", 
                "pcm_s24le (24-bit)", 
                "pcm_f32le (32-bit float)", 
                "alaw (8-bit A-law)", 
                "mulaw (8-bit μ-law)"
            ])
            self.codec_sel.setCurrentText("pcm_s16le (16-bit)")
            self.bitrate_sel.setEnabled(False)
            
            # If sample rate is 8000, recommend alaw/mulaw
            if self.sample_rate_sel.currentText() == "8000":
                msg = "8kHz sample rate is ideal for alaw/mulaw! Would you like to use one of these codecs?"
                reply = QtWidgets.QMessageBox.question(self, "Codec Recommendation", msg,
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    self.codec_sel.setCurrentText("alaw (8-bit A-law)")
            
            # Verify codecs are supported
            try:
                codec_check = subprocess.run(
                    ['ffmpeg', '-encoders'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=2
                )
                codec_output = codec_check.stdout.decode('utf-8')
                
                # For alaw and mulaw, look for pcm_alaw and pcm_mulaw
                if "pcm_alaw" not in codec_output:
                    print("Warning: pcm_alaw (A-law) codec might not be supported")
                if "pcm_mulaw" not in codec_output:
                    print("Warning: pcm_mulaw (μ-law) codec might not be supported")
            except Exception:
                pass
                
        elif fmt == "mp3":
            self.codec_sel.addItems(["libmp3lame"])
            self.codec_sel.setCurrentText("libmp3lame")
            self.bitrate_sel.setEnabled(True)
        elif fmt == "ogg":
            self.codec_sel.addItems(["libvorbis", "libopus"])
            self.codec_sel.setCurrentText("libvorbis")
            self.bitrate_sel.setEnabled(True)
        elif fmt == "flac":
            self.codec_sel.addItems(["flac"])
            self.codec_sel.setCurrentText("flac")
            self.bitrate_sel.setEnabled(False)
        elif fmt == "m4a":
            # First check if libfdk_aac is available (for HE-AAC support)
            has_libfdk_aac = False
            try:
                codec_check = subprocess.run(
                    ['ffmpeg', '-encoders'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=2
                )
                codec_output = codec_check.stdout.decode('utf-8')
                has_libfdk_aac = "libfdk_aac" in codec_output
            except Exception:
                pass
                
            # Add codec options based on availability
            codec_options = ["aac"]
            if has_libfdk_aac:
                codec_options.extend([
                    "libfdk_aac (HE-AAC v1)", 
                    "libfdk_aac (HE-AAC v2)"
                ])
                
            self.codec_sel.addItems(codec_options)
            self.codec_sel.setCurrentText("aac")
            self.bitrate_sel.setEnabled(True)

    def update_codec_selection2(self, index=None):
        """Update codec options for second format based on selected format"""
        self.codec_sel2.clear()
        fmt = self.format_sel2.currentText()
        
        if fmt == "wav":
            # Add bit depth information for each codec
            self.codec_sel2.addItems([
                "pcm_s16le (16-bit)", 
                "pcm_s24le (24-bit)", 
                "pcm_f32le (32-bit float)", 
                "alaw (8-bit A-law)", 
                "mulaw (8-bit μ-law)"
            ])
            self.codec_sel2.setCurrentText("pcm_s16le (16-bit)")
            self.bitrate_sel2.setEnabled(False)
                
        elif fmt == "mp3":
            self.codec_sel2.addItems(["libmp3lame"])
            self.codec_sel2.setCurrentText("libmp3lame")
            self.bitrate_sel2.setEnabled(True)
        elif fmt == "ogg":
            self.codec_sel2.addItems(["libvorbis", "libopus"])
            self.codec_sel2.setCurrentText("libvorbis")
            self.bitrate_sel2.setEnabled(True)
        elif fmt == "flac":
            self.codec_sel2.addItems(["flac"])
            self.codec_sel2.setCurrentText("flac")
            self.bitrate_sel2.setEnabled(False)
        elif fmt == "m4a":
            # First check if libfdk_aac is available (for HE-AAC support)
            has_libfdk_aac = False
            try:
                codec_check = subprocess.run(
                    ['ffmpeg', '-encoders'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=2
                )
                codec_output = codec_check.stdout.decode('utf-8')
                has_libfdk_aac = "libfdk_aac" in codec_output
            except Exception:
                pass
                
            # Add codec options based on availability
            codec_options = ["aac"]
            if has_libfdk_aac:
                codec_options.extend([
                    "libfdk_aac (HE-AAC v1)", 
                    "libfdk_aac (HE-AAC v2)"
                ])
                
            self.codec_sel2.addItems(codec_options)
            self.codec_sel2.setCurrentText("aac")
            self.bitrate_sel2.setEnabled(True)

    def populate_input_devices(self):
        """Populate the input device dropdown with available devices"""
        self.device_combo.clear()
        info = {}
        
        for i in range(self.recorder.audio.get_device_count()):
            device_info = self.recorder.audio.get_device_info_by_index(i)
            if device_info["maxInputChannels"] > 0:
                name = device_info["name"]
                info[name] = i
                self.device_combo.addItem(name)

    def update_sample_rate(self):
        """Update sample rate and suggest appropriate codecs"""
        fs = int(self.sample_rate_sel.currentText())
        
        # If sample rate is 8000, suggest A-law or μ-law for WAV
        if fs == 8000 and self.format_sel.currentText() == "wav":
            for i in range(self.codec_sel.count()):
                if "alaw" in self.codec_sel.itemText(i):
                    self.codec_sel.setCurrentIndex(i)
                    break

    def browse_output_folder(self):
        """Open dialog to select output folder"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Save Folder")
        if folder:
            self.output_path.setText(folder)
            
    def toggle_recording(self):
        """Toggle between starting and stopping recording"""
        if self.recorder.stream is None:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording"""
        try:
            # Ensure temp directory exists
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
            
            # Get selected device index
            device_name = self.device_combo.currentText()
            device_index = None
            
            for i in range(self.recorder.audio.get_device_count()):
                info = self.recorder.audio.get_device_info_by_index(i)
                if info["name"] == device_name:
                    device_index = i
                    break
            
            # Use first device if we can't find a match
            if device_index is None and self.device_combo.count() > 0:
                device_index = self.recorder.audio.get_device_info_by_index(0)["index"]
            
            # Check if dual format recording is enabled
            dual_format_enabled = self.dual_format_group.isChecked()
            
            # Start the recorder
            if dual_format_enabled:
                success = self.recorder.start_recording(
                    device_index,
                    self.output_path.text(),
                    self.format_sel,
                    self.codec_sel,
                    self.bitrate_sel,
                    self.sample_rate_sel.currentText(),
                    self.format_sel2,   # Second format
                    self.codec_sel2,    # Second codec
                    self.bitrate_sel2   # Second bitrate
                )
            else:
                success = self.recorder.start_recording(
                    device_index,
                    self.output_path.text(),
                    self.format_sel,
                    self.codec_sel,
                    self.bitrate_sel,
                    self.sample_rate_sel.currentText()
                )
            
            if success or self.recorder.stream is not None:
                # Store output file reference
                self.last_recorded_file = self.recorder.output_file
                self.last_recorded_file2 = self.recorder.output_file2 if dual_format_enabled else None
                
                # Start timers
                self.recording_start_time = time.time()
                self.timer.start(50)  # Update visualization every 50ms
                self.time_timer.start(1000)  # Update timer every second
                
                # Start recording indicator blinking
                self.blink_timer.start(500)  # Blink every 500ms
                
                # Start file monitoring
                self.file_monitor = FileMonitorThread(self.recorder.output_file)
                self.file_monitor.file_status.connect(self.update_file_status)
                self.file_monitor.start()
                
                # Update UI
                self.record_btn.setText("Stop Recording")
                self.record_btn.setStyleSheet("background-color: #e63946; color: white; font-size: 16px; padding: 8px; border-radius: 4px;")
                self.play_btn.setEnabled(False)
                self.file_status.setText("Starting recording..." + (" (dual format)" if dual_format_enabled else ""))
                self.file_status.setStyleSheet("color: #FFC107; font-weight: bold;")  # Yellow
                self.statusBar().showMessage("Recording in progress..." + (" (dual format)" if dual_format_enabled else ""))
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Unable to start recording: {str(e)}")
            self.statusBar().showMessage(f"Error: {str(e)}")

    def stop_recording(self):
        """Stop audio recording"""
        try:
            # Check if dual format was being used
            dual_format = hasattr(self.recorder, 'dual_format_enabled') and self.recorder.dual_format_enabled
            
            # Stop timers
            self.timer.stop()
            self.time_timer.stop()
            self.blink_timer.stop()
            
            # Reset recording indicator
            self.recording_indicator.setStyleSheet("font-size: 24px; color: gray;")
            
            # Stop file monitoring
            if self.file_monitor:
                self.file_monitor.stop()
                self.file_monitor.wait()
                self.file_monitor = None
            
            # Reset file status
            self.file_status.setText("Processing..." + (" (dual format)" if dual_format else ""))
            self.file_status.setStyleSheet("color: #1a73e8; font-weight: bold;")
            
            # Stop the recording
            success = self.recorder.stop_recording()
            
            # Update UI
            self.record_btn.setText("Start Recording")
            self.record_btn.setStyleSheet(f"background-color: {self.primary_blue}; color: white; font-size: 16px; padding: 8px; border-radius: 4px;")
            
            if success:
                self.play_btn.setEnabled(True)
                
                # Store output file references for later use
                self.last_recorded_file = self.recorder.output_file
                if dual_format and hasattr(self.recorder, 'output_file2') and self.recorder.output_file2:
                    self.last_recorded_file2 = self.recorder.output_file2
                    # Enable the "Play Second Format" menu item
                    self.play_second_format_action.setEnabled(True)
                
                status_msg = f"Recording saved: {self.recorder.output_file}"
                if dual_format and hasattr(self.recorder, 'output_file2') and self.recorder.output_file2:
                    status_msg += f" and {self.recorder.output_file2}"
                self.statusBar().showMessage(status_msg)
                
                # Ask if user wants to generate a report
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Generate Report",
                    "Would you like to generate a detailed report for this recording?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                )
                
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    # Start report generation in separate thread
                    self.start_report_generation(self.recorder.output_file)
                    
                    # If dual format was used, store the second file info
                    if dual_format and hasattr(self.recorder, 'output_file2') and self.recorder.output_file2 and os.path.exists(self.recorder.output_file2):
                        self.second_report_file = self.recorder.output_file2
                        QtWidgets.QMessageBox.information(
                            self,
                            "Dual Format Report",
                            "A report will also be generated for the second format recording after the first one completes."
                        )
            else:
                self.play_btn.setEnabled(False)
                self.statusBar().showMessage("Error: Recording was not saved")
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Warning", f"Problem stopping recording: {str(e)}")

    def start_report_generation(self, audio_file=None):
        """Start report generation in a separate thread"""
        # Use provided file or last recorded file
        file_to_process = audio_file if audio_file else self.last_recorded_file
        
        if not file_to_process or not os.path.exists(file_to_process):
            QtWidgets.QMessageBox.warning(self, "Error", "No valid audio file to process")
            return
            
        # Show progress
        self.report_status.setText("Preparing report...")
        self.report_progress_bar.setVisible(True)
        
        # Create and start report thread
        self.report_generator = ReportGeneratorThread(
            file_to_process, 
            self.format_sel, 
            self.codec_sel, 
            self.bitrate_sel, 
            self.temp_dir,
            SOFTWARE_VERSION  # Pass the software version
        )
        self.report_generator.report_progress.connect(self.handle_report_progress)
        self.report_generator.report_finished.connect(self.handle_report_finished)
        self.report_generator.start()

    def update_visualization(self):
        """Update real-time visualization during recording"""
        try:
            if not self.recorder.frames:
                return
                
            audio_data = np.frombuffer(self.recorder.frames[-1], dtype=np.int16)
            peak = np.abs(audio_data).max()
            self.vu_meter.setValue(int(peak/32767*100))
            
            # Ensure temp directory exists
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
                
            # Draw waveform
            plt.figure(figsize=(6,2), facecolor='white')
            plt.plot(audio_data, linewidth=0.8, color='#4CAF50')  # Changed to green
            plt.axis('off')
            plt.tight_layout()
            
            temp_file = os.path.join(self.temp_dir, 'live_waveform.png')
            plt.savefig(temp_file, facecolor='white')
            plt.close()
            
            # Verify file was created before using it
            if os.path.exists(temp_file):
                pixmap = QtGui.QPixmap(temp_file)
                self.waveform_label.setPixmap(pixmap.scaled(
                    self.waveform_label.width(), 
                    self.waveform_label.height(), 
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio
                ))
            else:
                # If file doesn't exist, show only text
                self.waveform_label.setText("Updating visualization...")
            
        except Exception as e:
            # Limit error messages
            if not hasattr(self, '_logged_viz_error'):
                self._logged_viz_error = True
                self.statusBar().showMessage(f"Visualization error: {str(e)}")
                print(f"Error updating visualization: {e}")

    def update_time_display(self):
        """Update recording time display with milliseconds"""
        elapsed = time.time() - self.recording_start_time
        time_str = format_time(elapsed)  # Using the updated format_time function
        self.time_display.setText(time_str)
    
    def blink_recording_indicator(self):
        """Make recording indicator blink"""
        if self.blink_state:
            self.recording_indicator.setStyleSheet("font-size: 24px; color: #e63946;")  # Red on
        else:
            self.recording_indicator.setStyleSheet("font-size: 24px; color: gray;")  # Off
        
        self.blink_state = not self.blink_state
    
    def update_file_status(self, is_recording, file_size_kb):
        """Update recording file status"""
        if is_recording:
            # Format file size
            if file_size_kb < 1024:
                size_str = f"{file_size_kb} KB"
            else:
                size_str = f"{file_size_kb/1024:.1f} MB"
            
            # Check if dual format is enabled
            dual_format = hasattr(self.recorder, 'dual_format_enabled') and self.recorder.dual_format_enabled
            
            # Update status with size information
            if dual_format:
                # For dual format, try to get the second file size
                second_file_size = 0
                if hasattr(self.recorder, 'output_file2') and self.recorder.output_file2 and os.path.exists(self.recorder.output_file2):
                    second_file_size = os.path.getsize(self.recorder.output_file2) / 1024
                
                # Format second file size
                if second_file_size < 1024:
                    size_str2 = f"{int(second_file_size)} KB"
                else:
                    size_str2 = f"{second_file_size/1024:.1f} MB"
                
                self.file_status.setText(f"Recording active: {size_str} + {size_str2}")
            else:
                self.file_status.setText(f"Recording active: {size_str}")
            
            # Change color based on file growth
            if file_size_kb > 0:
                self.file_status.setStyleSheet("color: #4CAF50; font-weight: bold;")  # Green
            else:
                self.file_status.setStyleSheet("color: #FFC107; font-weight: bold;")  # Yellow warning
        else:
            self.file_status.setText("Not recording")
            self.file_status.setStyleSheet("font-style: italic; color: gray;")
    
    def handle_report_progress(self, message):
        """Handle report progress updates"""
        self.report_status.setText(message)
        
    def handle_report_finished(self, success, message):
        """Handle report generation completion"""
        # Store reference to the just-completed report
        completed_report = self.report_generator
        self.report_generator = None
        self.report_progress_bar.setVisible(False)
        
        if success:
            self.report_status.setText(f"Report saved: {message}")
            self.report_status.setStyleSheet("color: #4CAF50;")  # Green
            
            # Check if we need to generate a report for a second file
            if hasattr(self, 'second_report_file') and self.second_report_file and os.path.exists(self.second_report_file):
                second_file = self.second_report_file
                self.second_report_file = None  # Clear the reference
                
                # Print debug info
                print(f"Starting second report for file: {second_file}")
                
                # Use QTimer.singleShot to allow UI to update before starting second report generation
                # Use longer delay (2000ms) to ensure first report is completely finished
                QtCore.QTimer.singleShot(2000, lambda: self.start_second_report(second_file))
        else:
            self.report_status.setText(f"Report error: {message}")
            self.report_status.setStyleSheet("color: #e63946;")  # Red
            
            # If there was a second file pending, try to generate its report anyway
            if hasattr(self, 'second_report_file') and self.second_report_file and os.path.exists(self.second_report_file):
                second_file = self.second_report_file
                self.second_report_file = None  # Clear the reference
                # Start report generation for second file after a short delay
                QtCore.QTimer.singleShot(2000, lambda: self.start_second_report(second_file))
        
        # Display message for longer time (20 seconds)
        QtCore.QTimer.singleShot(20000, lambda: self.report_status.setText(""))
        
    def start_second_report(self, file_path):
        """Start generation of the second report (for dual format)"""
        if not file_path or not os.path.exists(file_path):
            self.report_status.setText("Error: Second format file not found")
            self.report_status.setStyleSheet("color: #e63946;")  # Red
            return
            
        # Additional validation: make sure the file size is not zero
        if os.path.getsize(file_path) == 0:
            self.report_status.setText("Error: Second format file is empty")
            self.report_status.setStyleSheet("color: #e63946;")  # Red
            return
            
        # Print debug info about file path and format
        print(f"Starting second report for: {file_path}")
        print(f"Format: {self.format_sel2.currentText()}, Codec: {self.codec_sel2.currentText()}")
        
        # Find the matching format for the file extension
        file_ext = os.path.splitext(file_path)[1].lower()[1:]  # Get extension without dot
        if self.format_sel2.currentText() != file_ext:
            # If current format doesn't match file extension, find the right one
            for i in range(self.format_sel2.count()):
                if self.format_sel2.itemText(i) == file_ext:
                    self.format_sel2.setCurrentIndex(i)
                    break
            
        self.report_status.setText("Preparing second format report...")
        self.report_progress_bar.setVisible(True)
        
        # Create and start report thread for second file with correct format settings
        report_generator = ReportGeneratorThread(
            file_path, 
            self.format_sel2,    # Use second format settings 
            self.codec_sel2,     # Use second codec settings
            self.bitrate_sel2,   # Use second bitrate settings
            self.temp_dir,
            SOFTWARE_VERSION     # Pass the software version
        )
        self.report_generator = report_generator
        self.report_generator.report_progress.connect(self.handle_report_progress)
        self.report_generator.report_finished.connect(self.handle_report_finished)
        self.report_generator.start()

    def play_recording(self):
        """Play the recorded audio file with default application"""
        try:
            dual_format = hasattr(self, 'last_recorded_file2') and self.last_recorded_file2
            
            # Play primary recording
            if self.recorder.output_file and os.path.exists(self.recorder.output_file):
                open_file_with_default_app(self.recorder.output_file)
                # Also open the log file if it exists
                if self.recorder.log_file and os.path.exists(self.recorder.log_file):
                    open_file_with_default_app(self.recorder.log_file)
                    
                # Open second recording if dual format was used
                if self.recorder.dual_format_enabled and self.recorder.output_file2 and os.path.exists(self.recorder.output_file2):
                    open_file_with_default_app(self.recorder.output_file2)
                    if self.recorder.log_file2 and os.path.exists(self.recorder.log_file2):
                        open_file_with_default_app(self.recorder.log_file2)
                    
            elif self.last_recorded_file and os.path.exists(self.last_recorded_file):
                open_file_with_default_app(self.last_recorded_file)
                # Try to open the corresponding log file
                log_file = os.path.splitext(self.last_recorded_file)[0] + "_log"
                if os.path.exists(log_file):
                    open_file_with_default_app(log_file)
                    
                # Open second recording if dual format was used
                if dual_format and os.path.exists(self.last_recorded_file2):
                    open_file_with_default_app(self.last_recorded_file2)
                    log_file2 = os.path.splitext(self.last_recorded_file2)[0] + "_log"
                    if os.path.exists(log_file2):
                        open_file_with_default_app(log_file2)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Unable to play file: {str(e)}")

    def play_second_format(self):
        """Play the second format recording if it exists"""
        try:
            if hasattr(self.recorder, 'output_file2') and self.recorder.output_file2 and os.path.exists(self.recorder.output_file2):
                open_file_with_default_app(self.recorder.output_file2)
                # Also open the second log file if it exists
                if hasattr(self.recorder, 'log_file2') and self.recorder.log_file2 and os.path.exists(self.recorder.log_file2):
                    open_file_with_default_app(self.recorder.log_file2)
            elif hasattr(self, 'last_recorded_file2') and self.last_recorded_file2 and os.path.exists(self.last_recorded_file2):
                open_file_with_default_app(self.last_recorded_file2)
                # Try to open the corresponding log file
                log_file2 = os.path.splitext(self.last_recorded_file2)[0] + "_log"
                if os.path.exists(log_file2):
                    open_file_with_default_app(log_file2)
            else:
                QtWidgets.QMessageBox.information(self, "Information", "No second format recording is available")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Unable to play second format file: {str(e)}")

    def show_report_dialog(self):
        """Show dialog to select an audio file for report generation"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Audio File for Report",
            self.output_path.text(),
            "Audio Files (*.wav *.mp3 *.ogg *.flac *.m4a);;All Files (*.*)"
        )
        
        if file_path and os.path.exists(file_path):
            self.last_recorded_file = file_path
            self.start_report_generation(file_path)
    
    def show_about_dialog(self):
        """Show about dialog"""
        QtWidgets.QMessageBox.about(
            self,
            f"About KVSrecorder {SOFTWARE_VERSION}",
            f"""<h2>KVSrecorder {SOFTWARE_VERSION}</h2>
            <p>A professional audio recording and analysis application.</p>
            <p>Features:</p>
            <ul>
                <li>High-quality audio recording with custom format selection</li>
                <li>Dual format simultaneous recording</li>
                <li>Real-time visualization</li>
                <li>Detailed audio reports with waveform and spectrogram</li>
                <li>Support for multiple audio formats and codecs including HE-AAC</li>
                <li>File integrity verification with SHA-256 hash</li>
            </ul>
            <p>Version {SOFTWARE_VERSION}</p>"""
        )

    def closeEvent(self, event):
        """Handle window close event"""
        # Clean up resources
        if self.recorder.stream:
            self.stop_recording()
            
        # Stop active threads
        if hasattr(self, 'file_monitor') and self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor.wait()
            
        if hasattr(self, 'report_generator') and self.report_generator:
            self.report_generator.terminate()
            self.report_generator.wait()
            
        # Terminate PyAudio
        self.recorder.cleanup()
        
        # Clean up temporary files
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error cleaning temporary files: {e}")
            
        event.accept()