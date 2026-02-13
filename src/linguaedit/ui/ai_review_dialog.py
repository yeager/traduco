"""AI Review Dialog — Analyserar översättningar med AI eller heuristik.

Skickar källtext + översättning till OpenAI/Anthropic API eller använder
offline heuristik-regler för att bedöma kvalitet och ge förslag.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QGroupBox, QCheckBox, QComboBox,
    QDialogButtonBox, QApplication, QMessageBox, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

from linguaedit.services.settings import Settings


class AIReviewWorker(QThread):
    """Background worker för AI-review för att undvika UI-frysning."""
    
    finished = Signal(dict)  # {"score": int, "explanation": str, "suggestion": str}
    error = Signal(str)
    
    def __init__(self, source: str, translation: str, api_key: str = "", provider: str = "offline"):
        super().__init__()
        self.source = source
        self.translation = translation
        self.api_key = api_key
        self.provider = provider
    
    def run(self):
        try:
            if self.provider == "offline" or not self.api_key:
                result = self._heuristic_review()
            elif self.provider == "openai":
                result = self._openai_review()
            elif self.provider == "anthropic":
                result = self._anthropic_review()
            else:
                result = self._heuristic_review()
            
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
    
    def _heuristic_review(self) -> dict:
        """Offline heuristik-baserad granskning."""
        score = 3  # Start från medel
        issues = []
        suggestion = self.translation
        
        # Kontrollera längd
        if len(self.translation) == 0:
            score = 1
            issues.append("Översättning saknas")
            suggestion = self.source  # Föreslå källtext
        elif len(self.translation) > len(self.source) * 2:
            score -= 1
            issues.append("Översättning mycket längre än källa")
        elif len(self.translation) < len(self.source) * 0.3:
            score -= 1
            issues.append("Översättning mycket kortare än källa")
        
        # Kontrollera formatmarkörer
        source_placeholders = re.findall(r'%[sdif]|\{[^}]+\}|<[^>]+>', self.source)
        trans_placeholders = re.findall(r'%[sdif]|\{[^}]+\}|<[^>]+>', self.translation)
        
        if len(source_placeholders) != len(trans_placeholders):
            score -= 1
            issues.append("Olika antal formatmarkörer/taggar")
        
        # Kontrollera om det är samma som källa (ofta dåligt)
        if self.source.strip().lower() == self.translation.strip().lower():
            score -= 1
            issues.append("Identisk med källtext")
        
        # Kontrollera teckensnitt
        if self.translation.isupper() and not self.source.isupper():
            score -= 1
            issues.append("Alla versaler när källa inte är det")
        
        # Förbättra poäng för bra saker
        if len(self.translation) > 5 and self.translation != self.source:
            score += 1
        
        score = max(1, min(5, score))
        
        if not issues:
            explanation = "Ingen uppenbar problem hittade med denna översättning."
        else:
            explanation = "Problem identifierade: " + "; ".join(issues)
        
        return {
            "score": score,
            "explanation": explanation,
            "suggestion": suggestion if suggestion != self.translation else ""
        }
    
    def _openai_review(self) -> dict:
        """OpenAI API-baserad granskning."""
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.api_key)
            
            prompt = f"""Granska denna översättning:

Källtext: "{self.source}"
Översättning: "{self.translation}"

Betygsätt översättningen 1-5 stjärnor och ge konstruktiv feedback:
1 = Mycket dålig
2 = Dålig
3 = Acceptabel
4 = Bra
5 = Utmärkt

Svara med JSON:
{{"score": 1-5, "explanation": "...", "suggestion": "..."}}"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            # Extrahera JSON från svaret
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("Ogiltigt svar från OpenAI")
                
        except Exception as e:
            # Fallback till heuristik
            return self._heuristic_review()
    
    def _anthropic_review(self) -> dict:
        """Anthropic API-baserad granskning."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            prompt = f"""Granska denna översättning:

Källtext: "{self.source}"
Översättning: "{self.translation}"

Betygsätt översättningen 1-5 stjärnor och ge konstruktiv feedback:
1 = Mycket dålig
2 = Dålig  
3 = Acceptabel
4 = Bra
5 = Utmärkt

