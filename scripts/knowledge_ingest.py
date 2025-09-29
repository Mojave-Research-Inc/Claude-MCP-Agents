#!/usr/bin/env python3
"""
Claude Code Knowledge Ingestion - Indexes project files for semantic search.
Simplified version adapted from Codex integration.
"""

import json
import os
import hashlib
from pathlib import Path
from typing import List, Set, Optional, Dict
import mimetypes
import sys

# Add brain adapter to path
sys.path.append(str(Path(__file__).parent))
from brain_adapter import BrainAdapter

class KnowledgeIngestor:
    """Ingests and indexes project files for knowledge management."""

    def __init__(self, config_path: Path = None):
        self.brain = BrainAdapter()
        self.config = self._load_config(config_path)
        self.cache_file = Path.home() / ".claude" / ".ingest_cache.json"
        self.cache = self._load_cache()
        self.stats = {
            'files_processed': 0,
            'chunks_created': 0,
            'files_skipped': 0,
            'errors': 0
        }

    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration for knowledge ingestion."""
        if config_path is None:
            config_path = Path.home() / ".claude" / "brain_config.json"

        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                return config.get('knowledge_management', {})

        # Default configuration
        return {
            'enabled': True,
            'chunk_size': 1000,
            'overlap': 100,
            'file_extensions': [
                '.py', '.js', '.ts', '.jsx', '.tsx',
                '.md', '.txt', '.json', '.yaml', '.yml',
                '.toml', '.ini', '.cfg', '.conf',
                '.sh', '.bash', '.zsh',
                '.sql', '.graphql'
            ],
            'exclude_patterns': [
                'node_modules/', '.git/', '__pycache__/',
                '*.pyc', '.env', '*.log', 'dist/', 'build/', '.cache/'
            ],
            'ingest_paths': [os.getcwd()]
        }

    def _load_cache(self) -> Dict:
        """Load file modification cache."""
        if self.cache_file.exists():
            with open(self.cache_file) as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save file modification cache."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed."""
        # Check extension
        if self.config.get('file_extensions'):
            if not any(str(file_path).endswith(ext) for ext in self.config['file_extensions']):
                return False

        # Check exclude patterns
        for pattern in self.config.get('exclude_patterns', []):
            if pattern in str(file_path):
                return False

        # Check file size (skip very large files)
        try:
            if file_path.stat().st_size > 1024 * 1024:  # 1MB limit
                return False
        except:
            return False

        # Check cache for modifications
        file_hash = self._get_file_hash(file_path)
        cached_hash = self.cache.get(str(file_path))

        if cached_hash == file_hash:
            self.stats['files_skipped'] += 1
            return False

        # Update cache
        self.cache[str(file_path)] = file_hash
        return True

    def _get_file_hash(self, file_path: Path) -> str:
        """Get hash of file modification time and size."""
        try:
            stat = file_path.stat()
            return f"{stat.st_mtime}:{stat.st_size}"
        except:
            return ""

    def chunk_text(self, text: str, chunk_size: int = None,
                  overlap: int = None) -> List[str]:
        """Split text into overlapping chunks."""
        chunk_size = chunk_size or self.config.get('chunk_size', 1000)
        overlap = overlap or self.config.get('overlap', 100)

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to end at a sentence or paragraph boundary
            if end < len(text):
                # Look for sentence end
                last_period = chunk.rfind('. ')
                last_newline = chunk.rfind('\n')

                if last_period > chunk_size * 0.8:
                    end = start + last_period + 2
                elif last_newline > chunk_size * 0.8:
                    end = start + last_newline + 1

                chunk = text[start:end]

            chunks.append(chunk.strip())
            start = end - overlap

        return chunks

    def ingest_file(self, file_path: Path) -> int:
        """Ingest a single file into knowledge base."""
        if not self.should_process_file(file_path):
            return 0

        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if not content.strip():
                return 0

            # Determine file type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            chunk_type = 'code' if mime_type and 'text' in mime_type else 'text'

            # Create chunks
            chunks = self.chunk_text(content)

            # Determine tags based on file type and location
            tags = []
            if file_path.suffix:
                tags.append(f"lang:{file_path.suffix[1:]}")
            if 'test' in str(file_path).lower():
                tags.append("test")
            if 'doc' in str(file_path).lower():
                tags.append("documentation")

            # Add chunks to brain
            chunks_added = 0
            for chunk in chunks:
                if chunk:
                    result = self.brain.add_knowledge_chunk(
                        content=chunk,
                        source_path=str(file_path),
                        chunk_type=chunk_type,
                        tags=tags
                    )
                    if result:
                        chunks_added += 1

            self.stats['files_processed'] += 1
            self.stats['chunks_created'] += chunks_added

            return chunks_added

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            self.stats['errors'] += 1
            return 0

    def ingest_directory(self, directory: Path) -> Dict:
        """Ingest all files in a directory recursively."""
        directory = Path(directory).resolve()

        if not directory.exists():
            print(f"Directory does not exist: {directory}")
            return self.stats

        print(f"\n📚 Ingesting knowledge from: {directory}")

        # Find all files
        files_to_process = []
        for root, dirs, files in os.walk(directory):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if not any(
                pattern in d for pattern in self.config.get('exclude_patterns', [])
            )]

            for file in files:
                file_path = Path(root) / file
                if self.should_process_file(file_path):
                    files_to_process.append(file_path)

        print(f"Found {len(files_to_process)} files to process")

        # Process files
        for i, file_path in enumerate(files_to_process, 1):
            chunks = self.ingest_file(file_path)
            if chunks > 0:
                print(f"  [{i}/{len(files_to_process)}] ✓ {file_path.relative_to(directory)} ({chunks} chunks)")

        # Save cache
        self._save_cache()

        return self.stats

    def ingest_configured_paths(self) -> Dict:
        """Ingest all configured paths."""
        paths = self.config.get('ingest_paths', [os.getcwd()])

        for path in paths:
            path = Path(path).expanduser().resolve()
            if path.exists():
                self.ingest_directory(path)

        return self.stats

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search ingested knowledge."""
        return self.brain.search_knowledge(query, limit)


# CLI interface
if __name__ == "__main__":
    import sys

    ingestor = KnowledgeIngestor()

    if len(sys.argv) < 2:
        print("Usage: knowledge_ingest.py [ingest|search] [path|query]")
        print("\nExamples:")
        print("  knowledge_ingest.py ingest /path/to/project")
        print("  knowledge_ingest.py ingest  # ingest current directory")
        print("  knowledge_ingest.py search 'python function'")
        sys.exit(1)

    command = sys.argv[1]

    if command == "ingest":
        if len(sys.argv) > 2:
            path = Path(sys.argv[2])
        else:
            path = Path.cwd()

        stats = ingestor.ingest_directory(path)

        print(f"\n📊 Ingestion Complete:")
        print(f"  Files processed: {stats['files_processed']}")
        print(f"  Chunks created: {stats['chunks_created']}")
        print(f"  Files skipped (unchanged): {stats['files_skipped']}")
        print(f"  Errors: {stats['errors']}")

    elif command == "search":
        if len(sys.argv) < 3:
            print("Please provide a search query")
            sys.exit(1)

        query = " ".join(sys.argv[2:])
        results = ingestor.search(query)

        print(f"\n🔍 Search results for '{query}':")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['source_path']}")
            print(f"   {result['content'][:200]}...")
            if result.get('tags'):
                print(f"   Tags: {', '.join(result['tags'])}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)