"""
File Scanner Module

Handles discovery of .pex files and matching them with their corresponding .psc source files.
Supports both loose files and BSA archive files with proper precedence rules.
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from .bsa_handler import BSAHandler, BSA_AVAILABLE


class FileScanner:
    """Scans for .pex files and finds corresponding .psc source files."""
    
    def __init__(self, scripts_dir: str, enable_bsa: bool = True):
        self.scripts_dir = Path(scripts_dir)
        # Update search paths to be relative to the data directory
        data_dir = self.scripts_dir.parent  # Go up from Scripts to Data
        self.data_dir = data_dir
        self.source_search_paths = [
            data_dir / "Source" / "Scripts",
            data_dir / "Scripts" / "Source",
            data_dir / "Scripts" / "Souce",  # handle some typos
            data_dir / "Scripts"
        ]
        
        # BSA support
        self.enable_bsa = enable_bsa and BSA_AVAILABLE
        self.bsa_handler = None
        self.bsa_scripts = {}  # Cache for BSA script files
        self.temp_dir = None  # For extracted BSA files

        if self.enable_bsa:
            try:
                self.bsa_handler = BSAHandler(data_dir)
                self.temp_dir = Path(tempfile.mkdtemp(prefix="papyrus_bsa_"))
                logging.info(f"BSA support enabled - temp dir: {self.temp_dir}")
            except ImportError as e:
                logging.warning(f"BSA support disabled: {e}")
                self.enable_bsa = False
        else:
            logging.info("BSA support disabled")

    def __del__(self):
        """Cleanup temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logging.debug(f"Cleaned up temp dir: {self.temp_dir}")
            except Exception as e:
                logging.warning(f"Could not clean up temp dir {self.temp_dir}: {e}")

    def find_psc_files(self) -> List[Path]:
        """Find all .psc source files in the search paths."""
        psc_files = []
        found_files = set()
        
        for search_path in self.source_search_paths:
            path = Path(search_path)
            if not path.exists():
                continue
                
            for psc_file in path.rglob("*.psc"):
                if psc_file.is_file():
                    abs_path = psc_file.absolute()
                    if abs_path not in found_files:
                        found_files.add(abs_path)
                        psc_files.append(psc_file)
                    
        logging.info(f"Found {len(psc_files)} .psc source files")
        return psc_files

    def find_pex_files(self, pattern: str = "*.pex") -> List[Path]:
        """Find all .pex files matching the pattern in loose files and BSA archives."""
        pex_files = []

        # First, find loose .pex files
        loose_pex_files = self._find_loose_pex_files(pattern)
        pex_files.extend(loose_pex_files)

        # Then, find .pex files in BSA archives (if enabled)
        if self.enable_bsa:
            bsa_pex_files = self._find_bsa_pex_files(pattern, loose_pex_files)
            pex_files.extend(bsa_pex_files)

        logging.info(f"Found {len(pex_files)} .pex files total")
        return pex_files

    def _find_loose_pex_files(self, pattern: str) -> List[Path]:
        """Find loose .pex files in the scripts directory."""
        pex_files = []
        
        for pex_file in self.scripts_dir.rglob(pattern):
            if pex_file.is_file() and pex_file.suffix.lower() == '.pex':
                pex_files.append(pex_file)
                
        logging.info(f"Found {len(pex_files)} loose .pex files")
        return pex_files
    
    def _find_bsa_pex_files(self, pattern: str, loose_pex_files: List[Path]) -> List[Path]:
        """Find .pex files in BSA archives, excluding those that exist as loose files."""
        if not self.bsa_handler:
            return []

        # Create set of loose filenames for exclusion
        loose_filenames = {pex_file.name.lower() for pex_file in loose_pex_files}

        # Find BSA files and scan them
        bsa_files = self.bsa_handler.find_bsa_files()
        if not bsa_files:
            return []

        self.bsa_scripts = self.bsa_handler.scan_bsa_for_scripts(bsa_files, loose_filenames)

        # Extract .pex files that match the pattern
        bsa_pex_files = []
        for filename, file_info in self.bsa_scripts.items():
            if file_info['type'] == 'pex':
                if self._matches_pattern(filename, pattern.lower()):
                    # Create a virtual path for BSA files
                    virtual_path = self.scripts_dir / f"[BSA:{file_info['bsa_file'].name}]" / filename
                    bsa_pex_files.append(virtual_path)

        logging.info(f"Found {len(bsa_pex_files)} .pex files in BSA archives")
        return bsa_pex_files

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Simple pattern matching for BSA files."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)

    def find_pex_without_psc(self, psc_files: List[Path], pattern: str = "*.pex") -> List[Path]:
        """Find .pex files that don't have corresponding .psc source files."""
        psc_script_names = set()
        for psc_file in psc_files:
            psc_script_names.add(psc_file.stem.lower())
        
        # Find all .pex files
        all_pex_files = self.find_pex_files(pattern)
        
        # Filter out .pex files that have corresponding .psc files
        pex_without_psc = []
        for pex_file in all_pex_files:
            if "[BSA:" in str(pex_file):
                pex_name = pex_file.name.lower().replace('.pex', '')
            else:
                pex_name = pex_file.stem.lower()
            
            if pex_name not in psc_script_names:
                pex_without_psc.append(pex_file)
        
        logging.info(f"Found {len(pex_without_psc)} .pex files without corresponding .psc sources")
        return pex_without_psc

    def find_source_files(self, pex_files: List[Path]) -> Dict[Path, Optional[Path]]:
        """Find corresponding .psc source files for each .pex file."""
        source_matches = {}
        
        loose_psc_cache = self._build_loose_psc_cache()

        for pex_file in pex_files:
            source_file = self._find_matching_source(pex_file, loose_psc_cache)
            source_matches[pex_file] = source_file
            
            if source_file:
                logging.debug(f"Matched {pex_file.name} -> {source_file}")
            else:
                logging.debug(f"No source found for {pex_file.name}")
                
        found_count = sum(1 for source in source_matches.values() if source is not None)
        logging.info(f"Found source files for {found_count}/{len(pex_files)} .pex files")
        
        return source_matches
    
    def _build_loose_psc_cache(self) -> Dict[str, Path]:
        """Build a cache of loose .psc files indexed by lowercase filename."""
        psc_cache = {}
        
        for search_path in self.source_search_paths:
            path = Path(search_path)
            if not path.exists():
                continue
                
            for psc_file in path.rglob("*.psc"):
                if psc_file.is_file():
                    key = psc_file.stem.lower()
                    if key not in psc_cache:  # First match wins (precedence)
                        psc_cache[key] = psc_file
                        
        logging.info(f"Cached {len(psc_cache)} loose .psc files")
        return psc_cache
    
    def _find_matching_source(self, pex_file: Path, loose_psc_cache: Dict[str, Path]) -> Optional[Path]:
        """Find matching .psc file for a .pex file (loose files first, then BSA)."""
        if "[BSA:" in str(pex_file):
            pex_name = pex_file.name.lower().replace('.pex', '')
        else:
            pex_name = pex_file.stem.lower()

        # First, try loose files (highest precedence)
        loose_source = loose_psc_cache.get(pex_name)
        if loose_source:
            return loose_source

        # Then, try BSA files (if enabled and available)
        if self.enable_bsa and self.bsa_scripts:
            bsa_psc_name = f"{pex_name}.psc"
            if bsa_psc_name in self.bsa_scripts:
                file_info = self.bsa_scripts[bsa_psc_name]
                temp_file = self.bsa_handler.create_temp_file(file_info, self.temp_dir)
                if temp_file:
                    logging.debug(f"Extracted BSA source: {bsa_psc_name} -> {temp_file}")
                    return temp_file

        return None

    def get_relative_path(self, pex_file: Path) -> str:
        """Get relative path from scripts directory for organizing output."""
        try:
            if "[BSA:" in str(pex_file):
                return f"BSA/{pex_file.name}"
            else:
                return str(pex_file.relative_to(self.scripts_dir))
        except ValueError:
            return pex_file.name
    
    def get_relative_psc_path(self, psc_file: Path) -> str:
        """Get relative path from any source directory for organizing output."""
        for search_path in self.source_search_paths:
            try:
                relative_path = psc_file.relative_to(search_path)
                return str(relative_path)
            except ValueError:
                continue
        
        return psc_file.name