Svara med JSON:
{{"score": 1-5, "explanation": "...", "suggestion": "..."}}"""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("Ogiltigt svar från Anthropic")
                
        except Exception as e:
            # Fallback till heuristik
            return self._heuristic_review()


class AIReviewDialog(QDialog):
    """Dialog för AI-baserad översättningsgranskning."""
    
    def __init__(self, source: str, translation: str, parent=None):
        super().__init__(parent)
        self.source = source
        self.translation = translation
        self.suggestion = ""
        self.setWindowTitle(self.tr("AI Translation Review"))
        self.setModal(True)
        self.resize(600, 500)
        
        self._setup_ui()
        self._start_review()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Käll- och översättningstext
        text_group = QGroupBox(self.tr("Text to Review"))
        text_layout = QVBoxLayout(text_group)
        
        source_label = QLabel(self.tr("Source text:"))
        source_edit = QTextEdit()
        source_edit.setPlainText(self.source)
        source_edit.setReadOnly(True)
        source_edit.setMaximumHeight(80)
        text_layout.addWidget(source_label)
        text_layout.addWidget(source_edit)
        
        trans_label = QLabel(self.tr("Translation:"))
        self.trans_edit = QTextEdit()
        self.trans_edit.setPlainText(self.translation)
        self.trans_edit.setMaximumHeight(80)
        text_layout.addWidget(trans_label)
        text_layout.addWidget(self.trans_edit)
        
        layout.addWidget(text_group)
        
        # Analys-grupp
        analysis_group = QGroupBox(self.tr("Analysis"))
        analysis_layout = QVBoxLayout(analysis_group)
        
        # Progress bar under analys
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_label = QLabel(self.tr("Analyzing translation..."))
        analysis_layout.addWidget(self.progress_label)
        analysis_layout.addWidget(self.progress_bar)
        
        # Betyg (stjärnor)
        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel(self.tr("Score:")))
        self.score_label = QLabel("")
        font = QFont()
        font.setPointSize(16)
        self.score_label.setFont(font)
        score_layout.addWidget(self.score_label)
        score_layout.addStretch()
        analysis_layout.addLayout(score_layout)
        
        # Förklaring
        self.explanation_edit = QTextEdit()
        self.explanation_edit.setReadOnly(True)
        self.explanation_edit.setMaximumHeight(100)
        analysis_layout.addWidget(QLabel(self.tr("Explanation:")))
        analysis_layout.addWidget(self.explanation_edit)
        
        # Förslag
        self.suggestion_edit = QTextEdit()
        self.suggestion_edit.setMaximumHeight(80)
        analysis_layout.addWidget(QLabel(self.tr("Improvement suggestions:")))
        analysis_layout.addWidget(self.suggestion_edit)
        
        layout.addWidget(analysis_group)
        
        # Knappar
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton(self.tr("Apply Suggestion"))
        self.apply_btn.clicked.connect(self._apply_suggestion)
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
    
    def _start_review(self):
        """Startar AI-granskningen i bakgrunden."""
        settings = Settings.get()
        api_key = settings.get("ai_api_key", "")
        provider = settings.get("ai_provider", "offline")
        
        self.worker = AIReviewWorker(self.source, self.translation, api_key, provider)
        self.worker.finished.connect(self._on_review_finished)
        self.worker.error.connect(self._on_review_error)
        self.worker.start()
    
    def _on_review_finished(self, result: dict):
        """Hanterar färdig AI-granskning."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        score = result.get("score", 3)
        stars = "⭐" * score
        self.score_label.setText(f"{stars} ({score}/5)")
        
        self.explanation_edit.setPlainText(result.get("explanation", ""))
        
        suggestion = result.get("suggestion", "")
        if suggestion and suggestion != self.translation:
            self.suggestion_edit.setPlainText(suggestion)
            self.suggestion = suggestion
            self.apply_btn.setEnabled(True)
        else:
            self.suggestion_edit.setPlainText(self.tr("No specific suggestions."))
    
    def _on_review_error(self, error_msg: str):
        """Hanterar fel under granskning."""
        self.progress_bar.setVisible(False)
        self.progress_label.setText(self.tr("Analysis error: ") + error_msg)
        
        QMessageBox.warning(self, self.tr("Error"), 
                          self.tr("Could not analyze translation: ") + error_msg)
    
    def _apply_suggestion(self):
        """Applicerar förslaget till översättningstexten."""
        if self.suggestion:
            self.trans_edit.setPlainText(self.suggestion)
            self.apply_btn.setEnabled(False)
    
    def get_translation(self) -> str:
        """Returnerar den (eventuellt redigerade) översättningen."""
        return self.trans_edit.toPlainText()