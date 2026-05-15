"""
make_pdf.py

Utility script for generating a single PDF document containing all project source 
code and technical documentation. Useful for sharing the complete Phase 1 pipeline 
in a portable format.

Interactions:
- Reads from: All .py pipeline files, ../TECHNICAL_DOCUMENTATION.md
- Writes to: cv_hand_perception_code.pdf
"""
import os
from fpdf import FPDF

files_to_include = [
    "../TECHNICAL_DOCUMENTATION.md",
    "main.py",
    "camera.py",
    "hand_tracker.py",
    "features.py",
    "filters.py",
    "calibration.py",
    "telemetry.py",
    "tester.py",
    "visualizer.py",
    "aggregate_tests.py"
]

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.set_font("Courier", size=8)

for filename in files_to_include:
    pdf.set_font("Courier", style="B", size=10)
    pdf.cell(w=0, h=10, txt=f"File: {filename}", ln=True)
    pdf.set_font("Courier", size=8)
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = f"Error: File {filename} not found."
        
    for line in content.split("\n"):
        line = line.replace('\t', '    ')
        # Encode/decode to latin-1 to avoid FPDF character errors (e.g. for the € symbol)
        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
        
        # Split very long lines manually to avoid FPDFException
        while len(safe_line) > 100:
            pdf.cell(w=0, h=4, txt=safe_line[:100], ln=True)
            safe_line = "    " + safe_line[100:]
        pdf.cell(w=0, h=4, txt=safe_line, ln=True)
            
    pdf.add_page()

pdf.output("cv_hand_perception_code.pdf")
print("Successfully generated cv_hand_perception_code.pdf")
