import os
import shutil
import re
from typing import Optional
from .models import Sermon, PreacherMetadata

def slugify(text: str) -> str:
    """Simplified slugify for filenames."""
    # Remove non-alphanumeric except for some separators
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def format_new_path(sermon: Sermon, preacher_en: str) -> str:
    """
    Folder: sermons/<PreacherEN>/<SeriesEN>/nnn_<series_slug>_<verse>/
    File: nnn_<series_slug>_<verse>_<language>_original.mp3
    """
    # Clean preacher name (no spaces, no special characters)
    import re
    preacher_clean = re.sub(r'[^a-zA-Z0-9_-]', '', preacher_en.replace(' ', ''))
    
    series_name_en = sermon.series.name_en or sermon.series.name or "Misc"
    series_en_clean = re.sub(r'[^a-zA-Z0-9_-]', '', series_name_en.replace(' ', ''))
    
    series_en_slug = slugify(series_name_en)
    num = str(sermon.series.number).zfill(3)
    lang = sermon.language

    # Verse info: ch1v2_v4
    verse_info = ""
    if sermon.scripture_references:
        ref = sermon.scripture_references[0]
        if ref.chapter:
            verse_info = f"ch{ref.chapter}v{ref.verse_start}"
            if ref.verse_end and ref.verse_end != ref.verse_start:
                verse_info += f"_v{ref.verse_end}"
    
    # Base name: 001_luke_ch1v2_v4 (no special characters)
    parts = [num, series_en_slug]
    if verse_info:
        parts.append(verse_info)
        
    base_name = "_".join(parts)
    base_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
    
    # Folder structure: sermons/StevenTong/Luke/001_luke_ch1v2_v4/
    folder = os.path.join("sermons", preacher_clean, series_en_clean, base_name)
    filename = f"{base_name}_{lang}_original.mp3"
    
    return os.path.join(folder, filename)

def reorganize_preacher(metadata: PreacherMetadata, dry_run: bool = True):
    preacher_en = metadata.preacher.name_en or metadata.preacher.name
    
    for sermon_id, sermon in metadata.sermons.items():
        old_path = sermon.original_path
        new_path = format_new_path(sermon, preacher_en)
        
        # Update sermon model with the new path
        sermon.new_path = new_path
        
        if not os.path.exists(old_path):
            print(f"Warning: Original file not found: {old_path}")
            continue
            
        if dry_run:
            print(f"[DRY RUN] Would move: {old_path} -> {new_path}")
        else:
            print(f"Moving: {old_path} -> {new_path}")
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.copy2(old_path, new_path)
            # Verify copy
            if os.path.exists(new_path):
                print(f"Verified: {new_path}")
            else:
                print(f"Error copying: {old_path}")
