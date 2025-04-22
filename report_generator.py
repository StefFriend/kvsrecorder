"""
Report Generator Module

Handles the generation of detailed audio reports including waveform visualizations,
spectrograms, and audio file metadata.
"""

import os
import subprocess
import numpy as np
import librosa
import librosa.display
import matplotlib
# Use Agg backend to avoid GUI issues in threads
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import QThread, pyqtSignal
from fpdf import FPDF
import time
import warnings
from datetime import timedelta
import sys
import hashlib
from utils import APP_VERSION

# Filter librosa warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message="PySoundFile failed")
warnings.filterwarnings("ignore", message="amplitude_to_db was called on complex input")

class ReportGeneratorThread(QThread):
    # Signals to communicate with main interface
    report_progress = pyqtSignal(str)
    report_finished = pyqtSignal(bool, str)
    
    def __init__(self, output_file, format_sel, codec_sel, bitrate_sel, temp_dir):
        super().__init__()
        self.output_file = output_file
        self.format_sel = format_sel
        self.codec_sel = codec_sel
        self.bitrate_sel = bitrate_sel
        self.temp_dir = temp_dir
        self.channels = 1  # Default to mono
        
    def calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of the audio file"""
        hash_obj = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read file in chunks of 4K
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
        
    def format_time_axis(self, duration):
        """Format time axis labels based on total duration"""
        if duration < 60:  # Less than a minute
            # Use seconds.milliseconds format
            return "Time (seconds)"
        elif duration < 3600:  # Less than an hour
            # Use minutes:seconds format
            return "Time (minutes:seconds)"
        else:  # Hours or more
            # Use hours:minutes:seconds format
            return "Time (hours:minutes:seconds)"
    
    def run(self):
        try:
            self.report_progress.emit("Starting report generation...")
            
            # Verify file exists and is not empty
            if not os.path.exists(self.output_file) or os.path.getsize(self.output_file) == 0:
                self.report_finished.emit(False, f"Invalid or empty file: {self.output_file}")
                return
                
            # Create report filename
            pdf_path = os.path.splitext(self.output_file)[0] + "_report.pdf"
            
            # Make sure temp directory exists
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
                
            viz_path = os.path.join(self.temp_dir, 'audio_visualization.png')
            
            # Setup warnings to handle deprecation notices
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", message="PySoundFile failed")
            
            # Calculate file hash
            self.report_progress.emit("Calculating file hash...")
            file_hash = self.calculate_file_hash(self.output_file)
            
            # Get file size information
            file_size_str = "N/A"
            if os.path.exists(self.output_file):
                file_size_bytes = os.path.getsize(self.output_file)
                if file_size_bytes < 1024:
                    file_size_str = f"{file_size_bytes} B"
                elif file_size_bytes < 1024 * 1024:
                    file_size_str = f"{file_size_bytes / 1024:.2f} KB"
                else:
                    file_size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"
            
            # Load audio - process the full file regardless of size
            self.report_progress.emit("Loading audio for analysis...")
            try:
                # Check if file exists before loading
                if os.path.isfile(self.output_file):
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        audio, sr = librosa.load(self.output_file, sr=None)
                else:
                    self.report_finished.emit(False, f"Audio file not found: {self.output_file}")
                    return
            except Exception as e:
                self.report_finished.emit(False, f"Unable to analyze audio file: {str(e)}")
                return
                
            # Calculate duration from the loaded audio
            duration = len(audio) / sr
            
            # Create a function for time formatting based on duration
            def format_time(x, pos):
                seconds = int(x)
                if duration < 60:  # Less than a minute
                    ms = int((x - seconds) * 1000)
                    return f"{seconds}.{ms:03d}"
                elif duration < 3600:  # Less than an hour
                    minutes = seconds // 60
                    seconds = seconds % 60
                    return f"{minutes}:{seconds:02d}"
                else:  # Hours or more
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    seconds = seconds % 60
                    return f"{hours}:{minutes:02d}:{seconds:02d}"
            
            # Format time axis label based on duration
            time_label = self.format_time_axis(duration)
            
            # Generate visualization with perfectly matching widths
            self.report_progress.emit("Generating visualizations...")
            
            # Create a figure with specific subplot grid
            fig = plt.figure(figsize=(10, 7), dpi=150)
            
            # Main title for the visualization
            #fig.suptitle("Audio Visualization", fontsize=16, fontweight='bold', color='#1a73e8')
            
            # Create a GridSpec layout with 2 rows and 1 column
            from matplotlib import gridspec
            gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], hspace=0.5)
            
            # Create waveform plot in the first row
            ax1 = plt.subplot(gs[0])
            librosa.display.waveshow(audio, sr=sr, ax=ax1, color='#4CAF50')
            ax1.set_title("Waveform", color='#1a73e8', fontweight='bold')
            ax1.set_xlabel(time_label, color='#1a73e8')
            ax1.set_ylabel("Amplitude", color='#1a73e8')
            ax1.set_xlim(0, duration)
            ax1.grid(True, color='#e8f0fe', linestyle='-', linewidth=0.5)
            
            # Create spectrogram plot in the second row
            ax2 = plt.subplot(gs[1])
            S = librosa.stft(audio)
            spec_img = librosa.display.specshow(
                librosa.amplitude_to_db(np.abs(S), ref=np.max),
                sr=sr,
                y_axis='hz',
                x_axis='time',
                ax=ax2,
                cmap='Greens'
            )
            
            ax2.set_title("Spectrogram", color='#1a73e8', fontweight='bold')
            ax2.set_xlabel(time_label, color='#1a73e8')
            ax2.set_ylabel("Frequency (Hz)", color='#1a73e8')
            ax2.set_xlim(0, duration)  # Match x-axis limits with waveform
            #ax2.xaxis.set_major_formatter(FuncFormatter(format_time))
            
            # Add colorbar to spectrogram
            cbar = fig.colorbar(spec_img, ax=ax2, format="%+2.0f dB")
            cbar.set_label('Amplitude (dB)', color='#1a73e8')
            cbar.ax.yaxis.label.set_color('#1a73e8')
            cbar.ax.tick_params(colors='#1a73e8')
            
            # Critical: After adding colorbar, make the waveform axes match the spectrogram's width
            # This is done by getting the position of both axes and adjusting the first one
            pos_spectro = ax2.get_position()
            pos_wave = ax1.get_position()
            ax1.set_position([pos_wave.x0, pos_wave.y0, pos_spectro.width, pos_wave.height])
            
            plt.tight_layout(rect=[0, 0, 1, 0.95])  # Adjust for suptitle
            plt.savefig(viz_path, bbox_inches='tight', facecolor='white')
            plt.close('all')

            # Calculate audio statistics
            self.report_progress.emit("Calculating audio statistics...")
            rms = np.sqrt(np.mean(audio**2))
            peak = np.abs(audio).max()
            dynamic_range = 20 * np.log10(peak / (np.mean(np.abs(audio)) + 1e-10))

            # Format duration as 00:00:00.000
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            milliseconds = int((duration - int(duration)) * 1000)
            duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            
            # Get bitdepth information - FIX: Extract codec properly from the combo box
            codec_full = self.codec_sel.currentText()
            codec_base = codec_full.split(" ")[0]  # Extract just the codec name without description
            
            # Set bitdepth based on codec
            bitdepth = "16-bit"  # Default
            if codec_base in ["alaw", "mulaw"]:
                bitdepth = "8-bit"
            elif codec_base == "pcm_s24le":
                bitdepth = "24-bit"
            elif codec_base == "pcm_f32le":
                bitdepth = "32-bit float"
            elif codec_base == "libfdk_aac":
                bitdepth = "Variable (AAC-LC)"
            
            # Also check the description part for bit depth information
            if " (" in codec_full and "bit" in codec_full:
                try:
                    # Try to extract bit depth from the description
                    bitdepth_part = codec_full.split("(")[1].split(")")[0]
                    if "8-bit" in bitdepth_part:
                        bitdepth = "8-bit"
                    elif "16-bit" in bitdepth_part:
                        bitdepth = "16-bit"
                    elif "24-bit" in bitdepth_part:
                        bitdepth = "24-bit"
                    elif "32-bit" in bitdepth_part:
                        bitdepth = "32-bit"
                except:
                    pass
                    
            # Get bitrate information - handle for all formats
            bitrate_str = "N/A"
            if self.bitrate_sel and self.bitrate_sel.isEnabled():
                bitrate_str = self.bitrate_sel.currentText()
            
            # Some formats have implicit bitrates even when not shown in UI
            fmt = os.path.splitext(self.output_file)[1][1:].lower()
            if fmt == "wav":
                if codec_base == "pcm_s16le":
                    bitrate_str = f"{sr * 16 * self.channels / 1000} kbps"
                elif codec_base == "pcm_s24le":
                    bitrate_str = f"{sr * 24 * self.channels / 1000} kbps"
                elif codec_base == "pcm_f32le":
                    bitrate_str = f"{sr * 32 * self.channels / 1000} kbps"
                elif codec_base in ["alaw", "mulaw"]:
                    bitrate_str = f"{sr * 8 * self.channels / 1000} kbps"
            elif fmt == "flac":
                bitrate_str = "Variable (lossless)"

            # Generate PDF with white and blue theme
            self.report_progress.emit("Creating PDF report...")
            class PDF(FPDF):
                def header(self):
                    # Title in blue
                    self.set_font('Arial', 'B', 18)
                    self.set_text_color(26, 115, 232)  # #1a73e8
                    self.cell(0, 10, f'KVSrecorder v{APP_VERSION}', 0, 1, 'C')
                    self.ln(10)
                
                def footer(self):
                    self.set_y(-15)
                    self.set_font('Arial', 'I', 8)
                    self.set_text_color(26, 115, 232)  # #1a73e8
                    self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')
            
            pdf = PDF()
            pdf.alias_nb_pages()
            pdf.add_page()
            
            # Report header
            pdf.set_font("Arial", "B", 16)
            pdf.set_text_color(26, 115, 232)  # #1a73e8
            pdf.cell(0, 10, "Complete Audio Report", ln=True, align='C')
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            # Main data
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(26, 115, 232)  # #1a73e8
            pdf.cell(60, 10, "File Information:", 0, 1)
            
            pdf.set_font("Arial", "", 11)
            pdf.set_text_color(0, 0, 0)  # Black text
            pdf.cell(50, 8, f"File Name:", 0)
            pdf.cell(0, 8, f"{os.path.basename(self.output_file)}", 0, 1)
            
            # Add file size information
            pdf.cell(50, 8, f"File Size:", 0)
            pdf.cell(0, 8, f"{file_size_str}", 0, 1)
            
            # Format current time with milliseconds
            current_time = time.strftime("%d/%m/%Y %H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
            pdf.cell(50, 8, f"Report date:", 0)
            pdf.cell(0, 8, f"{current_time}", 0, 1)
            
            pdf.cell(50, 8, f"Duration:", 0)
            pdf.cell(0, 8, f"{duration_formatted}", 0, 1)
            
            # Add file hash
            pdf.cell(50, 8, f"SHA-256 Hash:", 0)
            pdf.cell(0, 8, f"{file_hash}", 0, 1)
            
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(26, 115, 232)  # #1a73e8
            pdf.cell(60, 10, "Technical Specifications:", 0, 1)
            
            pdf.set_font("Arial", "", 11)
            pdf.set_text_color(0, 0, 0)  # Black text
            pdf.cell(50, 8, f"Format:", 0)
            pdf.cell(0, 8, f"{os.path.splitext(self.output_file)[1][1:]}", 0, 1)
            
            pdf.cell(50, 8, f"Codec:", 0)
            pdf.cell(0, 8, f"{codec_base}", 0, 1)
            
            pdf.cell(50, 8, f"Bit Depth:", 0)
            pdf.cell(0, 8, f"{bitdepth}", 0, 1)
            
            pdf.cell(50, 8, f"Bitrate:", 0)
            pdf.cell(0, 8, f"{bitrate_str}", 0, 1)
            
            pdf.cell(50, 8, f"Sample Rate:", 0)
            pdf.cell(0, 8, f"{sr} Hz", 0, 1)
            
            # Add software version
            pdf.cell(50, 8, f"Software Version:", 0)
            pdf.cell(0, 8, f"{APP_VERSION}", 0, 1)
            
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(26, 115, 232)  # #1a73e8
            pdf.cell(60, 10, "Audio Analysis:", 0, 1)
            
            pdf.set_font("Arial", "", 11)
            pdf.set_text_color(0, 0, 0)  # Black text
            pdf.cell(50, 8, f"RMS:", 0)
            pdf.cell(0, 8, f"{rms:.6f}", 0, 1)
            
            pdf.cell(50, 8, f"Peak:", 0)
            pdf.cell(0, 8, f"{peak:.6f}", 0, 1)
            
            pdf.cell(50, 8, f"Dynamic Range:", 0)
            pdf.cell(0, 8, f"{dynamic_range:.2f} dB", 0, 1)
            
            pdf.add_page()
            
            # Add visualization - no need for additional title
            pdf.image(viz_path, x=10, y=30, w=190)
            
            self.report_progress.emit("Saving report...")
            pdf.output(pdf_path)
            
            # Signal successful completion
            self.report_finished.emit(True, pdf_path)
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report_finished.emit(False, f"Error generating report: {str(e)}")
            
    def __del__(self):
        # Ensure clean shutdown
        self.wait()