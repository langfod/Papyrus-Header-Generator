"""
BSA Handler Module

Handles extraction and discovery of .pex and .psc files from BSA archive files.
Implements file precedence rules (loose files take priority over BSA contents).
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from io import BytesIO

try:
    from bethesda_structs.archive import BSAArchive
    BSA_AVAILABLE = True
except ImportError:
    BSA_AVAILABLE = False
    logging.warning("bethesda_structs not available - BSA support disabled")


class BSAHandler:
    """Handles BSA archive file processing for Papyrus scripts."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.bsa_cache = {}  # Cache for BSA archive objects
        self.bsa_scripts = {}  # Cache for BSA script files

        if not BSA_AVAILABLE:
            raise ImportError("bethesda_structs module required for BSA support")

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

        if not BSAArchive.can_handle(str(bsa_file)):
            logging.warning(f"Cannot handle BSA format: {bsa_file}")
            return script_files

        try:
            archive = BSAArchive.parse_file(str(bsa_file))

            for file_record in archive.iter_files():
                # Get the file path within the BSA - try different possible attributes
                file_path = None
                if hasattr(file_record, 'name'):
                    file_path = file_record.name
                elif hasattr(file_record, 'filepath'):
                    file_path = file_record.filepath
                elif hasattr(file_record, 'path'):
                    file_path = file_record.path
                else:
                    # If we can't get the path, try to extract it from the record
                    try:
                        file_path = str(file_record)
                    except:
                        logging.debug(f"Could not determine file path for record: {file_record}")
                        continue

                if not file_path:
                    continue

                # Convert file_path to string if it's a Path object
                file_path_str = str(file_path)

                # Check if it's a script file
                if not (file_path_str.lower().endswith('.pex') or file_path_str.lower().endswith('.psc')):
                    continue

                # Extract just the filename for comparison
                filename = Path(file_path_str).name.lower()

                # Skip if this file exists as a loose file (precedence rule)
                if filename in excluded_files:
                    logging.debug(f"Skipping BSA file {filename} - loose file takes precedence")
                    continue

                # Determine file type and expected location
                file_type = 'pex' if filename.endswith('.pex') else 'psc'

                script_files[filename] = {
                    'path': file_path,
                    'type': file_type,
                    'bsa_file': bsa_file,
                    'file_record': file_record,
                    'archive': None  # Will be loaded on demand
                }

                logging.debug(f"Found {file_type}: {filename} in {bsa_file.name}")

        except Exception as e:
            logging.error(f"Error parsing BSA {bsa_file}: {e}")

        return script_files

    def _get_cached_archive(self, bsa_file: Path):
        """Get a cached BSA archive object or create one if not cached."""
        bsa_path_str = str(bsa_file)
        if bsa_path_str not in self.bsa_cache:
            try:
                archive = BSAArchive.parse_file(bsa_path_str)
                self.bsa_cache[bsa_path_str] = archive
                logging.debug(f"Cached BSA archive: {bsa_file.name}")
            except Exception as e:
                logging.error(f"Failed to cache BSA {bsa_file.name}: {e}")
                return None
        return self.bsa_cache.get(bsa_path_str)

    def extract_file_content(self, file_info: Dict) -> Optional[str]:
        """
        Extract file content from BSA archive using cached archive objects.

        Args:
            file_info: File info dict from scan_bsa_for_scripts

        Returns:
            String content of the file, or None if extraction fails
        """
        try:
            bsa_file = file_info['bsa_file']
            file_path = file_info['path']
            file_record = file_info['file_record']

            # Use cached archive instead of re-parsing every time
            archive = self._get_cached_archive(bsa_file)
            if archive is None:
                return None

            # Try different extraction approaches - but limit expensive operations
            content_bytes = None

            # Method 1: Try using file record directly (fastest)
            if hasattr(file_record, 'extract'):
                try:
                    content_bytes = file_record.extract()
                    if content_bytes:
                        logging.debug(f"Extracted {file_path} using method 1 (file_record.extract)")
                except Exception as e:
                    logging.debug(f"Method 1 failed for {file_path}: {e}")

            # Method 2: Try archive.extract with normalized path (fast)
            if content_bytes is None and hasattr(archive, 'extract'):
                try:
                    content_bytes = file_record.data
                    if content_bytes:
                        logging.debug(f"Extracted {file_path} using method 2 (file_record.data)")
                except Exception as e:
                    logging.debug(f"Method 2 failed for {file_path}: {e}")

            # Method 3: Try opening file record as file-like object
            if content_bytes is None and hasattr(file_record, 'open'):
                try:
                    with file_record.open() as f:
                        content_bytes = f.read()
                    if content_bytes:
                        logging.debug(f"Extracted {file_path} using method 3 (file_record.open)")
                except Exception as e:
                    logging.debug(f"Method 3 failed for {file_path}: {e}")

            if content_bytes is None:
                logging.debug(f"Could not extract {file_path} from {bsa_file.name}")
                return None

            # For .pex files, return raw bytes instead of trying to decode as text
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
