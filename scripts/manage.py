import os
import argparse
import json
from src.metadata import extract_preacher_metadata
from src.reorganizer import reorganize_preacher
from src.scanner import SermonScanner
from src.models import PreacherMetadata

from src.llm import LLMService

def main():
    parser = argparse.ArgumentParser(description="Sermon Voices Management Script")
    parser.add_argument("command", choices=["extract", "reorganize", "scan"], help="Command to run")
    parser.add_argument("--preacher", help="Specific preacher directory (for extract)")
    parser.add_argument("--metadata", help="Specific metadata file (for reorganize)")
    parser.add_argument("--no-dry-run", action="store_true", help="Perform actual moves (for reorganize)")
    parser.add_argument("--metadata-dir", default="metadata", help="Metadata directory")
    parser.add_argument("--llm", action="store_true", help="Use LLM for English translation")
    
    args = parser.parse_args()

    llm = LLMService() if args.llm else None

    if args.command == "extract":
        base_blobs_dir = "blobs"
        output_dir = args.metadata_dir
        os.makedirs(output_dir, exist_ok=True)
        
        preacher_dirs = []
        if args.preacher:
            if os.path.isdir(args.preacher):
                preacher_dirs = [args.preacher]
            else:
                p_path = os.path.join(base_blobs_dir, args.preacher)
                if os.path.isdir(p_path):
                    preacher_dirs = [p_path]
        else:
            if os.path.exists(base_blobs_dir):
                preacher_dirs = [os.path.join(base_blobs_dir, d) for d in os.listdir(base_blobs_dir) if os.path.isdir(os.path.join(base_blobs_dir, d))]
            
        for p_dir in preacher_dirs:
            p_basename = os.path.basename(p_dir)
            print(f"Processing preacher: {p_basename}")
            
            # 1. Determine the expected slug/output name
            # If a metadata file already exists for this preacher, use its name 
            # and potentially skip extraction.
            existing_metadata_file = None
            for f in os.listdir(output_dir):
                if f.endswith("_metadata.json"):
                    with open(os.path.join(output_dir, f), 'r', encoding='utf-8') as jf:
                        try:
                            tmp_data = json.load(jf)
                            if tmp_data.get("preacher", {}).get("name") == p_basename:
                                existing_metadata_file = f
                                break
                        except:
                            continue
            
            if existing_metadata_file:
                print(f"Found existing metadata: {existing_metadata_file}. Skipping extraction to preserve manual edits.")
                continue

            print(f"Extracting metadata for: {p_basename}")
            metadata = extract_preacher_metadata(p_dir, llm=llm)
            
            # Save to JSON using Slugified English name
            p_name_en = metadata.preacher.name_en or metadata.preacher.name
            # If it's still Chinese, try once more to slugify to English if LLM available
            if llm and any('\u4e00' <= c <= '\u9fff' for c in p_name_en):
                slug = llm.slugify_to_english(p_name_en)
            else:
                from src.reorganizer import slugify
                slug = slugify(p_name_en)
            
            output_name = f"{slug}_metadata.json"
            output_path = os.path.join(output_dir, output_name)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata.model_dump(), f, ensure_ascii=False, indent=2)
            print(f"Saved to {output_path}")

    elif args.command == "reorganize":
        if args.metadata:
            # Reorganize single preacher
            with open(args.metadata, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metadata = PreacherMetadata(**data)
                reorganize_preacher(metadata, dry_run=not args.no_dry_run)
                # Update metadata if needed (new paths)
                with open(args.metadata, 'w', encoding='utf-8') as fw:
                    json.dump(metadata.model_dump(), fw, ensure_ascii=False, indent=2)
        else:
            # Reorganize all in metadata_dir
            for filename in os.listdir(args.metadata_dir):
                if filename.endswith(".json"):
                    path = os.path.join(args.metadata_dir, filename)
                    print(f"Reorganizing based on: {path}")
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        metadata = PreacherMetadata(**data)
                        reorganize_preacher(metadata, dry_run=not args.no_dry_run)
                        with open(path, 'w', encoding='utf-8') as fw:
                            json.dump(metadata.model_dump(), fw, ensure_ascii=False, indent=2)

    elif args.command == "scan":
        scanner = SermonScanner(args.metadata_dir)
        sermons = scanner.scan_all()
        print(f"Found total sermons: {len(sermons)}")
        for i, s in enumerate(sermons[:5]):
            print(f" - [{s.id}] {s.title} ({s.date})")
        if len(sermons) > 5:
            print(f"   ... and {len(sermons)-5} more.")

if __name__ == "__main__":
    main()
