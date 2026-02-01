"""
BSA Handler Module

Handles extraction and discovery of .pex and .psc files from BSA archive files.
Implements file precedence rules (loose files take priority over BSA contents).
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    from sse_bsa import BSAArchive
    BSA_AVAILABLE = True
except ImportError:
    BSA_AVAILABLE = False
    logging.warning("sse_bsa not available - BSA support disabled")


class BSAHandler:
    """Handles BSA archive file processing for Papyrus scripts."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.bsa_cache: Dict[str, BSAArchive] = {}  # Cache for BSA archive objects
        self.bsa_scripts = {}  # Cache for BSA script files

        if not BSA_AVAILABLE:
            raise ImportError("sse_bsa module required for BSA support")

    def find_bsa_files(self) -> List[Path]:
        """Find all BSA files in the data directory."""
        bsa_files = []

        for bsa_file in self.data_dir.glob("*.bsa"):
            if bsa_file.is_file():
                bsa_files.append(bsa_file)

        logging.info(f"Found {len(bsa_files)} BSA files")
        return bsa_files

    def scan_bsa_for_scripts(self, bsa_files: List[Path], excluded_files: Set[str] = None) -> Dict[str, Dict]:
        """
        Scan BSA files for .pex and .psc files.

        Args:
            bsa_files: List of BSA file paths to scan
            excluded_files: Set of filenames to exclude (loose files take precedence)

        Returns:
            Dict mapping lowercase filename -> {path, type, bsa_file, content}
        """
        if excluded_files is None:
            excluded_files = set()

        script_files = {}

        for bsa_file in bsa_files:
            logging.debug(f"Scanning BSA: {bsa_file.name}")

            try:
                bsa_scripts = self._scan_single_bsa(bsa_file, excluded_files)

                # Merge results, but don't override existing entries (first BSA wins)
                for filename, file_info in bsa_scripts.items():
                    if filename not in script_files:
                        script_files[filename] = file_info

            except Exception as e:
                logging.error(f"Error scanning BSA {bsa_file}: {e}")
                continue

        logging.info(f"Found {len(script_files)} script files in BSA archives")
        return script_files

    def _scan_single_bsa(self, bsa_file: Path, excluded_files: Set[str]) -> Dict[str, Dict]:
        """Scan a single BSA file for script files."""
        script_files = {}

        try:
            archive = self._get_cached_archive(bsa_file)
            if archive is None:
                return script_files

            for file_path in archive.files:
                # Ensure file_path is a string
                file_path_str = str(file_path)
                
                # Check if it's a script file
                file_path_lower = file_path_str.lower()
                if not (file_path_lower.endswith('.pex') or file_path_lower.endswith('.psc')):
                    continue

                # Extract just the filename for comparison
                filename = Path(file_path_str).name.lower()

                # Skip if this file exists as a loose file (precedence rule)
                if filename in excluded_files:
                    logging.debug(f"Skipping BSA file {filename} - loose file takes precedence")
                    continue

                # Determine file type
                file_type = 'pex' if filename.endswith('.pex') else 'psc'

                script_files[filename] = {
                    'path': file_path_str,
                    'type': file_type,
                    'bsa_file': bsa_file,
                }

                logging.debug(f"Found {file_type}: {filename} in {bsa_file.name}")

        except Exception as e:
            logging.error(f"Error parsing BSA {bsa_file}: {e}")

        return script_files

    def _get_cached_archive(self, bsa_file: Path) -> Optional[BSAArchive]:
        """Get a cached BSA archive object or create one if not cached."""
        bsa_path_str = str(bsa_file)
        if bsa_path_str not in self.bsa_cache:
            try:
                archive = BSAArchive(bsa_file)
                self.bsa_cache[bsa_path_str] = archive
                logging.debug(f"Cached BSA archive: {bsa_file.name}")
            except Exception as e:
                logging.error(f"Failed to cache BSA {bsa_file.name}: {e}")
                return None
        return self.bsa_cache.get(bsa_path_str)

    def extract_file_content(self, file_info: Dict) -> Optional[bytes | str]:
        """
        Extract file content from BSA archive using cached archive objects.

        Args:
            file_info: File info dict from scan_bsa_for_scripts

        Returns:
            Bytes for .pex files, string for .psc files, or None if extraction fails
        """
        try:
            bsa_file = file_info['bsa_file']
            file_path = file_info['path']

            # Use cached archive
            archive = self._get_cached_archive(bsa_file)
            if archive is None:
                return None

            # Get file content as bytes using get_file_stream
            content_bytes = archive.get_file_stream(file_path).read()

            if content_bytes is None:
                logging.debug(f"Could not extract {file_path} from {bsa_file.name}")
                return None

            # For .pex files, return raw bytes
            if str(file_path).lower().endswith('.pex'):
                return content_bytes

            # Convert to string (assuming UTF-8 encoding) for .psc files
            try:
                content = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Try with latin-1 as fallback
                content = content_bytes.decode('latin-1', errors='ignore')

            return content

        except Exception as e:
            logging.error(f"Error extracting {file_info['path']} from {file_info['bsa_file']}: {e}")
            return None

    def create_temp_file(self, file_info: Dict, temp_dir: Path) -> Optional[Path]:
        """
        Extract BSA file to a temporary location for processing.

        Args:
            file_info: File info dict from scan_bsa_for_scripts
            temp_dir: Directory to extract file to

        Returns:
            Path to extracted temporary file, or None if extraction fails
        """
        content = self.extract_file_content(file_info)
        if content is None:
            return None

        # Create temp file path
        filename = Path(file_info['path']).name
        temp_file_path = temp_dir / filename

        # Ensure temp directory exists
        os.makedirs(temp_dir, exist_ok=True)

        # Write content to temp file
        try:
            if isinstance(content, bytes):
                # Binary file (e.g., .pex)
                with open(temp_file_path, 'wb') as f:
                    f.write(content)
            else:
                # Text file (e.g., .psc)
                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

            logging.debug(f"Extracted {filename} to {temp_file_path}")
            return temp_file_path

        except Exception as e:
            logging.error(f"Error writing temp file {temp_file_path}: {e}")
            return None
