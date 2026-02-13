"""OCR Screenshot Dialog - Extract text from images using OCR."""

from __future__ import annotations

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFileDialog, QMessageBox, QProgressBar,
    QGroupBox, QListWidget, QListWidgetItem, QSplitter,
    QCheckBox, QComboBox, QSpinBox, QFormLayout, QWidget
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QPixmap, QFont, QIcon


class OCRWorker(QThread):
    """Worker thread for OCR processing."""
    
    progress = Signal(str)  # status message
    finished = Signal(list)  # extracted strings
    error = Signal(str)     # error message
    
    def __init__(self, image_path: str, language: str = 'eng', psm: int = 6):
        super().__init__()
        self._image_path = image_path
        self._language = language
        self._psm = psm
        
    def run(self):
        try:
            self.progress.emit(self.tr("Checking tesseract installation..."))
            
            # Check if tesseract is installed
            if not self._check_tesseract():
                self.error.emit(self.tr("Tesseract not installed. Please install tesseract-ocr."))
                return
            
            self.progress.emit(self.tr("Processing image..."))
            
            # Run OCR
            strings = self._run_ocr()
            self.finished.emit(strings)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _check_tesseract(self) -> bool:
        """Check if tesseract is available."""
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _run_ocr(self) -> List[str]:
        """Run tesseract OCR on the image."""
        # Create temporary file for output
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
            temp_output = temp_file.name
        
        try:
            # Run tesseract
            cmd = [
                'tesseract', 
                self._image_path, 
                temp_output[:-4],  # Remove .txt extension, tesseract adds it
                '-l', self._language,
                '--psm', str(self._psm)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise RuntimeError(f"Tesseract failed: {result.stderr}")
            
            # Read output
            with open(temp_output, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Split into lines and filter out empty ones
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            return lines
            
        finally:
            # Clean up temporary file
            try:
                Path(temp_output).unlink(missing_ok=True)
            except Exception:
                pass


class ImagePreviewLabel(QLabel):
    """Label that shows image preview and allows clicking."""
    
    clicked = Signal()
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 200)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #cccccc;
                border-radius: 10px;
                background-color: #f9f9f9;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setText(self.tr("Click to select image\n(PNG, JPG, GIF)"))
        self.setScaledContents(True)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def set_image(self, pixmap: QPixmap):
        """Set the image to display."""
        if not pixmap.isNull():
            # Scale image to fit while maintaining aspect ratio
            scaled = pixmap.scaled(
                self.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled)
        else:
            self.clear()
            self.setText(self.tr("Click to select image\n(PNG, JPG, GIF)"))


class OCRDialog(QDialog):
    """Dialog for extracting text from images using OCR."""
    
    strings_extracted = Signal(list)  # Emitted when strings are ready for PO creation
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("OCR Screenshot"))
        self.setModal(True)
        self.resize(1000, 700)
        
        self._current_image_path = ""
        self._ocr_worker = None
        
        self._setup_ui()
        self._check_tesseract_availability()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Image and settings
        left_widget = self._create_left_panel()
        splitter.addWidget(left_widget)
        
        # Right side: Results
        right_widget = self._create_right_panel()
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Status label
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._browse_btn = QPushButton(self.tr("Browse Image..."))
        self._browse_btn.clicked.connect(self._browse_image)
        button_layout.addWidget(self._browse_btn)
        
        self._process_btn = QPushButton(self.tr("Extract Text"))
        self._process_btn.clicked.connect(self._process_image)
        self._process_btn.setEnabled(False)
        button_layout.addWidget(self._process_btn)
        
        button_layout.addStretch()
        
        self._create_po_btn = QPushButton(self.tr("Create PO from Extracted Strings"))
        self._create_po_btn.clicked.connect(self._create_po_file)
        self._create_po_btn.setEnabled(False)
        button_layout.addWidget(self._create_po_btn)
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_left_panel(self):
        """Create the left panel with image preview and settings."""
        widget = QVBoxLayout()
        
        # Image preview
        image_group = QGroupBox(self.tr("Image"))
        image_layout = QVBoxLayout(image_group)
        
        self._image_preview = ImagePreviewLabel()
        self._image_preview.clicked.connect(self._browse_image)
        image_layout.addWidget(self._image_preview)
        
        widget.addWidget(image_group)
        
        # OCR Settings
        settings_group = QGroupBox(self.tr("OCR Settings"))
        settings_layout = QFormLayout(settings_group)
        
        # Language
        self._language_combo = QComboBox()
        self._language_combo.addItems([
            ('eng', 'English'),
            ('deu', 'German'),
            ('fra', 'French'),
            ('spa', 'Spanish'),
            ('ita', 'Italian'),
            ('por', 'Portuguese'),
            ('rus', 'Russian'),
            ('jpn', 'Japanese'),
            ('chi_sim', 'Chinese Simplified'),
            ('chi_tra', 'Chinese Traditional'),
            ('kor', 'Korean'),
            ('ara', 'Arabic'),
            ('hin', 'Hindi'),
            ('nld', 'Dutch'),
            ('swe', 'Swedish'),
            ('nor', 'Norwegian'),
            ('dan', 'Danish'),
            ('fin', 'Finnish'),
            ('pol', 'Polish'),
            ('ces', 'Czech'),
            ('hun', 'Hungarian')
        ])
        settings_layout.addRow(self.tr("Language:"), self._language_combo)
        
        # Page Segmentation Mode
        self._psm_combo = QComboBox()
        psm_modes = [
            (0, self.tr("Orientation and script detection (OSD) only")),
            (1, self.tr("Automatic page segmentation with OSD")),
            (2, self.tr("Automatic page segmentation, but no OSD, or OCR")),
            (3, self.tr("Fully automatic page segmentation, but no OSD")),
            (4, self.tr("Assume a single column of text of variable sizes")),
            (5, self.tr("Assume a single uniform block of vertically aligned text")),
            (6, self.tr("Assume a single uniform block of text")),
            (7, self.tr("Treat the image as a single text line")),
            (8, self.tr("Treat the image as a single word")),
            (9, self.tr("Treat the image as a single word in a circle")),
            (10, self.tr("Treat the image as a single character")),
            (11, self.tr("Sparse text. Find as much text as possible in no particular order")),
            (12, self.tr("Sparse text with OSD")),
            (13, self.tr("Raw line. Treat the image as a single text line, bypassing hacks"))
        ]
        
        for value, description in psm_modes:
            self._psm_combo.addItem(f"{value}: {description}", value)
        
        self._psm_combo.setCurrentIndex(6)  # Default to mode 6
        settings_layout.addRow(self.tr("Page Segmentation:"), self._psm_combo)
        
        # Preprocessing options
        self._preprocess_check = QCheckBox(self.tr("Apply preprocessing"))
        self._preprocess_check.setChecked(True)
        self._preprocess_check.setToolTip(self.tr("Apply image preprocessing to improve OCR accuracy"))
        settings_layout.addRow(self._preprocess_check)
        
        widget.addWidget(settings_group)
        widget.addStretch()
        
        container = QWidget()
        container.setLayout(widget)
        return container
    
    def _create_right_panel(self):
        """Create the right panel with extracted text results."""
        widget = QVBoxLayout()
        
        # Extracted strings
        results_group = QGroupBox(self.tr("Extracted Text"))
        results_layout = QVBoxLayout(results_group)
        
        # Filter/search
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(self.tr("Filter:")))
        
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(self.tr("Filter extracted strings..."))
        self._filter_edit.textChanged.connect(self._filter_strings)
        filter_layout.addWidget(self._filter_edit)
        
        results_layout.addLayout(filter_layout)
        
        # Strings list
        self._strings_list = QListWidget()
        self._strings_list.setSelectionMode(QListWidget.MultiSelection)
        results_layout.addWidget(self._strings_list)
        
        # Selection tools
        selection_layout = QHBoxLayout()
        
        select_all_btn = QPushButton(self.tr("Select All"))
        select_all_btn.clicked.connect(self._strings_list.selectAll)
        selection_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton(self.tr("Select None"))
        select_none_btn.clicked.connect(self._strings_list.clearSelection)
        selection_layout.addWidget(select_none_btn)
        
        selection_layout.addStretch()
        
        remove_btn = QPushButton(self.tr("Remove Selected"))
        remove_btn.clicked.connect(self._remove_selected_strings)
        selection_layout.addWidget(remove_btn)
        
        results_layout.addLayout(selection_layout)
        
        widget.addWidget(results_group)
        
        # Raw text output
        raw_group = QGroupBox(self.tr("Raw OCR Output"))
        raw_layout = QVBoxLayout(raw_group)
        
        self._raw_text = QTextEdit()
        self._raw_text.setMaximumHeight(150)
        self._raw_text.setFont(QFont("Courier", 9))
        self._raw_text.setReadOnly(True)
        raw_layout.addWidget(self._raw_text)
        
        widget.addWidget(raw_group)
        
        container = QWidget()
        container.setLayout(widget)
        return container
    
    def _check_tesseract_availability(self):
        """Check if tesseract is available and show status."""
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.split('\n')[0] if result.stdout else "Unknown version"
                self._status_label.setText(self.tr("✓ Tesseract available: %1").arg(version))
                self._status_label.setStyleSheet("color: green;")
            else:
                self._show_tesseract_error()
        except (subprocess.SubprocessError, FileNotFoundError):
            self._show_tesseract_error()
    
    def _show_tesseract_error(self):
        """Show tesseract installation error."""
        self._status_label.setText("⚠ Tesseract not found. Please install tesseract-ocr.")
        self._status_label.setStyleSheet("color: red;")
        self._process_btn.setEnabled(False)
        
        # Show installation instructions
        QMessageBox.information(
            self, 
            self.tr("Tesseract Required"),
            self.tr(
                "OCR functionality requires tesseract-ocr to be installed.\n\n"
                "Installation instructions:\n"
                "• macOS: brew install tesseract\n"
                "• Ubuntu/Debian: sudo apt install tesseract-ocr\n"
                "• Windows: Download from GitHub releases\n"
                "• Arch Linux: sudo pacman -S tesseract"
            )
        )
    
    def _browse_image(self):
        """Browse for image file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Image"),
            "",
            self.tr("Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.tiff)")
        )
        
        if file_path:
            self._load_image(file_path)
    
    def _load_image(self, file_path: str):
        """Load and display selected image."""
        self._current_image_path = file_path
        
        # Load and display image
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self._image_preview.set_image(pixmap)
            self._process_btn.setEnabled(True)
            self._status_label.setText(self.tr("Image loaded: %1").arg(Path(file_path).name))
            self._status_label.setStyleSheet("color: blue;")
        else:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Could not load image."))
    
    def _process_image(self):
        """Start OCR processing."""
        if not self._current_image_path:
            return
        
        # Get settings
        language_code = self._language_combo.currentData() or 'eng'
        psm_mode = self._psm_combo.currentData() or 6
        
        # Start OCR worker
        self._ocr_worker = OCRWorker(self._current_image_path, language_code, psm_mode)
        self._ocr_worker.progress.connect(self._on_ocr_progress)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        
        # Update UI
        self._process_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        
        self._ocr_worker.start()
    
    def _on_ocr_progress(self, message: str):
        """Handle OCR progress update."""
        self._status_label.setText(message)
    
    def _on_ocr_finished(self, strings: List[str]):
        """Handle OCR completion."""
        self._progress_bar.setVisible(False)
        self._process_btn.setEnabled(True)
        
        if strings:
            self._status_label.setText(self.tr("✓ OCR completed. Found %1 text strings.").arg(len(strings)))
            self._status_label.setStyleSheet("color: green;")
            
            # Populate strings list
            self._strings_list.clear()
            for string in strings:
                if string.strip():  # Only add non-empty strings
                    item = QListWidgetItem(string)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self._strings_list.addItem(item)
            
            # Show raw text
            self._raw_text.setPlainText('\n'.join(strings))
            
            # Enable PO creation
            self._create_po_btn.setEnabled(True)
        else:
            self._status_label.setText("⚠ No text found in image.")
            self._status_label.setStyleSheet("color: orange;")
    
    def _on_ocr_error(self, error: str):
        """Handle OCR error."""
        self._progress_bar.setVisible(False)
        self._process_btn.setEnabled(True)
        
        self._status_label.setText(self.tr("✗ OCR failed: %1").arg(error))
        self._status_label.setStyleSheet("color: red;")
        
        QMessageBox.warning(self, self.tr("OCR Error"), error)
    
    def _filter_strings(self, text: str):
        """Filter displayed strings based on search text."""
        for i in range(self._strings_list.count()):
            item = self._strings_list.item(i)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def _remove_selected_strings(self):
        """Remove selected strings from the list."""
        selected_items = self._strings_list.selectedItems()
        for item in selected_items:
            row = self._strings_list.row(item)
            self._strings_list.takeItem(row)
    
    def _create_po_file(self):
        """Create PO file from extracted strings."""
        # Get checked strings
        strings = []
        for i in range(self._strings_list.count()):
            item = self._strings_list.item(i)
            if item.checkState() == Qt.Checked and not item.isHidden():
                strings.append(item.text())
        
        if not strings:
            QMessageBox.warning(self, self.tr("No Strings"), 
                              self.tr("No strings selected for PO file creation."))
            return
        
        # Ask for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save PO File"),
            "extracted_strings.po",
            self.tr("PO Files (*.po)")
        )
        
        if file_path:
            try:
                self._save_po_file(file_path, strings)
                QMessageBox.information(
                    self, 
                    self.tr("Success"), 
                    self.tr("PO file created successfully:\n{}").format(file_path)
                )
                
                # Emit signal for parent to potentially open the file
                self.strings_extracted.emit(strings)
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Failed to create PO file:\n{}").format(str(e))
                )
    
    def _save_po_file(self, file_path: str, strings: List[str]):
        """Save strings as a PO file."""
        po_content = [
            '# SOME DESCRIPTIVE TITLE.',
            '# Copyright (C) YEAR THE PACKAGE\'S COPYRIGHT HOLDER',
            '# This file is distributed under the same license as the PACKAGE package.',
            '# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.',
            '#',
            'msgid ""',
            'msgstr ""',
            '"Project-Id-Version: PACKAGE VERSION\\n"',
            '"Report-Msgid-Bugs-To: \\n"',
            '"POT-Creation-Date: 2024-02-08 12:00+0000\\n"',
            '"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"',
            '"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"',
            '"Language-Team: LANGUAGE <LL@li.org>\\n"',
            '"Language: \\n"',
            '"MIME-Version: 1.0\\n"',
            '"Content-Type: text/plain; charset=UTF-8\\n"',
            '"Content-Transfer-Encoding: 8bit\\n"',
            '',
            f'# Extracted from OCR of image: {Path(self._current_image_path).name}',
            ''
        ]
        
        for i, string in enumerate(strings):
            po_content.extend([
                f'#: ocr_extracted:{i+1}',
                f'msgid "{self._escape_po_string(string)}"',
                'msgstr ""',
                ''
            ])
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(po_content))
    
    def _escape_po_string(self, s: str) -> str:
        """Escape string for PO file format."""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    
    def dragEnterEvent(self, event):
        """Handle drag enter event for dropping image files."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop event for image files."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if any(file_path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']):
                self._load_image(file_path)
                break
        event.acceptProposedAction()