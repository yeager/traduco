#!/usr/bin/env python3
"""
Automatisera översättning av LinguaEdit TS-fil till svenska.
"""

import re
import xml.etree.ElementTree as ET

def translate_to_swedish(english_text):
    """Översätt vanliga engelska strängar till formell svenska."""
    
    # Vanliga UI-översättningar
    translations = {
        # File Menu
        "File": "Fil",
        "New": "Ny", 
        "Open": "Öppna",
        "Save": "Spara",
        "Save As": "Spara som",
        "Close": "Stäng",
        "Exit": "Avsluta",
        "Recent": "Senaste",
        "Import": "Importera",
        "Export": "Exportera",
        
        # Edit Menu
        "Edit": "Redigera",
        "Cut": "Klipp ut", 
        "Copy": "Kopiera",
        "Paste": "Klistra in",
        "Undo": "Ångra",
        "Redo": "Gör om",
        "Find": "Sök",
        "Replace": "Ersätt",
        "Select All": "Markera allt",
        
        # View Menu
        "View": "Visa",
        "Zoom In": "Zooma in",
        "Zoom Out": "Zooma ut",
        "Fullscreen": "Helskärm",
        
        # Tools/Settings
        "Tools": "Verktyg",
        "Settings": "Inställningar", 
        "Preferences": "Inställningar",
        "Options": "Alternativ",
        "Configuration": "Konfiguration",
        
        # Help
        "Help": "Hjälp",
        "About": "Om",
        "Documentation": "Dokumentation",
        
        # Dialog buttons
        "OK": "OK",
        "Cancel": "Avbryt", 
        "Apply": "Tillämpa",
        "Yes": "Ja",
        "No": "Nej",
        "Browse": "Bläddra",
        "Reset": "Återställ",
        
        # Common actions
        "Add": "Lägg till",
        "Remove": "Ta bort", 
        "Delete": "Ta bort",
        "Create": "Skapa",
        "Load": "Ladda",
        "Update": "Uppdatera",
        "Refresh": "Uppdatera",
        "Clear": "Rensa",
        
        # Status/State
        "Loading": "Laddar",
        "Saving": "Sparar", 
        "Complete": "Klar",
        "Ready": "Redo",
        "Error": "Fel",
        "Warning": "Varning",
        "Success": "Framgång",
        
        # Navigation
        "Next": "Nästa",
        "Previous": "Föregående",
        "First": "Första", 
        "Last": "Sista",
        "Back": "Tillbaka",
        
        # Data/Content
        "Name": "Namn",
        "Type": "Typ",
        "Size": "Storlek",
        "Date": "Datum",
        "Status": "Status",
        "Description": "Beskrivning",
        "Details": "Detaljer",
        "Properties": "Egenskaper",
        
        # Translation specific
        "Translation": "Översättning",
        "Source": "Källtext", 
        "Target": "Måltext",
        "Language": "Språk",
        "Fuzzy": "Osäker",
        "Untranslated": "Oöversatt",
        "Translated": "Översatt",
        "Progress": "Förlopp",
        "Statistics": "Statistik",
        
        # Quality
        "Quality": "Kvalitet",
        "Review": "Granskning",
        "Approved": "Godkänd",
        "Rejected": "Avvisad",
        
        # Project terms
        "Project": "Projekt",
        "File Format": "Filformat",
        "Encoding": "Kodning",
        
        # Common verbs
        "Search": "Sök",
        "Filter": "Filtrera", 
        "Sort": "Sortera",
        "Group": "Gruppera",
        "Select": "Välj",
        "Check": "Kontrollera",
        "Validate": "Validera",
        "Test": "Testa",
        
        # AI Review terms
        "AI Review": "AI-granskning",
        "Analysis": "Analys", 
        "Confidence": "Tillförlitlighet",
        "Score": "Poäng",
        "Rating": "Betyg",
        "Suggestion": "Förslag",
        
        # File operations
        "Upload": "Ladda upp",
        "Download": "Ladda ner",
        "Backup": "Säkerhetskopia",
        "Restore": "Återställ",
        
        # Time/Progress
        "Time": "Tid",
        "Duration": "Varaktighet",
        "Remaining": "Återstående",
        "Estimated": "Uppskattat",
        
        # Achievements/Gamification
        "Achievement": "Prestation",
        "Progress": "Framsteg",
        "Level": "Nivå",
        "Points": "Poäng",
        "Unlock": "Lås upp",
        "Unlocked": "Upplåst",
        
        # Common phrases
        "Please wait": "Vänta",
        "Are you sure?": "Är du säker?",
        "This action cannot be undone": "Denna åtgärd kan inte ångras",
        "Save changes?": "Spara ändringar?",
        "No results found": "Inga resultat hittades",
        "Invalid input": "Ogiltig inmatning",
        "Operation completed": "Åtgärden slutförd",
        "Processing": "Bearbetar",
        
        # Bookmarks/Navigation
        "Bookmark": "Bokmärke",
        "Bookmarks": "Bokmärken", 
        "Navigate": "Navigera",
        "Go to": "Gå till",
        "Jump to": "Hoppa till",
        
        # Search/Replace
        "Find and Replace": "Sök och ersätt",
        "Match case": "Matcha versaler/gemener",
        "Whole word": "Helt ord", 
        "Regular expression": "Reguljärt uttryck",
        "Replace all": "Ersätt alla",
        
        # Themes
        "Theme": "Tema",
        "Light": "Ljust",
        "Dark": "Mörkt", 
        "Default": "Standard",
        
        # Tools
        "Linter": "Kontrollverktyg",
        "Spellcheck": "Stavningskontroll",
        "Grammar": "Grammatik",
        "Glossary": "Ordlista",
        
        # Memory/Translation Memory
        "Translation Memory": "Översättningsminne",
        "Memory": "Minne",
        "Suggestions": "Förslag",
        "Match": "Träff",
        "Fuzzy match": "Osäker träff",
        "Exact match": "Exakt träff",
        
        # Plurals
        "Plural": "Plural",
        "Singular": "Singular",
        "Forms": "Former",
        
        # Comments
        "Comment": "Kommentar",
        "Comments": "Kommentarer",
        "Note": "Anteckning",
        "Notes": "Anteckningar",
    }
    
    # Använd ordbok för direkta träffar
    if english_text in translations:
        return translations[english_text]
    
    # Några enkla mönster-baserade översättningar
    text = english_text
    
    # Hantera format strings
    if "{}" in text or "%s" in text or "%d" in text:
        # Behåll format strings som de är för dessa vanliga fall
        pass
    
    # Kontrollera om texten redan är på svenska (innehåller åäö)
    if any(char in text for char in 'åäöÅÄÖ'):
        return english_text  # Redan svenska
    
    # För okända strängar, returnera ursprungstexten 
    # så att vi kan översätta manuellt senare
    return None  # Markera som behöver manuell översättning

