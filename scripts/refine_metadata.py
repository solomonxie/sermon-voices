import os
import json
import argparse
from src.llm import LLMService
from src.models import PreacherMetadata, Sermon, SeriesInfo, ScriptureReference

def refine_json(metadata_path: str, llm: LLMService, limit: int = 0):
    print(f"Refining: {metadata_path} (limit: {limit if limit > 0 else 'All'})")
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    preacher_name = data.get('preacher', {}).get('name', 'Unknown')
    metadata_obj = PreacherMetadata(**data)
    
    refined_sermons = {}
    new_id_counter = 1
    processed_count = 0
    
    # We'll refine sermon by sermon
    for sermon_id, sermon in metadata_obj.sermons.items():
        if limit > 0 and processed_count >= limit:
            break
            
        print(f"  [{new_id_counter}] Refining sermon: {sermon.title}")
        
        # Cast Pydantic to dict for LLM
        sermon_dict = sermon.model_dump()
        refinement = llm.refine_sermon_metadata(sermon_dict, preacher_name)
        
        if refinement:
            # Apply refinements
            sermon.title_en = refinement.get('title_en', sermon.title_en)
            sermon.series.name_en = refinement.get('series_en', sermon.series.name_en)
            
            # Preacher name update (global for this file)
            metadata_obj.preacher.name_en = llm.clean_slug(refinement.get('preacher_en', metadata_obj.preacher.name_en))
            
            # Scripture references
            if refinement.get('chapter'):
                if not sermon.scripture_references:
                    sermon.scripture_references.append(ScriptureReference(
                        book=refinement.get('series_en', ''),
                        book_zh=sermon.series.name,
                        chapter=refinement.get('chapter', 0),
                        verse_start=refinement.get('verse_start', 0),
                        verse_end=refinement.get('verse_end', 0)
                    ))
                else:
                    ref = sermon.scripture_references[0]
                    ref.book = refinement.get('series_en', ref.book)
                    ref.chapter = refinement.get('chapter', ref.chapter)
                    ref.verse_start = refinement.get('verse_start', ref.verse_start)
                    ref.verse_end = refinement.get('verse_end', ref.verse_end)
        
        # Incremental ID
        new_id = str(new_id_counter)
        sermon.id = new_id
        refined_sermons[new_id] = sermon
        new_id_counter += 1
        processed_count += 1
        
        if new_id_counter % 10 == 0:
            print(f"    ... processed {new_id_counter} sermons")

    metadata_obj.sermons = refined_sermons
    
    # Save back
    output_path = metadata_path # Overwrite as requested or save to .refined.json?
    # User said "refine the json first", usually implies overwriting or creating a new one.
    # To be safe and follow "don't remove existing metadata", I'll save to a temp name first or just overwrite.
    # Actually, user said "write a script to check the metadata.json themselves... refine the json first"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata_obj.model_dump(), f, ensure_ascii=False, indent=2)
    
    print(f"✓ Refinement complete: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Refine metadata JSONs using LLM")
    parser.add_argument("--dir", default="metadata", help="Directory containing JSON files")
    parser.add_argument("--file", help="Specific JSON file to refine")
    parser.add_argument("--model", default="gemma3:12b-it-qat", help="Ollama model to use")
    
    parser.add_argument("--limit", type=int, default=0, help="Limit number of sermons to refine (for testing)")
    
    args = parser.parse_args()
    llm = LLMService(model=args.model)
    
    if args.file:
        refine_json(args.file, llm, limit=args.limit)
    else:
        for filename in os.listdir(args.dir):
            if filename.endswith(".json"):
                refine_json(os.path.join(args.dir, filename), llm, limit=args.limit)

if __name__ == "__main__":
    main()
