"""
File Scanner Module

Handles discovery of .pex files and matching them with their corresponding .psc source files.
"""

import glob
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional


class FileScanner:
    """Scans for .pex files and finds corresponding .psc source files."""
    
    def __init__(self, scripts_dir: str):
        self.scripts_dir = Path(scripts_dir)
        # Update search paths to be relative to the data directory
        data_dir = self.scripts_dir.parent  # Go up from Scripts to Data
        self.source_search_paths = [
            data_dir / "Source" / "Scripts",
            data_dir / "Scripts" / "Source",
            data_dir / "Scripts" / "Souce",  # Original typo in requirements
            data_dir / "Scripts"
        ]
        
    def find_pex_files(self, pattern: str = "*.pex") -> List[Path]:
        """Find all .pex files matching the pattern."""
        pex_files = []
        
        # Search in the main scripts directory and subdirectories
        for pex_file in self.scripts_dir.rglob(pattern):
            if pex_file.is_file() and pex_file.suffix.lower() == '.pex':
                pex_files.append(pex_file)
                
        logging.info(f"Found {len(pex_files)} .pex files")
        return pex_files
    
    def find_source_files(self, pex_files: List[Path]) -> Dict[Path, Optional[Path]]:
        """Find corresponding .psc source files for each .pex file."""
        source_matches = {}
        
        # Build a cache of all .psc files for efficient lookup
        psc_cache = self._build_psc_cache()
        
        for pex_file in pex_files:
            source_file = self._find_matching_source(pex_file, psc_cache)
            source_matches[pex_file] = source_file
            
            if source_file:
                logging.debug(f"Matched {pex_file.name} -> {source_file}")
            else:
                logging.debug(f"No source found for {pex_file.name}")
                
        found_count = sum(1 for source in source_matches.values() if source is not None)
        logging.info(f"Found source files for {found_count}/{len(pex_files)} .pex files")
        
        return source_matches
    
    def _build_psc_cache(self) -> Dict[str, Path]:
        """Build a cache of all .psc files indexed by lowercase filename."""
        psc_cache = {}
        
        for search_path in self.source_search_paths:
            path = Path(search_path)
            if not path.exists():
                continue
                
            for psc_file in path.rglob("*.psc"):
                if psc_file.is_file():
                    # Use lowercase filename as key for case-insensitive matching
                    key = psc_file.stem.lower()
                    if key not in psc_cache:  # First match wins (precedence)
                        psc_cache[key] = psc_file
                        
        logging.info(f"Cached {len(psc_cache)} .psc files")
        return psc_cache
    
    def _find_matching_source(self, pex_file: Path, psc_cache: Dict[str, Path]) -> Optional[Path]:
        """Find matching .psc file for a .pex file."""
        # Get the base name without extension (case-insensitive)
        pex_name = pex_file.stem.lower()
        
        # Look up in cache
        return psc_cache.get(pex_name)
    
    def get_relative_path(self, pex_file: Path) -> str:
        """Get relative path from scripts directory for organizing output."""
        try:
            return str(pex_file.relative_to(self.scripts_dir))
        except ValueError:
            # If file is not under scripts_dir, use just the filename
            return pex_file.name
