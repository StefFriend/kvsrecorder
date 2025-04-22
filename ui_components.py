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
from utils import create_temp_directory, clean_temp_directory, open_directory, format_time, APP_VERSION

# Filter librosa warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message="PySoundFile failed")
warnings.filterwarnings("ignore", message="amplitude_to_db was called on complex input")

class AudioProAdvanced(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KVSrecorder v{APP_VERSION}")
        self.resize(800, 650)  # Made more compact horizontally
        
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

        # Report generation queue
        self.report_queue = []
        self.is_report_processing = False

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
        self.play_second_format_action = QAction("Open Second Format Recording Folder", self)
        self.play_second_format_action.triggered.connect(self.open_second_format_folder)
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
        layout.setContentsMargins(8, 8, 8, 8)  # Make UI more compact

        # Input device selection
        device_layout = QtWidgets.QHBoxLayout()
        device_label = QtWidgets.QLabel("Input Device:")
        self.device_combo = QtWidgets.QComboBox()
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo, 1)  # Give it stretch factor to make UI more compact
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.populate_input_devices)
        device_layout.addWidget(refresh_btn)
        layout.addLayout(device_layout)

        # Advanced audio settings
        settings_group = QtWidgets.QGroupBox("Audio Settings")
        settings_group.setMaximumHeight(170)  # Make more compact
        form_layout = QtWidgets.QFormLayout(settings_group)
        form_layout.setContentsMargins(8, 12, 8, 8)  # Make UI more compact
        form_layout.setVerticalSpacing(6)  # Reduce vertical spacing
        
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
        dual_group.setMaximumHeight(140)  # Make more compact
        dual_layout = QtWidgets.QFormLayout(dual_group)
        dual_layout.setContentsMargins(8, 12, 8, 8)  # Make UI more compact
        dual_layout.setVerticalSpacing(6)  # Reduce vertical spacing
        
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
        output_layout.addWidget(self.output_path, 1)  # Give it stretch factor to make UI more compact
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout)

        # Recording timer and status
        timer_layout = QtWidgets.QHBoxLayout()
        
        # Timer display
        self.time_display = QtWidgets.QLabel("00:00:00.000")
        self.time_display.setStyleSheet("font-size: 22px; font-weight: bold;")  # Slightly smaller
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
        
        # Replace Play button with Open Folder button
        self.folder_btn = QtWidgets.QPushButton("Open Destination Folder")
        self.folder_btn.clicked.connect(self.open_destination_folder)
        self.folder_btn.setStyleSheet("font-size: 14px; padding: 8px;")
        
        button_layout.addWidget(self.record_btn)
        button_layout.addWidget(self.folder_btn)
        layout.addLayout(button_layout)

        # Real-Time Visualizations with vertical level meter
        viz_group = QtWidgets.QGroupBox("Real-Time Visualization")
        viz_layout = QtWidgets.QHBoxLayout(viz_group)  # Changed to horizontal layout
        viz_layout.setContentsMargins(8, 12, 8, 8)

        # Create a custom level meter instead of using QProgressBar
        # This will be a simple colored rectangle that updates with level
        self.level_meter_widget = QtWidgets.QWidget()
        self.level_meter_widget.setFixedWidth(40)
        self.level_meter_widget.setMinimumHeight(180)
        self.level_meter_widget.setStyleSheet("background-color: black; border: 1px solid gray;")

        # Add layout for labels and meter
        meter_layout = QtWidgets.QHBoxLayout()

        # Add level labels (0dB, -20dB, etc.)
        level_labels_layout = QtWidgets.QVBoxLayout()
        level_labels_layout.addWidget(QtWidgets.QLabel("0 dB"), 0, QtCore.Qt.AlignmentFlag.AlignRight)
        level_labels_layout.addStretch(1)
        level_labels_layout.addWidget(QtWidgets.QLabel("-20"), 0, QtCore.Qt.AlignmentFlag.AlignRight)
        level_labels_layout.addStretch(1)
        level_labels_layout.addWidget(QtWidgets.QLabel("-40"), 0, QtCore.Qt.AlignmentFlag.AlignRight)
        level_labels_layout.addStretch(1)
        level_labels_layout.addWidget(QtWidgets.QLabel("-60"), 0, QtCore.Qt.AlignmentFlag.AlignRight)

        meter_layout.addLayout(level_labels_layout)
        meter_layout.addWidget(self.level_meter_widget)

        # Store the current audio level for painting
        self.current_level = 0

        # Waveform display
        self.waveform_label = QtWidgets.QLabel()
        self.waveform_label.setFixedHeight(180)
        self.waveform_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.waveform_label.setText("Waveform will appear here during recording")
        
        # Add meter and waveform to visualization layout
        viz_layout.addLayout(meter_layout)
        viz_layout.addWidget(self.waveform_label, 1)  # Give waveform stretch factor

        layout.addWidget(viz_group)

        # Now override the paintEvent in the level meter widget to draw the level
        self.level_meter_widget.paintEvent = self.paint_level_meter

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
            # Only standard AAC - removed HE-AAC options
            self.codec_sel.addItems(["aac"])
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
            # Only standard AAC - removed HE-AAC options
            self.codec_sel2.addItems(["aac"])
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
                self.folder_btn.setEnabled(False)
                self.file_status.setText("Starting recording..." + (" (dual format)" if dual_format_enabled else ""))
                self.file_status.setStyleSheet("color: #FFC107; font-weight: bold;")  # Yellow
                self.statusBar().showMessage("Recording in progress..." + (" (dual format)" if dual_format_enabled else ""))
        
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Warning", f"Problem stopping recording: {str(e)}")

    def queue_report_generation(self, audio_file):
        """Add a file to the report generation queue"""
        if audio_file and os.path.exists(audio_file):
            self.report_queue.append(audio_file)
            # Start processing queue if not already running
            if not self.is_report_processing:
                self.process_report_queue()

    def process_report_queue(self):
        """Process the next file in the report queue"""
        if not self.report_queue:
            self.is_report_processing = False
            return
            
        self.is_report_processing = True
        file_to_process = self.report_queue[0]
        
        # Find appropriate format selector and codec selector based on file extension
        file_ext = os.path.splitext(file_to_process)[1].lower()[1:]  # Get extension without dot
        
        # Determine which format selectors to use based on file extension
        if self.last_recorded_file2 and file_to_process == self.last_recorded_file2:
            # This is the second format file
            format_sel = self.format_sel2
            codec_sel = self.codec_sel2
            bitrate_sel = self.bitrate_sel2
            
            # Ensure format is set correctly for this file
            if format_sel.currentText() != file_ext:
                for i in range(format_sel.count()):
                    if format_sel.itemText(i) == file_ext:
                        format_sel.setCurrentIndex(i)
                        break
        else:
            # This is the primary format file
            format_sel = self.format_sel
            codec_sel = self.codec_sel
            bitrate_sel = self.bitrate_sel
            
            # Ensure format is set correctly
            if format_sel.currentText() != file_ext:
                for i in range(format_sel.count()):
                    if format_sel.itemText(i) == file_ext:
                        format_sel.setCurrentIndex(i)
                        break
                        
        # Start report generation
        self.start_report_generation(file_to_process, format_sel, codec_sel, bitrate_sel)

    def start_report_generation(self, audio_file=None, format_sel=None, codec_sel=None, bitrate_sel=None):
        """Start report generation in a separate thread"""
        # Use provided file or last recorded file
        file_to_process = audio_file if audio_file else self.last_recorded_file
        
        if not file_to_process or not os.path.exists(file_to_process):
            QtWidgets.QMessageBox.warning(self, "Error", "No valid audio file to process")
            # Continue with next file in queue if this one fails
            self.handle_report_finished(False, "Invalid file")
            return
            
        # Use provided selectors or defaults
        format_selector = format_sel if format_sel else self.format_sel
        codec_selector = codec_sel if codec_sel else self.codec_sel
        bitrate_selector = bitrate_sel if bitrate_sel else self.bitrate_sel
            
        # Show progress
        self.report_status.setText(f"Preparing report for {os.path.basename(file_to_process)}...")
        self.report_progress_bar.setVisible(True)
        
        # Create and start report thread
        self.report_generator = ReportGeneratorThread(
            file_to_process, 
            format_selector, 
            codec_selector, 
            bitrate_selector, 
            self.temp_dir
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
            
            # Calculate peak level
            peak = float(np.abs(audio_data).max())
            
            # Scale peak value to meter range (0-100)
            # Using logarithmic scaling for better visual response
            if peak > 0:
                # Convert to dB, clamped to -60dB minimum
                db = max(-60, 20 * np.log10(peak / 32767))
                # Map -60dB..0dB to 0..100%
                self.current_level = (db + 60) / 60 * 100
            else:
                self.current_level = 0
                
            # Print debug info
            #print(f"Peak: {peak:.2f}, Level: {self.current_level:.1f}%, dB: {20 * np.log10(max(1, peak) / 32767):.1f}")
            
            # Request a repaint of the level meter
            self.level_meter_widget.update()
            
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
            # Print full exception for debugging
            import traceback
            traceback.print_exc()
            
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
        # Clear the report generator reference
        self.report_generator = None
        
        if success:
            self.report_status.setText(f"Report saved: {message}")
            self.report_status.setStyleSheet("color: #4CAF50;")  # Green
        else:
            self.report_status.setText(f"Report error: {message}")
            self.report_status.setStyleSheet("color: #e63946;")  # Red
        
        # Remove the processed file from the queue
        if self.report_queue:
            self.report_queue.pop(0)
        
        # Continue processing queue if there are more files
        if self.report_queue:
            # Use a timer to create a small delay between reports
            QtCore.QTimer.singleShot(1000, self.process_report_queue)
        else:
            self.is_report_processing = False
            self.report_progress_bar.setVisible(False)
            # Hide message after 15 seconds
            QtCore.QTimer.singleShot(15000, lambda: self.report_status.setText(""))

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
            self.queue_report_generation(file_path)
    
    # New method to open destination folder (replaces play_recording)
    def open_destination_folder(self):
        """Open the destination folder where recordings are saved"""
        try:
            output_dir = self.output_path.text()
            if os.path.exists(output_dir):
                open_directory(output_dir)
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "Output directory does not exist")
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Unable to open directory: {str(e)}")

    # Modified to open directory instead of playing file
    def open_second_format_folder(self):
        """Open the folder containing the second format recording"""
        try:
            second_file = None
            
            if hasattr(self.recorder, 'output_file2') and self.recorder.output_file2 and os.path.exists(self.recorder.output_file2):
                second_file = self.recorder.output_file2
            elif hasattr(self, 'last_recorded_file2') and self.last_recorded_file2 and os.path.exists(self.last_recorded_file2):
                second_file = self.last_recorded_file2
                
            if second_file:
                second_dir = os.path.dirname(second_file)
                open_directory(second_dir)
            else:
                QtWidgets.QMessageBox.information(self, "Information", "No second format recording is available")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Unable to open folder: {str(e)}")

    def show_about_dialog(self):
        """Show about dialog"""
        QtWidgets.QMessageBox.about(
            self,
            f"About KVSrecorder v{APP_VERSION}",
            f"""<h2>KVSrecorder v{APP_VERSION}</h2>
            <p>A professional audio recording and analysis application.</p>
            <p>Features:</p>
            <ul>
                <li>High-quality audio recording with custom format selection</li>
                <li>Dual format simultaneous recording</li>
                <li>Real-time visualization</li>
                <li>Detailed audio reports with waveform and spectrogram</li>
                <li>Support for multiple audio formats and codecs</li>
                <li>File integrity verification with SHA-256 hash</li>
            </ul>"""
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
                self.folder_btn.setEnabled(True)
                
                # Store output file references for later use
                self.last_recorded_file = self.recorder.output_file
                if dual_format and hasattr(self.recorder, 'output_file2') and self.recorder.output_file2:
                    self.last_recorded_file2 = self.recorder.output_file2
                    # Enable the "Open Second Format Folder" menu item
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
                    # Add files to report queue
                    self.queue_report_generation(self.recorder.output_file)
                    
                    # If dual format was used, add second file to report queue
                    if dual_format and hasattr(self.recorder, 'output_file2') and self.recorder.output_file2 and os.path.exists(self.recorder.output_file2):
                        QtWidgets.QMessageBox.information(
                            self,
                            "Dual Format Report",
                            "A report will also be generated for the second format recording after the first one completes."
                        )
                        self.queue_report_generation(self.recorder.output_file2)
            else:
                self.folder_btn.setEnabled(False)
                self.statusBar().showMessage("Error: Recording was not saved")
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Warning", f"Problem stopping recording: {str(e)}")

    def paint_level_meter(self, event):
        """Custom paint method for the level meter widget"""
        painter = QtGui.QPainter(self.level_meter_widget)
        
        # Get the widget dimensions
        width = self.level_meter_widget.width()
        height = self.level_meter_widget.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, QtGui.QColor('#212121'))  # Dark gray background
        
        # Calculate the level height (inverted - 0 at top, 100 at bottom)
        level_height = int(height * (1 - self.current_level / 100))
        
        # Draw the level meter (from bottom up)
        # Red for top 10% of range (0 to -10dB)
        if self.current_level > 90:
            red_zone_height = min(int(height * 0.1), height - level_height)
            painter.fillRect(0, level_height, width, red_zone_height, QtGui.QColor('#FF4444'))  # Red
            
        # Yellow for next 20% of range (-10dB to -30dB)
        if self.current_level > 70:
            yellow_start = max(level_height, int(height * 0.1))
            yellow_height = min(int(height * 0.2), height - yellow_start)
            painter.fillRect(0, yellow_start, width, yellow_height, QtGui.QColor('#FFFF00'))  # Yellow
            
        # Green for the rest (-30dB to -60dB)
        if self.current_level > 0:
            green_start = max(level_height, int(height * 0.3))
            green_height = height - green_start
            painter.fillRect(0, green_start, width, green_height, QtGui.QColor('#44FF44'))  # Green
        
        # Draw tick marks for reference
        pen = QtGui.QPen(QtGui.QColor('#FFFFFF'))
        pen.setWidth(1)
        painter.setPen(pen)
        
        # 0dB mark at 0% height
        painter.drawLine(0, int(height * 0.0), width, int(height * 0.0))
        
        # -20dB mark at 33% height
        painter.drawLine(0, int(height * 0.33), width, int(height * 0.33))
        
        # -40dB mark at 66% height
        painter.drawLine(0, int(height * 0.66), width, int(height * 0.66))
        
        painter.end()