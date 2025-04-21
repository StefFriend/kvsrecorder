# Get file size information
            file_size_str = "N/A"
            if os.path.exists(self.output_file):
                file_size_bytes = os.path.getsize(self.output_file)
                if file_size_bytes < 1024:
                    file_size_str = f"{file_size_bytes} B"
                elif file_size_bytes < 1024 * 1024:
                    file_size_str = f"{file_size_bytes / 1024:.2f} KB"
                else:
                    file_size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB""""
Report Generator Module

Handles the generation of detailed audio reports including waveform visualizations,
spectrograms, and audio file metadata.
"""

import os
import subprocess
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from PyQt6.QtCore import QThread, pyqtSignal
from fpdf import FPDF
import time
import warnings
from datetime import timedelta
import sys
import hashlib

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
        
    def calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of the audio file"""
        hash_obj = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read file in chunks of 4K
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
        
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
                
            waveform_path = os.path.join(self.temp_dir, 'final_waveform.png')
            spectrogram_path = os.path.join(self.temp_dir, 'final_spectrogram.png')
            
            # Setup warnings to handle deprecation notices
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", message="PySoundFile failed")
            
            # Calculate file hash
            self.report_progress.emit("Calculating file hash...")
            file_hash = self.calculate_file_hash(self.output_file)
            
            # Verify file is valid using ffprobe
            try:
                self.report_progress.emit("Verifying audio file...")
                probe_cmd = [
                    'ffprobe', 
                    '-v', 'error', 
                    '-show_entries', 'format=duration', 
                    '-of', 'default=noprint_wrappers=1:nokey=1', 
                    self.output_file
                ]
                
                result = subprocess.run(
                    probe_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=5
                )
                
                # If ffprobe can't read the file, it will raise an error
                # Otherwise it will return the duration
                probe_duration = result.stdout.decode('utf-8').strip()
                if not probe_duration or float(probe_duration) <= 0:
                    self.report_finished.emit(False, "Invalid or empty audio file")
                    return
                    
            except Exception as e:
                self.report_finished.emit(False, f"Unable to verify audio file: {str(e)}")
                return
            
            # Load audio
            self.report_progress.emit("Loading audio for analysis...")
            try:
                # Check if file exists before loading
                if os.path.isfile(self.output_file):
                    # Try to use SoundFile directly if available
                    try:
                        import soundfile as sf
                        audio, sr = sf.read(self.output_file)
                    except (ImportError, Exception) as sf_error:
                        # If it fails, use librosa with warnings handling
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            audio, sr = librosa.load(self.output_file, sr=None)
                else:
                    self.report_finished.emit(False, f"Audio file not found: {self.output_file}")
                    return
            except Exception as e:
                self.report_finished.emit(False, f"Unable to analyze audio file: {str(e)}")
                return

            # Generate waveform with green theme
            self.report_progress.emit("Generating waveform...")
            plt.figure(figsize=(10, 4), facecolor='white')
            librosa.display.waveshow(audio, sr=sr, color='#4CAF50')  # Changed to green
            plt.title("Complete Waveform", color='#1a73e8', fontweight='bold')
            plt.grid(True, color='#e8f0fe', linestyle='-', linewidth=0.5)
            plt.savefig(waveform_path, bbox_inches='tight', facecolor='white')

            # Generate spectrogram with green theme
            self.report_progress.emit("Generating spectrogram...")
            plt.figure(figsize=(10, 4), facecolor='white')
            S = librosa.stft(audio)
            # Use np.abs to avoid warning on complex input
            im = librosa.display.specshow(librosa.amplitude_to_db(np.abs(S), ref=np.max), 
                                    sr=sr, y_axis='log', x_axis='time', cmap='Greens')  # Changed to green
            plt.title("Complete Spectrogram", color='#1a73e8', fontweight='bold')
            cbar = plt.colorbar(im, format="%+2.0f dB")
            cbar.ax.yaxis.label.set_color('#1a73e8')
            cbar.ax.tick_params(colors='#1a73e8')
            plt.savefig(spectrogram_path, bbox_inches='tight', facecolor='white')
            plt.close('all')

            # Calculate audio statistics
            self.report_progress.emit("Calculating audio statistics...")
            duration = len(audio) / sr
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
                if "v1" in codec_full:
                    bitdepth = "Variable (HE-AAC v1)"
                elif "v2" in codec_full:
                    bitdepth = "Variable (HE-AAC v2)"
                else:
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

            # Generate PDF with white and blue theme
            self.report_progress.emit("Creating PDF report...")
            class PDF(FPDF):
                def header(self):
                    # Logo (if available)
                    # self.image('logo.png', 10, 8, 33)
                    # Title in blue
                    self.set_font('Arial', 'B', 18)
                    self.set_text_color(26, 115, 232)  # #1a73e8
                    self.cell(0, 10, 'KVSrecorder', 0, 1, 'C')
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
            pdf.cell(50, 8, f"Date:", 0)
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
            pdf.cell(0, 8, f"{self.bitrate_sel.currentText() if self.bitrate_sel.isEnabled() else 'N/A'}", 0, 1)
            
            pdf.cell(50, 8, f"Sample Rate:", 0)
            pdf.cell(0, 8, f"{sr} Hz", 0, 1)
            
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
            pdf.set_font("Arial", "B", 14)
            pdf.set_text_color(26, 115, 232)  # #1a73e8
            pdf.cell(0, 10, "Waveform", ln=True)
            pdf.image(waveform_path, w=180)
            
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.set_text_color(26, 115, 232)  # #1a73e8
            pdf.cell(0, 10, "Spectrogram", ln=True)
            pdf.image(spectrogram_path, w=180)
            
            self.report_progress.emit("Saving report...")
            pdf.output(pdf_path)
            
            # Automatically open the report if requested
            try:
                if os.path.exists(pdf_path):
                    if sys.platform == 'win32':
                        os.startfile(pdf_path)
                    elif sys.platform == 'darwin':  # macOS
                        subprocess.run(['open', pdf_path])
                    else:  # Linux
                        subprocess.run(['xdg-open', pdf_path])
            except Exception as e:
                self.report_progress.emit(f"Warning: Unable to automatically open report: {str(e)}")
            
            # Signal successful completion
            self.report_finished.emit(True, pdf_path)
                    
        except Exception as e:
            self.report_finished.emit(False, f"Error generating report: {str(e)}")