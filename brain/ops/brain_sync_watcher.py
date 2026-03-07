import os
import asyncio
import json
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from neural_memory import Brain
from neural_memory.storage import SQLiteStorage
from neural_memory.engine.encoder import MemoryEncoder
from layer3_metadata import (
    build_chunk_metadata,
    build_tags,
    derive_project_name,
    infer_source_timestamp,
    resolve_workspace_root,
)

# Configuration
WORKSPACE_ROOT = resolve_workspace_root(__file__)
MONITOR_PATTERN = os.path.join("brain", "layer1_stream")
BRAIN_PREFIX = "antigravity_"
STATE_FILE = os.path.join(WORKSPACE_ROOT, "brain", "ops", ".sync_state.json")
DB_PATH = os.path.join(WORKSPACE_ROOT, "brain", "layer3_index", "neural_memory.db")

class LogSyncHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop
        self.offsets = self._load_state()
        self.brains = {} # project_name -> brain_obj
        self.storage = SQLiteStorage(DB_PATH)
        self._init_done = False

    async def initialize(self):
        await self.storage.initialize()
        self._init_done = True
        print("Storage Initialized.")

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.offsets, f)
        except Exception as e:
            print(f"Failed to save state: {e}")

    async def _get_brain_for_project(self, project_name):
        if project_name in self.brains:
            return self.brains[project_name]

        # Normalized name: SEO - EDF -> seo_edf
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', project_name.lower())
        clean_name = re.sub(r'_+', '_', clean_name).strip('_')
        safe_name = BRAIN_PREFIX + clean_name
        
        brain_obj = await self.storage.find_brain_by_name(safe_name)
        
        if not brain_obj:
            print(f"Creating new brain for project: {project_name} -> {safe_name}")
            brain_obj = Brain.create(safe_name)
            await self.storage.save_brain(brain_obj)
        
        self.brains[project_name] = brain_obj
        return brain_obj

    async def _get_encoder(self, project_name):
        brain = await self._get_brain_for_project(project_name)
        self.storage.set_brain(brain.id)
        return MemoryEncoder(self.storage, brain.config)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            norm_path = os.path.normpath(event.src_path)
            if MONITOR_PATTERN in norm_path:
                self.loop.call_soon_threadsafe(
                    asyncio.create_task, self.process_file(norm_path)
                )

    async def process_file(self, file_path):
        try:
            if not self._init_done:
                return
            
            norm_path = os.path.normpath(file_path)
            project_name = derive_project_name(norm_path, WORKSPACE_ROOT)
            source_timestamp = infer_source_timestamp(norm_path)

            await asyncio.sleep(0.5)
            
            with open(norm_path, 'r', encoding='utf-8') as f:
                last_offset = self.offsets.get(norm_path, 0)
                f.seek(0, os.SEEK_END)
                current_size = f.tell()
                
                if current_size <= last_offset == 0:
                    pass
                elif current_size < last_offset:
                    last_offset = 0
                
                f.seek(last_offset)
                new_content = f.read()
                
                if not new_content.strip():
                    return

                print(f"[{project_name}] New content in {os.path.basename(norm_path)}")
                
                brain = await self._get_brain_for_project(project_name)
                encoder = await self._get_encoder(project_name)
                chunks = self._chunk_content(new_content)
                for chunk in chunks:
                    if len(chunk["content"].strip()) > 10:
                        metadata = build_chunk_metadata(
                            file_path=norm_path,
                            workspace_root=WORKSPACE_ROOT,
                            project_name=project_name,
                            brain_name=brain.name,
                            chunk=chunk,
                            source_timestamp=source_timestamp,
                        )
                        tags = build_tags(metadata)
                        await encoder.encode(
                            chunk["content"],
                            timestamp=source_timestamp,
                            metadata=metadata,
                            tags=tags,
                        )
                        heading = metadata.get("source_heading", "(no heading)")
                        print(
                            f"  Synced to {brain.name}: "
                            f"{heading} [chunk {metadata['chunk_index'] + 1}/{metadata['chunk_count']}]"
                        )

                self.offsets[norm_path] = current_size
                self._save_state()
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    def _chunk_content(self, text):
        """
        Phase 2 Upgrade: Metadata-aware semantic chunking
        - Respects Markdown Headers
        - Implements Overlap
        - Filters noisy short text
        """
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_header = ""
        
        def flush_chunk():
            content = "\n".join(current_chunk).strip()
            if len(content) > 15:
                chunks.append(
                    {
                        "content": content,
                        "heading": current_header or None,
                    }
                )
        
        for line in lines:
            line = line.strip().lstrip("\ufeff")
            if not line:
                continue
            
            # If it's a header, start a new chunk but include context
            if line.startswith('#'):
                if current_chunk:
                    flush_chunk()
                    # Overlap: keep the last 2 lines for context
                    current_chunk = current_chunk[-2:] if len(current_chunk) > 2 else current_chunk
                
                current_header = line
                current_chunk.append(line)
            else:
                current_chunk.append(line)
                
                # Max chunk size ~500 chars
                if len("\n".join(current_chunk)) > 500:
                    flush_chunk()
                    # Overlap
                    current_chunk = [current_header] + current_chunk[-2:] if current_header else current_chunk[-3:]

        if current_chunk:
            flush_chunk()

        total_chunks = len(chunks)
        for index, chunk in enumerate(chunks):
            chunk["chunk_index"] = index
            chunk["chunk_count"] = total_chunks

        return chunks

async def main():
    print("NeuralMemory Multi-Project Watcher Started...")
    
    loop = asyncio.get_running_loop()
    handler = LogSyncHandler(loop)
    await handler.initialize()
    
    print(f"Initial scan in {WORKSPACE_ROOT}...")
    EXCLUDE_DIRS = {'.git', 'node_modules', '.gemini', 'venv', '__pycache__'}
    
    for root, dirs, files in os.walk(WORKSPACE_ROOT):
        # Skip excluded dirs in-place to speed up walk
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        norm_root = os.path.normpath(root)
        if MONITOR_PATTERN in norm_root:
            print(f"Found log directory: {norm_root}")
            for file in files:
                if file.endswith(".md"):
                    await handler.process_file(os.path.join(norm_root, file))

    observer = Observer()
    observer.schedule(handler, WORKSPACE_ROOT, recursive=True)
    observer.start()
    
    print("Watcher is active and monitoring all projects.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
