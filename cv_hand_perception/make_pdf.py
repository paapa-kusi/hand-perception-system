import os
from fpdf import FPDF

files_to_include = [
    "features.py",
    "filters.py",
    "calibration.py",
    "hand_tracker.py"
]

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.set_font("Courier", size=8)

for filename in files_to_include:
    pdf.set_font("Courier", style="B", size=10)
    pdf.cell(w=0, h=10, txt=f"File: {filename}", ln=True)
    pdf.set_font("Courier", size=8)
    
    with open(filename, "r") as f:
        content = f.read()
        
    for line in content.split("\n"):
        line = line.replace('\t', '    ')
        # Split very long lines manually to avoid FPDFException
        while len(line) > 100:
            pdf.cell(w=0, h=4, txt=line[:100], ln=True)
            line = "    " + line[100:]
        pdf.cell(w=0, h=4, txt=line, ln=True)
            
    pdf.add_page()

pdf.output("cv_hand_perception_code.pdf")
print("Successfully generated cv_hand_perception_code.pdf")
