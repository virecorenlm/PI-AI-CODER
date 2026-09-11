#!/usr/bin/env python3
"""Backward-compatibility shim.

The context manager now lives in ``pi_ai_coder.context.manager``. This
module re-exports the same names so any existing external imports of
``context_manager`` keep working unchanged.
"""

from pi_ai_coder.context.manager import ContextManager, FileChunk

__all__ = ["ContextManager", "FileChunk"]

if __name__ == "__main__":
    # Preserve the original self-test behavior.
    cm = ContextManager()

    chunks = cm.load_file(__file__)
    print(f"Loaded {len(chunks)} chunks from this file")

    for chunk in chunks[:3]:
        print(f"\nChunk {chunk.start_line}-{chunk.end_line} ({chunk.chunk_type}):")
        print(chunk.content[:100] + "...")

    context = cm.build_context([__file__], "how to chunk files")
    print(f"\n\nBuilt context: {len(context)} chars")
