#!/usr/bin/env python3
"""
Papyrus Header Generator

Generates header files from Papyrus source files (.psc) for compiled scripts (.pex).
This tool helps speed up compilation by providing function signatures without full implementations.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Set

from src.file_scanner import FileScanner
from src.parser import PapyrusParser
from src.header_generator import HeaderGenerator


def setup_logging(log_file: str = "errors.log"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Generate Papyrus header files from source scripts")
    parser.add_argument("--data-dir", default="Data",
                       help="Directory containing the Data folder structure (default: Data)")
    parser.add_argument("--output-dir", default="Headers",
                       help="Output directory for header files (default: Headers)")
    parser.add_argument("--pattern", default="*.pex",
                       help="Pattern for .pex files to process (default: *.pex)")
    parser.add_argument("--missing-log", default="missing_source.txt",
                       help="File to log missing source files (default: missing_source.txt)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")

    args = parser.parse_args()

    # Normalize data directory path - handle both with and without trailing slash
    # Also strip any surrounding quotes that might be included from command line
    data_dir_str = args.data_dir.strip('"').strip("'")
    data_dir = Path(data_dir_str)

    # If the path ends with "Data" or points to a Data subdirectory, use it directly
    # Otherwise, assume it's the parent directory and append "Data"
    if data_dir.name.lower() == "data":
        scripts_dir = data_dir / "Scripts"
    else:
        scripts_dir = data_dir / "Data" / "Scripts"

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    setup_logging()

    logging.info("Starting Papyrus Header Generator")
    logging.info(f"Data directory: {data_dir}")
    logging.info(f"Scripts directory: {scripts_dir}")
    logging.info(f"Output directory: {args.output_dir}")
    logging.info(f"Pattern: {args.pattern}")

    try:
        # Initialize components
        scanner = FileScanner(str(scripts_dir))
        parser_instance = PapyrusParser()
        generator = HeaderGenerator(args.output_dir)

        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)

        # Find all .pex files
        pex_files = scanner.find_pex_files(args.pattern)
        logging.info(f"Found {len(pex_files)} .pex files")

        # Find corresponding source files
        source_matches = scanner.find_source_files(pex_files)

        # Track missing sources
        missing_sources = []
        processed_count = 0

        # Process each source file
        for pex_file, source_file in source_matches.items():
            if source_file is None:
                missing_sources.append(pex_file)
                continue

            try:
                # Parse source file
                parsed_data = parser_instance.parse_file(source_file)

                # Generate header
                header_path = generator.generate_header(pex_file, parsed_data)
                logging.debug(f"Generated header: {header_path}")
                processed_count += 1

            except Exception as e:
                logging.error(f"Error processing {source_file}: {e}")
                missing_sources.append(pex_file)

        # Log missing sources
        if missing_sources:
            with open(args.missing_log, 'w') as f:
                for missing in missing_sources:
                    f.write(f"{missing}\n")
            logging.warning(f"Could not find source files for {len(missing_sources)} .pex files")
            logging.warning(f"Missing sources logged to: {args.missing_log}")

        logging.info(f"Successfully processed {processed_count} files")
        logging.info(f"Generated headers in: {args.output_dir}")

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