def process_ts_file(input_file, output_file):
    """Bearbeta TS-fil och översätt strängar."""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Räkna totalt antal unfinished
    total_unfinished = content.count('type="unfinished"')
    translated_count = 0
    
    print(f"Hittade {total_unfinished} oöversatta strängar.")
    
    # Reguljärt uttryck för att hitta meddelanden
    message_pattern = re.compile(
        r'(<message>.*?<source>(.*?)</source>.*?<translation[^>]*>)(.*?)(</translation>.*?</message>)', 
        re.DOTALL
    )
    
    def translate_message(match):
        nonlocal translated_count
        
        full_start = match.group(1)  # <message>...<translation...>
        source_text = match.group(2)  # Innehåll i <source>
        current_translation = match.group(3)  # Nuvarande översättning
        full_end = match.group(4)  # </translation></message>
        
        # Om det redan finns en översättning som inte är tom, behåll den
        if current_translation.strip() and 'type="unfinished"' not in full_start:
            return match.group(0)  # Returnera oförändrat
        
        # Försök översätta
        swedish_text = translate_to_swedish(source_text)
        
        if swedish_text is not None:
            # Ta bort unfinished-markering och sätt översättning
            new_start = full_start.replace('type="unfinished"', '')
            new_translation = swedish_text
            translated_count += 1
            print(f"Översatte: '{source_text}' -> '{swedish_text}'")
            return new_start + new_translation + full_end
        else:
            # Behåll som unfinished för manuell översättning
            # Men kopiera källtexten som placeholder om det är svenska redan
            if any(char in source_text for char in 'åäöÅÄÖ'):
                # Källtexten ser ut att vara svenska redan
                new_start = full_start.replace('type="unfinished"', '')
                new_translation = source_text
                translated_count += 1
                print(f"Kopierade svensk text: '{source_text}'")
                return new_start + new_translation + full_end
            
            return match.group(0)  # Lämna oförändrat
    
    # Tillämpa översättningar
    new_content = message_pattern.sub(translate_message, content)
    
    # Skriv resultat
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    remaining_unfinished = new_content.count('type="unfinished"')
    
    print(f"\nResultat:")
    print(f"- Automatiskt översatta: {translated_count}")
    print(f"- Återstående för manuell översättning: {remaining_unfinished}")
    print(f"- Sparad som: {output_file}")
    
    return translated_count, remaining_unfinished

if __name__ == "__main__":
    input_file = "translations/linguaedit_sv.ts"
    output_file = "translations/linguaedit_sv_auto.ts"
    
    process_ts_file(input_file, output_file)