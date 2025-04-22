# KVSrecorder - Known Voice Samples Recorder

![KVSrecorder Banner](https://img.shields.io/badge/KVSrecorder-Known%20Voice%20Samples%20Recorder-blue)
![License](https://img.shields.io/badge/License-GNU%20GPLv3-green)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-brightgreen)

KVSrecorder is a professional-grade audio recording and analysis application designed for capturing high-quality voice samples with comprehensive metadata, particularly for forensic applications and voice analysis. It provides a clean, user-friendly interface while offering advanced technical capabilities for audio professionals.

## Overview

This tool is designed to produce legally defensible voice recordings with detailed metadata, waveform analysis, and spectrograms. KVSrecorder focuses on audio chain integrity through detailed logs, hash verification, and comprehensive reports suitable for evidentiary use.

## Features

- **Professional Audio Recording**: Multi-format recording with customizable sample rates, bit depths, and codecs
- **Dual Format Recording**: Simultaneously record in two different formats (e.g., WAV + MP3)
- **Real-time Visualization**: Live waveform display and level meter during recording
- **Comprehensive Reports**: Generate detailed PDF reports with waveforms, spectrograms, and complete technical metadata
- **Audio Integrity**: SHA-256 hash verification and detailed logging of all recording parameters
- **Format Support**: Records in WAV, MP3, OGG, FLAC, and M4A with various codec options
- **Modern Interface**: Clean, responsive GUI with a professional blue and white theme
- **Technical Analysis**: Audio statistics including RMS level, peak measurements, and dynamic range

## Installation

### Prerequisites

- Python 3.8 or higher
- PyQt6
- FFmpeg (accessible in your system PATH)
- Required Python packages (see requirements.txt)

```bash
# Clone the repository
git clone https://github.com/yourusername/KVSrecorder.git
cd KVSrecorder

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the application
python main.py
```

### Basic Recording Workflow

1. Select your input device from the dropdown
2. Choose audio format, codec, and sample rate settings
3. Enable dual format recording if needed
4. Set the destination folder
5. Click "Start Recording" to begin
6. Monitor real-time levels and waveform
7. Click "Stop Recording" when finished
8. Generate a detailed report if desired

### Audio Settings

- **Format**: WAV, MP3, OGG, FLAC, M4A
- **Codec Options**:
  - WAV: PCM 16/24-bit, 32-bit float, A-law/μ-law
  - MP3: libmp3lame with variable bitrates
  - OGG: Vorbis and Opus codecs
  - FLAC: Lossless compression
  - M4A: AAC encoding
- **Sample Rates**: 8kHz, 44.1kHz, 48kHz, 96kHz
- **Bitrates**: 128k, 192k, 256k, 320k (for lossy formats)

### Report Generation

KVSrecorder generates comprehensive PDF reports that include:

- Complete audio file information and metadata
- Recording date, time, and duration
- File hash for integrity verification
- Technical specifications (format, codec, bit depth, etc.)
- Audio analysis metrics (RMS, peak, dynamic range)
- Waveform visualization and spectrogram

## Core Components

- **UI Components**: Main application window and interface elements
- **Audio Recorder**: Handles recording functionality via PyAudio and FFmpeg
- **Report Generator**: Creates detailed PDF reports with visualizations
- **File Monitor**: Tracks recording status and file growth
- **Utilities**: Hash calculation, file handling, and time formatting

## License

This project is licensed under the GNU General Public License v3.0 (GNU GPLv3) - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- Utilizes [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework
- Built with [FFmpeg](https://ffmpeg.org/) for audio encoding
- Uses [librosa](https://librosa.org/) for audio analysis and visualization
- PDF reports generated with [FPDF](https://pyfpdf.readthedocs.io/)
