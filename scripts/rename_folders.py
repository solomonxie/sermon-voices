import os
import re
import json
import shutil
from slugify import slugify

OUTPUT_ROOT = './output'

def rename_sermon_folders():
    """ 
    Traverses the output directory and renames folders to remove the scripture part.
    Old format: sequence_title_scripture_date
    New format: sequence_title_date
    """
    print(f"🚀 Starting folder migration in {OUTPUT_ROOT}...")
    
    if not os.path.exists(OUTPUT_ROOT):
        print(f"⚠️ {OUTPUT_ROOT} does not exist. Nothing to do.")
        return

    # Iterate through preacher/series/sermon_folder
    for preacher in os.listdir(OUTPUT_ROOT):
        preacher_path = os.path.join(OUTPUT_ROOT, preacher)
        if not os.path.isdir(preacher_path) or preacher.startswith('.'):
            continue
            
        for series in os.listdir(preacher_path):
            series_path = os.path.join(preacher_path, series)
            if not os.path.isdir(series_path) or series.startswith('.'):
                continue
                
            for sermon_folder in os.listdir(series_path):
                sermon_path = os.path.join(series_path, sermon_folder)
                if not os.path.isdir(sermon_path) or sermon_folder.startswith('.'):
                    continue
                
                # Simple strategy: split by "_"
                parts = sermon_folder.split('_')
                if len(parts) != 4:
                    # Skip folders that don't match the expected old format
                    # (sequence_title_scripture_date)
                    continue
                
                # New format: sequence_title_date (remove index 2: scripture)
                new_sermon_slug = f"{parts[0]}_{parts[1]}_{parts[3]}"
                
                if sermon_folder != new_sermon_slug:
                    new_sermon_path = os.path.join(series_path, new_sermon_slug)
                    
                    if os.path.exists(new_sermon_path):
                        print(f"⏩ Skipping {sermon_folder} -> {new_sermon_slug} (Target already exists)")
                        continue
                        
                    print(f"📂 Renaming: {sermon_folder} -> {new_sermon_slug}")
                    try:
                        os.rename(sermon_path, new_sermon_path)
                    except Exception as e:
                        print(f"❌ Failed to rename {sermon_path}: {e}")

if __name__ == "__main__":
    rename_sermon_folders()
