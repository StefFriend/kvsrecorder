"""
Audio Pro Advanced - Main Application Entry Point

A professional audio recording and analysis application with advanced features
including waveform visualization, spectrograms, and detailed audio reports.
"""

import sys
import os
from PyQt6 import QtWidgets, QtGui

from ui_components import AudioProAdvanced

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern and consistent style across all platforms
    
    # Customize application palette
    palette = app.palette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#202124"))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#f8f9fa"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#202124"))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#202124"))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#1a73e8"))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#1a73e8"))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(palette)
    
    window = AudioProAdvanced()
    window.show()
    sys.exit(app.exec())