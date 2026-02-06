import os
import json
from src.constants import OUTPUT_ROOT


def main() -> None:
    print(f"\n--- Phase 3: Document Generation (EN) ---")
    from glob import glob
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in sorted(metadata_files):
        try:
            process_en_documents(metadata_path)
        except Exception as e:
            print(f"❌ Error processing documents for {metadata_path}: {str(e)}")


def process_en_documents(metadata_path: str) -> None:
    """ Generates various document formats from translated English text. """
    sermon_dir = os.path.dirname(metadata_path)
    translation_en_path = os.path.join(sermon_dir, 'translation_en.txt')
    
    if not os.path.exists(translation_en_path):
        # Skipping if EN translation doesn't exist yet
        return

    print(f"\n⚙️ Generating Documents: {sermon_dir}")
    with open(translation_en_path, 'r', encoding='utf-8') as f:
        en_text = f.read()

    # 1. Generate Markdown
    markdown_path = os.path.join(sermon_dir, 'translation_en.md')
    convert_to_markdown(en_text.strip(), markdown_path)

    # 2. Generate LaTeX
    latex_path = os.path.join(sermon_dir, 'translation_en.tex')
    convert_to_latex(markdown_path, latex_path)

    # 3. Generate PDF
    pdf_path = os.path.join(sermon_dir, 'translation_en.pdf')
    convert_to_pdf(en_text.strip(), pdf_path)
    
    print(f"✅ Document generation complete for: {sermon_dir}")


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
        tex_content = pypandoc.convert_text(md_content, 'latex', format='markdown')
    except Exception:
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
        for line in text.split('\n'):
            pdf.multi_cell(0, 10, line.encode('latin-1', 'replace').decode('latin-1'))
        pdf.output(output_path)
    except Exception as e:
        print(f"⚠️ PDF generation failed: {e}")
    return output_path


if __name__ == '__main__':
    main()
