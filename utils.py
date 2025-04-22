"""
Utility Functions Module

Contains helper functions and utilities for the Audio Pro Advanced application.
"""

import os
import shutil
import subprocess
import sys
import hashlib
import datetime

# Define application version - used consistently across the application
APP_VERSION = "1.0.1"

def create_temp_directory(dir_path):
    """
    Create a temporary directory if it doesn't exist
    
    Args:
        dir_path: Path to the temporary directory
        
    Returns:
        bool: True if directory exists or was created successfully
    """
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            return True
        except Exception as e:
            print(f"Error creating temp directory: {e}")
            return False
    return True

def clean_temp_directory(dir_path):
    """
    Remove temporary directory and all its contents
    
    Args:
        dir_path: Path to the temporary directory
        
    Returns:
        bool: True if operation was successful
    """
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            return True
        except Exception as e:
            print(f"Error cleaning temp directory: {e}")
            return False
    return True

def open_file_with_default_app(file_path):
    """
    Open a file with the system's default application
    
    Args:
        file_path: Path to the file to open
        
    Returns:
        bool: True if operation was successful
    """
    try:
        if not os.path.exists(file_path):
            return False
            
        if sys.platform == 'win32':
            os.startfile(file_path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', file_path])
        else:  # Linux
            subprocess.run(['xdg-open', file_path])
        return True
    except Exception as e:
        print(f"Error opening file: {e}")
        return False

def open_directory(directory_path):
    """
    Open a directory with the system's file explorer
    
    Args:
        directory_path: Path to the directory to open
        
    Returns:
        bool: True if operation was successful
    """
    try:
        if not os.path.exists(directory_path):
            return False
            
        if sys.platform == 'win32':
            os.startfile(directory_path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', directory_path])
        else:  # Linux
            subprocess.run(['xdg-open', directory_path])
        return True
    except Exception as e:
        print(f"Error opening directory: {e}")
        return False

def format_time(seconds, include_milliseconds=True):
    """
    Format seconds into hours:minutes:seconds.milliseconds
    
    Args:
        seconds: Number of seconds (float with milliseconds)
        include_milliseconds: Whether to include milliseconds in output
        
    Returns:
        str: Formatted time string (00:00:00.000)
    """
    # Split seconds into whole seconds and milliseconds
    whole_seconds = int(seconds)
    milliseconds = int((seconds - whole_seconds) * 1000)
    
    # Calculate hours, minutes, seconds
    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    seconds = whole_seconds % 60
    
    # Format with or without milliseconds
    if include_milliseconds:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_available_codecs():
    """
    Get a list of available audio codecs by querying FFmpeg
    
    Returns:
        dict: Dictionary of available codecs by format
    """
    codecs = {
        "wav": ["pcm_s16le (16-bit)"],
        "mp3": ["libmp3lame"],
        "ogg": ["libvorbis"],
        "flac": ["flac"],
        "m4a": ["aac"]
    }
    
    try:
        # Query FFmpeg for available encoders
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=2
        )
        
        output = result.stdout.decode('utf-8')
        
        # Check for additional codecs
        if "pcm_s24le" in output:
            codecs["wav"].append("pcm_s24le (24-bit)")
        if "pcm_f32le" in output:
            codecs["wav"].append("pcm_f32le (32-bit float)")
        if "pcm_alaw" in output or "alaw" in output:
            codecs["wav"].append("alaw (8-bit A-law)")
        if "pcm_mulaw" in output or "mulaw" in output:
            codecs["wav"].append("mulaw (8-bit μ-law)")
        if "libopus" in output:
            codecs["ogg"].append("libopus")
            
    except Exception as e:
        print(f"Warning: Unable to query FFmpeg for codecs: {e}")
        # Use default codecs list if FFmpeg query fails
        codecs["wav"] = [
            "pcm_s16le (16-bit)", 
            "pcm_s24le (24-bit)", 
            "pcm_f32le (32-bit float)", 
            "alaw (8-bit A-law)", 
            "mulaw (8-bit μ-law)"
        ]
        
    return codecs

def calculate_file_hash(file_path, hash_type='sha256'):
    """
    Calculate hash of a file
    
    Args:
        file_path: Path to the file
        hash_type: Type of hash (md5, sha1, sha256, etc.)
        
    Returns:
        str: Hash value as hexadecimal string
    """
    if not os.path.exists(file_path):
        return "File not found"
        
    try:
        hash_obj = None
        if hash_type.lower() == 'md5':
            hash_obj = hashlib.md5()
        elif hash_type.lower() == 'sha1':
            hash_obj = hashlib.sha1()
        else:  # Default to sha256
            hash_obj = hashlib.sha256()
            
        with open(file_path, 'rb') as f:
            # Read file in chunks of 4K
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
                
        return hash_obj.hexdigest()
    except Exception as e:
        return f"Error calculating hash: {str(e)}"

def create_recording_log(log_file_path, audio_file_path, ffmpeg_command, start_time, end_time=None):
    """
    Create a log file for a recording session
    
    Args:
        log_file_path: Path to save the log file
        audio_file_path: Path to the recorded audio file
        ffmpeg_command: The FFmpeg command used for recording
        start_time: Recording start time (datetime object)
        end_time: Recording end time (datetime object), or None if recording is in progress
    
    Returns:
        bool: True if log was created successfully
    """
    try:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Format times with microseconds
        start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Truncate to milliseconds
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if end_time else "In Progress"
        
        # Calculate duration
        duration_str = "In Progress"
        if end_time:
            duration = end_time - start_time
            total_seconds = duration.total_seconds()
            # Format duration as 00:00:00.000
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            milliseconds = int((total_seconds - int(total_seconds)) * 1000)
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            
        # Calculate file hash if the file exists
        file_hash = "File not found"
        file_size_kb = "N/A"
        if os.path.exists(audio_file_path):
            file_hash = calculate_file_hash(audio_file_path)
            file_size_bytes = os.path.getsize(audio_file_path)
            if file_size_bytes < 1024:
                file_size_kb = f"{file_size_bytes} B"
            elif file_size_bytes < 1024 * 1024:
                file_size_kb = f"{file_size_bytes / 1024:.2f} KB"
            else:
                file_size_kb = f"{file_size_bytes / (1024 * 1024):.2f} MB"
            
        # Format command as string if it's a list
        if isinstance(ffmpeg_command, list):
            ffmpeg_command_str = " ".join(ffmpeg_command)
        else:
            ffmpeg_command_str = str(ffmpeg_command)
            
        # Create log content
        log_content = f"""
KVSrecorder v{APP_VERSION} - RECORDING LOG
==================================

File Information:
----------------
Filename: {os.path.basename(audio_file_path)}
File Path: {audio_file_path}
File Size: {file_size_kb}
File Hash (SHA-256): {file_hash}

Recording Session:
----------------
Start Time: {start_time_str}
End Time: {end_time_str}
Duration: {duration_str}

FFmpeg Command:
----------------
{ffmpeg_command_str}

System Information:
----------------
Platform: {sys.platform}
Python Version: {sys.version}
Software Version: {APP_VERSION}
Log Created: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}
"""
        
        # Write to log file
        with open(log_file_path, 'w') as f:
            f.write(log_content)
            
        return True
    except Exception as e:
        print(f"Error creating recording log: {e}")
        return False

def update_recording_log(log_file_path, end_time=None, file_hash=None):
    """
    Update an existing recording log with end time and file hash
    
    Args:
        log_file_path: Path to the log file
        end_time: Recording end time (datetime object)
        file_hash: Hash value of the file
        
    Returns:
        bool: True if log was updated successfully
    """
    try:
        if not os.path.exists(log_file_path):
            return False
            
        # Read existing log
        with open(log_file_path, 'r') as f:
            log_content = f.read()
            
        # Update end time
        if end_time:
            end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Truncate to milliseconds
            log_content = log_content.replace("End Time: In Progress", f"End Time: {end_time_str}")
            
            # Calculate and update duration
            start_time_str = None
            for line in log_content.split('\n'):
                if line.startswith("Start Time:"):
                    start_time_str = line.replace("Start Time: ", "").strip()
                    break
                    
            if start_time_str:
                try:
                    start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    try:
                        # Try without milliseconds if parse fails
                        start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        start_time = None
                        
                if start_time:
                    duration = end_time - start_time
                    total_seconds = duration.total_seconds()
                    # Format duration as 00:00:00.000
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    seconds = int(total_seconds % 60)
                    milliseconds = int((total_seconds - int(total_seconds)) * 1000)
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                    log_content = log_content.replace("Duration: In Progress", f"Duration: {duration_str}")
                    
            # Also update file size if file path can be found
            file_path = None
            for line in log_content.split('\n'):
                if line.startswith("File Path:"):
                    file_path = line.replace("File Path: ", "").strip()
                    break
                    
            if file_path and os.path.exists(file_path):
                file_size_bytes = os.path.getsize(file_path)
                if file_size_bytes < 1024:
                    file_size_str = f"{file_size_bytes} B"
                elif file_size_bytes < 1024 * 1024:
                    file_size_str = f"{file_size_bytes / 1024:.2f} KB"
                else:
                    file_size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"
                    
                # Replace file size line (handle both N/A and actual values)
                if "File Size: N/A" in log_content:
                    log_content = log_content.replace("File Size: N/A", f"File Size: {file_size_str}")
                else:
                    # Try to find and replace existing file size
                    import re
                    file_size_pattern = r"File Size: .*$"
                    log_content = re.sub(file_size_pattern, f"File Size: {file_size_str}", log_content, flags=re.MULTILINE)
        
        # Update file hash
        if file_hash:
            log_content = log_content.replace("File Hash (SHA-256): File not found", f"File Hash (SHA-256): {file_hash}")
            
        # Write updated log
        with open(log_file_path, 'w') as f:
            f.write(log_content)
            
        return True
    except Exception as e:
        print(f"Error updating recording log: {e}")
        return False