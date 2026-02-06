import os

def convert_to_markdown(text: str, output_path: str) -> str:
    print(f"📝 Generating Markdown: {output_path}")
    md_content = f"# Sermon Transcript\n\n---\n\n{text}"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    return output_path


def convert_to_latex(md_path: str, output_path: str) -> str:
    print(f"📄 Generating LaTeX: {output_path}")
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    try:
        import pypandoc
        # Check if pandoc is available via pypandoc
        tex_content = pypandoc.convert_text(md_content, 'latex', format='markdown')
    except Exception:
        # Fallback to simple template
        tex_content = f"\\documentclass{{article}}\n\\usepackage[utf8]{{inputenc}}\n\\begin{{document}}\n{md_content}\n\\end{{document}}"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)
    return output_path


def convert_to_pdf(text: str, output_path: str) -> str:
    print(f"📊 Generating PDF: {output_path}")
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        # Handle multi-line text
        for line in text.split('\n'):
            pdf.multi_cell(0, 10, line.encode('latin-1', 'replace').decode('latin-1'))
        pdf.output(output_path)
    except Exception as e:
        print(f"⚠️ PDF generation failed: {e}")
    return output_path
