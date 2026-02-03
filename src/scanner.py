import os
import json
from typing import List
from .models import PreacherMetadata, Sermon

class SermonScanner:
    def __init__(self, metadata_dir: str = "metadata"):
        self.metadata_dir = metadata_dir

    def scan_all(self) -> List[Sermon]:
        """Scans the metadata directory and returns all sermons from all preachers."""
        all_sermons = []
        
        if not os.path.exists(self.metadata_dir):
            print(f"Warning: Metadata directory {self.metadata_dir} not found.")
            return []

        for filename in os.listdir(self.metadata_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.metadata_dir, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Validate with Pydantic
                        metadata = PreacherMetadata(**data)
                        all_sermons.extend(metadata.sermons.values())
                except Exception as e:
                    print(f"Error loading metadata from {path}: {e}")
        
        return all_sermons

    def load_preacher(self, json_path: str) -> PreacherMetadata:
        """Loads a specific preacher's metadata."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return PreacherMetadata(**data)
