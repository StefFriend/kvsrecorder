"""
Audio Recorder Module

Handles the recording functionality including audio stream management,
FFmpeg process control, and audio format configuration.
"""

import os
import time
import subprocess
import pyaudio
import numpy as np
from PyQt6 import QtWidgets
import datetime
from utils import calculate_file_hash, create_recording_log, update_recording_log

class AudioRecorder:
    def __init__(self, parent):
        self.parent = parent
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.ffmpeg_process = None
        self.ffmpeg_process2 = None  # Second FFmpeg process for dual recording
        self.frames = []
        self.fs = 48000  # Sample rate
        self.channels = 1  # Mono recording
        self.chunk = 2048  # Buffer size
        self.recording_start_time = 0
        self.recording_start_datetime = None
        self.output_file = None
        self.output_file2 = None  # Second output file for dual recording
        self.log_file = None
        self.log_file2 = None  # Second log file for dual recording
        self.current_filename = None
        self.ffmpeg_command = None
        self.ffmpeg_command2 = None  # Second FFmpeg command for dual recording
        self.dual_format_enabled = False  # Flag for dual format recording
        
    def start_recording(self, device_index, output_dir, format_sel, codec_sel, bitrate_sel, sample_rate, 
                        format_sel2=None, codec_sel2=None, bitrate_sel2=None):
        """Start recording audio with the specified settings"""
        try:
            # Check if dual format recording is enabled
            self.dual_format_enabled = format_sel2 is not None and codec_sel2 is not None
            
            # Reset error flags
            if hasattr(self, '_logged_write_error'):
                delattr(self, '_logged_write_error')
            
            # Create output directory if it doesn't exist
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Generate filename based on timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            self.current_filename = f"rec_{timestamp}"
            fmt = format_sel.currentText()
            
            # Extract base codec (remove parentheses part if present)
            codec_full = codec_sel.currentText()
            codec = codec_full.split(" ")[0] if " " in codec_full else codec_full
            
            bitrate = bitrate_sel.currentText()
            self.output_file = os.path.join(output_dir, f"{self.current_filename}.{fmt}")
            self.log_file = os.path.join(output_dir, f"{self.current_filename}_log.txt")
            
            # Setup second format if dual recording is enabled
            if self.dual_format_enabled:
                fmt2 = format_sel2.currentText()
                codec_full2 = codec_sel2.currentText()
                codec2 = codec_full2.split(" ")[0] if " " in codec_full2 else codec_full2
                bitrate2 = bitrate_sel2.currentText() if bitrate_sel2 else "256k"
                self.output_file2 = os.path.join(output_dir, f"{self.current_filename}_2.{fmt2}")
                self.log_file2 = os.path.join(output_dir, f"{self.current_filename}_2_log.txt")
            
            # Prepare for recording
            self.frames.clear()
            self.fs = int(sample_rate)
            
            # Store start datetime
            self.recording_start_datetime = datetime.datetime.now()
            
            # Verify FFmpeg
            try:
                # Test to make sure FFmpeg is available
                subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               check=True,
                               timeout=2)
            except (subprocess.SubprocessError, FileNotFoundError):
                QtWidgets.QMessageBox.critical(self.parent, "Error", 
                    "FFmpeg not found. Make sure FFmpeg is installed and available in your PATH.")
                return False
                
            # Verify the selected codec is supported
            try:
                codec_check = subprocess.run(
                    ['ffmpeg', '-encoders'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=2
                )
                codec_output = codec_check.stdout.decode('utf-8')
                
                # Special handling for alaw and mulaw
                codec_to_check = codec
                if codec == "alaw":
                    codec_to_check = "pcm_alaw"
                elif codec == "mulaw":
                    codec_to_check = "pcm_mulaw"
                
                # Map of alternative codecs if primary isn't supported
                codec_alternatives = {
                    "libmp3lame": "mp3",
                    "libvorbis": "vorbis",
                    "libopus": "opus",
                    "aac": "aac"  # AAC may be available under a different name
                }
                
                if codec_to_check not in codec_output:
                    # Check if there's an alternative
                    alternative = codec_alternatives.get(codec_to_check)
                    if alternative and alternative in codec_output:
                        if codec != "alaw" and codec != "mulaw":  # Don't replace alaw/mulaw
                            codec_sel.setCurrentText(alternative)
                            codec = alternative
                            QtWidgets.QMessageBox.information(self.parent, "Information", 
                                f"Using alternative codec '{alternative}' compatible with your FFmpeg version.")
                    else:
                        if codec == "alaw" or codec == "mulaw":
                            warning_msg = (f"The codec '{codec}' (ffmpeg_codec='{codec_to_check}') might not be "
                                        f"supported by your FFmpeg version.\n\n"
                                        f"If you want to use A-law or μ-law, you might need to install a "
                                        f"more complete version of FFmpeg with support for these codecs.\n\n"
                                        f"Do you want to continue anyway?")
                            
                            reply = QtWidgets.QMessageBox.question(self.parent, "Warning", warning_msg, 
                                                                QtWidgets.QMessageBox.StandardButton.Yes | 
                                                                QtWidgets.QMessageBox.StandardButton.No)
                            
                            if reply == QtWidgets.QMessageBox.StandardButton.No:
                                codec_sel.setCurrentText("pcm_s16le (16-bit)")
                                codec = "pcm_s16le"
                        else:
                            QtWidgets.QMessageBox.warning(self.parent, "Warning", 
                                f"The codec '{codec}' might not be supported by your FFmpeg version.\n"
                                "If recording fails, try installing a more complete version of FFmpeg.")
                
                # Also check the second codec if dual recording is enabled
                if self.dual_format_enabled:
                    codec_to_check2 = codec2
                    if codec2 == "alaw":
                        codec_to_check2 = "pcm_alaw"
                    elif codec2 == "mulaw":
                        codec_to_check2 = "pcm_mulaw"
                    
                    if codec_to_check2 not in codec_output:
                        alternative2 = codec_alternatives.get(codec_to_check2)
                        if alternative2 and alternative2 in codec_output:
                            if codec2 != "alaw" and codec2 != "mulaw":
                                codec_sel2.setCurrentText(alternative2)
                                codec2 = alternative2
                                QtWidgets.QMessageBox.information(self.parent, "Information", 
                                    f"Using alternative codec '{alternative2}' for second format.")
                        else:
                            QtWidgets.QMessageBox.warning(self.parent, "Warning", 
                                f"The codec '{codec2}' for the second format might not be supported.\n"
                                "If recording fails, try a different second format.")
                                
            except Exception:
                # If we can't verify, continue anyway
                pass
            
            # Build FFmpeg command based on format and codec
            command = ['ffmpeg', '-y', '-f', 's16le', '-ar', str(self.fs),
                      '-ac', str(self.channels), '-i', 'pipe:0']
            
            # Add format-specific options
            if fmt == "wav":
                if codec == "alaw":
                    # Special configuration for alaw (8-bit)
                    command.extend(['-c:a', 'pcm_alaw'])
                elif codec == "mulaw":
                    # Special configuration for mulaw (8-bit)
                    command.extend(['-c:a', 'pcm_mulaw'])
                else:
                    command.extend(['-c:a', codec])
            elif fmt == "mp3":
                command.extend(['-c:a', codec, '-b:a', bitrate])
            elif fmt == "ogg":
                if codec == "libvorbis":
                    command.extend(['-c:a', codec, '-q:a', '4'])  # Variable quality for Vorbis
                else:
                    command.extend(['-c:a', codec, '-b:a', bitrate])
            elif fmt == "flac":
                command.extend(['-c:a', codec, '-compression_level', '8'])  # Maximum compression
            elif fmt == "m4a":
                if "libfdk_aac" in codec:
                    # Configure HE-AAC based on version
                    base_codec = codec.split(" ")[0]
                    if "v1" in codec_full:
                        # HE-AAC v1
                        command.extend([
                            '-c:a', base_codec,
                            '-profile:a', 'aac_he',  # HE-AAC v1 profile
                            '-b:a', bitrate
                        ])
                    elif "v2" in codec_full:
                        # HE-AAC v2
                        command.extend([
                            '-c:a', base_codec,
                            '-profile:a', 'aac_he_v2',  # HE-AAC v2 profile
                            '-b:a', bitrate
                        ])
                    else:
                        # Standard AAC with libfdk_aac
                        command.extend(['-c:a', base_codec, '-b:a', bitrate])
                else:
                    # Standard AAC
                    command.extend(['-c:a', codec, '-b:a', bitrate, '-strict', 'experimental'])
            
            # Add output file
            command.append(self.output_file)
            
            # Store the FFmpeg command for logging
            self.ffmpeg_command = command
            
            # Create second command for dual recording if enabled
            if self.dual_format_enabled:
                command2 = ['ffmpeg', '-y', '-f', 's16le', '-ar', str(self.fs),
                           '-ac', str(self.channels), '-i', 'pipe:0']
                
                # Add format-specific options for second format
                if fmt2 == "wav":
                    if codec2 == "alaw":
                        command2.extend(['-c:a', 'pcm_alaw'])
                    elif codec2 == "mulaw":
                        command2.extend(['-c:a', 'pcm_mulaw'])
                    else:
                        command2.extend(['-c:a', codec2])
                elif fmt2 == "mp3":
                    command2.extend(['-c:a', codec2, '-b:a', bitrate2])
                elif fmt2 == "ogg":
                    if codec2 == "libvorbis":
                        command2.extend(['-c:a', codec2, '-q:a', '4'])
                    else:
                        command2.extend(['-c:a', codec2, '-b:a', bitrate2])
                elif fmt2 == "flac":
                    command2.extend(['-c:a', codec2, '-compression_level', '8'])
                elif fmt2 == "m4a":
                    if "libfdk_aac" in codec2:
                        # Configure HE-AAC based on version
                        base_codec2 = codec2.split(" ")[0]
                        if "v1" in codec_full2:
                            command2.extend([
                                '-c:a', base_codec2,
                                '-profile:a', 'aac_he',
                                '-b:a', bitrate2
                            ])
                        elif "v2" in codec_full2:
                            command2.extend([
                                '-c:a', base_codec2,
                                '-profile:a', 'aac_he_v2',
                                '-b:a', bitrate2
                            ])
                        else:
                            command2.extend(['-c:a', base_codec2, '-b:a', bitrate2])
                    else:
                        command2.extend(['-c:a', codec2, '-b:a', bitrate2, '-strict', 'experimental'])
                
                # Add second output file
                command2.append(self.output_file2)
                
                # Store the second FFmpeg command for logging
                self.ffmpeg_command2 = command2
            
            # Log commands for debugging
            print(f"Executing FFmpeg command: {' '.join(command)}")
            if self.dual_format_enabled:
                print(f"Executing second FFmpeg command: {' '.join(command2)}")
            
            try:
                # Start first FFmpeg process
                self.ffmpeg_process = subprocess.Popen(command, 
                                                      stdin=subprocess.PIPE, 
                                                      stderr=subprocess.PIPE, 
                                                      stdout=subprocess.PIPE,
                                                      bufsize=self.chunk*4)
                
                # Start second FFmpeg process if dual recording is enabled
                if self.dual_format_enabled:
                    self.ffmpeg_process2 = subprocess.Popen(command2, 
                                                          stdin=subprocess.PIPE, 
                                                          stderr=subprocess.PIPE, 
                                                          stdout=subprocess.PIPE,
                                                          bufsize=self.chunk*4)
                
                # Initialize audio stream
                self.stream = self.audio.open(format=pyaudio.paInt16,
                                           channels=self.channels,
                                           rate=self.fs,
                                           input=True,
                                           input_device_index=device_index,
                                           frames_per_buffer=self.chunk,
                                           stream_callback=self.audio_callback)

                # Create initial log file
                create_recording_log(
                    self.log_file,
                    self.output_file,
                    command,
                    self.recording_start_datetime
                )
                
                # Create second log file if dual recording is enabled
                if self.dual_format_enabled:
                    create_recording_log(
                        self.log_file2,
                        self.output_file2,
                        command2,
                        self.recording_start_datetime
                    )
                
                # Start recording
                self.recording_start_time = time.time()
                return True
                
            except Exception as e:
                # Clean up if there's an error
                if self.ffmpeg_process:
                    self.ffmpeg_process.terminate()
                    self.ffmpeg_process = None
                    
                if self.dual_format_enabled and self.ffmpeg_process2:
                    self.ffmpeg_process2.terminate()
                    self.ffmpeg_process2 = None
                    
                raise Exception(f"Error initializing audio stream: {str(e)}")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.parent, "Error", f"Unable to start recording: {str(e)}")
            self.parent.statusBar().showMessage(f"Error: {str(e)}")
            return False
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Audio stream callback that writes data to FFmpeg process(es)"""
        self.frames.append(in_data)
        try:
            # Write to the first FFmpeg process
            if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                try:
                    self.ffmpeg_process.stdin.write(in_data)
                except BrokenPipeError:
                    # FFmpeg process has closed or has a broken pipe
                    pass
                except Exception as e:
                    # Log other errors but only once
                    if not hasattr(self, '_logged_write_error1'):
                        self._logged_write_error1 = True
                        self.parent.statusBar().showMessage(f"Write error (1): {str(e)}")
            
            # Write to the second FFmpeg process if dual recording is enabled
            if self.dual_format_enabled and self.ffmpeg_process2 and self.ffmpeg_process2.poll() is None:
                try:
                    self.ffmpeg_process2.stdin.write(in_data)
                except BrokenPipeError:
                    # Second FFmpeg process has closed or has a broken pipe
                    pass
                except Exception as e:
                    # Log other errors but only once
                    if not hasattr(self, '_logged_write_error2'):
                        self._logged_write_error2 = True
                        self.parent.statusBar().showMessage(f"Write error (2): {str(e)}")
                        
        except Exception:
            pass
        return (in_data, pyaudio.paContinue)
    
    def stop_recording(self):
        """Stop recording and finalize the output file(s)"""
        try:
            # Record end time
            recording_end_datetime = datetime.datetime.now()
            
            # Stop audio stream
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            # Close first FFmpeg process safely
            if self.ffmpeg_process:
                try:
                    # Check if process is still active
                    if self.ffmpeg_process.poll() is None:
                        try:
                            self.ffmpeg_process.stdin.close()
                        except BrokenPipeError:
                            # Ignore broken pipe errors
                            pass
                        except Exception as e:
                            print(f"Warning (1): {e}")
                        
                        # Wait for FFmpeg to terminate
                        try:
                            self.ffmpeg_process.wait(timeout=5)  # Wait max 5 seconds
                        except subprocess.TimeoutExpired:
                            self.ffmpeg_process.terminate()  # Force terminate if blocked
                            time.sleep(0.5)
                            if self.ffmpeg_process.poll() is None:
                                self.ffmpeg_process.kill()  # Kill process if still running
                                
                        # Check for errors
                        if self.ffmpeg_process.returncode != 0:
                            stderr_output = self.ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                            print(f"FFmpeg error (1): {stderr_output}")
                            
                            # Identify common errors and provide more detailed messages
                            if "Unsupported codec" in stderr_output:
                                QtWidgets.QMessageBox.warning(self.parent, "Codec Error (1)", 
                                    "The selected codec is not supported by your FFmpeg version.\n\n"
                                    "To resolve this issue:\n"
                                    "1. Use WAV format with pcm_s16le codec\n"
                                    "2. Reinstall FFmpeg with extended codec support\n"
                                    "   - macOS: brew install ffmpeg --with-fdk-aac\n"
                                    "   - Ubuntu: sudo apt install ffmpeg libavcodec-extra")
                            elif "Error opening filters" in stderr_output:
                                QtWidgets.QMessageBox.warning(self.parent, "Filter Error (1)", 
                                    "Error in audio processing. The requested filters are not available.")
                            elif "Unknown encoder" in stderr_output:
                                QtWidgets.QMessageBox.warning(self.parent, "Encoder Error (1)", 
                                    "The selected encoder is not available in your FFmpeg installation.\n"
                                    "Try selecting another format (WAV is always supported).")
                except Exception as e:
                    print(f"Error closing FFmpeg process (1): {e}")
                
                self.ffmpeg_process = None
            
            # Close second FFmpeg process if dual recording is enabled
            if self.dual_format_enabled and self.ffmpeg_process2:
                try:
                    # Check if process is still active
                    if self.ffmpeg_process2.poll() is None:
                        try:
                            self.ffmpeg_process2.stdin.close()
                        except BrokenPipeError:
                            # Ignore broken pipe errors
                            pass
                        except Exception as e:
                            print(f"Warning (2): {e}")
                        
                        # Wait for FFmpeg to terminate
                        try:
                            self.ffmpeg_process2.wait(timeout=5)  # Wait max 5 seconds
                        except subprocess.TimeoutExpired:
                            self.ffmpeg_process2.terminate()  # Force terminate if blocked
                            time.sleep(0.5)
                            if self.ffmpeg_process2.poll() is None:
                                self.ffmpeg_process2.kill()  # Kill process if still running
                                
                        # Check for errors
                        if self.ffmpeg_process2.returncode != 0:
                            stderr_output = self.ffmpeg_process2.stderr.read().decode('utf-8', errors='ignore')
                            print(f"FFmpeg error (2): {stderr_output}")
                            
                            # Identify common errors and provide more detailed messages
                            if "Unsupported codec" in stderr_output:
                                QtWidgets.QMessageBox.warning(self.parent, "Codec Error (2)", 
                                    "The second codec is not supported by your FFmpeg version.\n\n"
                                    "Try using WAV format with pcm_s16le codec for the second format.")
                except Exception as e:
                    print(f"Error closing FFmpeg process (2): {e}")
                
                self.ffmpeg_process2 = None
            
            # Check if first file was created successfully
            first_file_success = os.path.exists(self.output_file) and os.path.getsize(self.output_file) > 0
            
            # Check if second file was created successfully (if dual recording was enabled)
            second_file_success = False
            if self.dual_format_enabled:
                second_file_success = os.path.exists(self.output_file2) and os.path.getsize(self.output_file2) > 0
            
            # Update logs and calculate hashes for successful recordings
            if first_file_success:
                # Calculate file hash
                file_hash = calculate_file_hash(self.output_file)
                
                # Update log file
                update_recording_log(
                    self.log_file, 
                    recording_end_datetime,
                    file_hash
                )
            
            if self.dual_format_enabled and second_file_success:
                # Calculate file hash for second file
                file_hash2 = calculate_file_hash(self.output_file2)
                
                # Update second log file
                update_recording_log(
                    self.log_file2, 
                    recording_end_datetime,
                    file_hash2
                )
            
            # Return success based on first file (primary file)
            if first_file_success:
                return True
            else:
                # First file failed - show error message
                err_output = ""
                if hasattr(self, 'ffmpeg_process') and self.ffmpeg_process and hasattr(self.ffmpeg_process, 'stderr'):
                    try:
                        err_output = self.ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                    except:
                        pass
                
                # Show error message with details if available
                error_msg = "Recording was not completed successfully. The resulting file is empty or wasn't created.\n\n"
                error_msg += "Possible causes:\n"
                error_msg += "- Unsupported codec or format\n"
                error_msg += "- FFmpeg error during encoding\n"
                error_msg += "- Insufficient permissions to write to output folder\n\n"
                error_msg += "Recommendations:\n"
                error_msg += "- Select WAV format with pcm_s16le codec (always supported)\n"
                error_msg += "- Verify FFmpeg is installed correctly\n"
                
                if err_output:
                    error_msg += f"\nFFmpeg error details:\n{err_output[:300]}..."
                    
                QtWidgets.QMessageBox.warning(self.parent, "Recording Error", error_msg)
                
                self.parent.statusBar().showMessage("Error: Recording was not saved correctly")
                return False
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.parent, "Warning", f"Problem stopping recording: {str(e)}")
            return False
            
    def get_input_devices(self):
        """Get a list of available input devices"""
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info["maxInputChannels"] > 0:
                devices.append((device_info["name"], i))
        return devices
        
    def cleanup(self):
        """Clean up resources when closing"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            try:
                self.ffmpeg_process.terminate()
                time.sleep(0.5)
                if self.ffmpeg_process.poll() is None:
                    self.ffmpeg_process.kill()
            except:
                pass
                
        if self.ffmpeg_process2 and self.ffmpeg_process2.poll() is None:
            try:
                self.ffmpeg_process2.terminate()
                time.sleep(0.5)
                if self.ffmpeg_process2.poll() is None:
                    self.ffmpeg_process2.kill()
            except:
                pass
                
        self.audio.terminate()