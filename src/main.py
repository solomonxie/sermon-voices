"""
- Scan each file in the blob
- Extract basic information: full path, audio basic info
- Let local LLM extract metadata:
    - Speaker name (mostly from path)
    - Bible book name or sermon series name (mostly from path)
    - Title (mostly from path or file name)
- Rename file to a better structured folder:
    ./output/audio/<speaker_name_en_slugify>/<book_name_or_series_name_en_slugify>/000_<title_en_slugify>/000_<title_en_slugify>_original.mp3
- Transcript audio to text file under ./output/text/ (using latest and best open source lib or local LLM)
- Refine text file with LLM (./output/text_refine)
- Convert text file to Markdown file using local LLM (save to ./output/markdown)
- Convert Markdown file to Latex file and PDF files (./output/latex and ./output/pdf)
- Translate text file to english (./output/text_en)
- Text-to-speech with local LLM and open source libraries
"""


import os
import json
import shutils
from glob import glob


def main():
    for path in glob('./blobs/*'):
        if not path.endswith('.mp3'):
            print(f'Not supported: {path}')
            continue
        metadata = extract_metadata(path)
        new_path = make_new_path(metadata)
        shutils.mkdirs(os.path.dirname(new_path), exist_ok=True)
        shutils.move(path, new_path)
        transcript_path = transcript_audio(new_path)
        refined_transcript_path = refine_transcript(transcript_path)
        markdown_path = convert_to_markdown(refined_transcript_path)
        latex_path = convert_to_latex(markdown_path)
        _ = convert_to_pdf(latex_path)
        # To English
        translated_text_path = translate_transcript(transcript_path)
        audio_path = text_to_speech(translated_text_path)
        # Update metadata
        update_metadata(new_path, refined_transcript_path, translated_text_path)
        print(f'Done: {path}')


def extract_metadata(path: str) -> dict:
    resp = ask_llm("""
        Based on this path of a biblical sermon audio file, you should extract these basic information:
        - Speaker name (original name): e.g., 唐崇荣，C. S. Lewis, John Piper...
        - Bible book name or sermon series name (original): e.g., Genesis, Hebrews, 创世纪, 解答集.
        - Title (original): e.g., "2014.12.07箴言003（1章8-9节）圣道的益处", or "hebrews chapter 1 verse 1 to 3 and 9", or "answer collections 1 why it doesnt work"
        If any name in the path isn't clear, You should be able to guess, for example:
        "blobs/华贤全套查经系列（压缩版）/1路1-321全（zip文件）/121-159/解压密码：20162017/2016.07.15路加福音121（7章1-5节）迦百农的百夫长.mp3"
        You should extract information as a JSON result like:
        {
            "preacher": ["华贤"],
            "series": ["1路1-321全", "华贤全套查经系列"],
            "sequence": 321,
            "books": [{"book": "Luke", "references": ["ch7_v1_5", "ch8_v1_v3"]}],
            "title": "2016.07.15路加福音121（7章1-5节）迦百农的百夫长",
            "created_at": "2016-07-15"
        }
    """)
    metadata = json.loads(resp)
    return metadata


def make_new_path(metadata: dict) -> str:
    return './output/audio/{}/{}/{}/{}_{}_original.mp3'.format(
        slugify('_and_'.join(metadata['preacher'])),
        slugify('_and_'.join(metadata['series'])),
        slugify(metadata['title']),
        slugify(metadata['sequence']),
        slugify(metadata['title']),
    )


def ask_llm(prompt: str, model: str='llamma3') -> str:
    # TODO: Send prompt to a local LLM
    return '{}'


def slugify(s: str) -> str:
    # TODO: Convert unicode string to slugified english or pinyin without special characters
    return ''


def transcript_audio(path: str) -> str:
    transcript_path = './output/transcripts/' + path.replace('output/audio', '').replace('.mp3', '.txt')
    # TODO: use open source lib or local LLM to transcript into text file
    return transcript_path


def refine_transcript(transcript_path: str) -> str:
    refine_path = transcript_path.replace('.txt', '_refined.txt')
    # TODO: use LLM to refine transcript
    # ...
    return refine_path

def convert_to_markdown(text_path: str) -> str:
    markdown_path = text_path.replace('.txt', '.md')
    # TODO: use LLM
    # ...
    return markdown_path

def convert_to_latex(markdown_path: str) -> str:
    latex_path = markdown_path.replace('.md', '.latex')
    # TODO: use LLM
    # ...
    return latex_path

def convert_to_pdf(latex_path: str) -> str:
    pdf_path = latex_path.replace('.latex', '.pdf')
    # TODO: use LLM or libraries
    # ...
    return pdf_path


def translate_transcript(transcript_path: str) -> str:
    path = transcript_path.replace('.txt', '_en.txt')
    # TODO: use LLM or libraries
    # ...
    return path


def text_to_speech(text_path: str, orig_audio_path: str) -> str:
    audio_path = orig_audio_path.replace('.mp3', '_en.mp3')
    # TODO: use LLM or libraries
    # ...
    return pdf_path


def update_metadata(orig_audio_path: str, transcript_path: str, translated_text_path: str) -> str:
    metadata_path = './output/metadata/' + ''  # TODO: should be similar to new audio path structure
    # TODO: use LLM or libraries
    # ...
    return metadata_path


if __name__ == '__main__':
    main()
