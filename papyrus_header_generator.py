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

from src.file_scanner import FileScanner
from src.parser import PapyrusParser
from src.header_generator import HeaderGenerator


def setup_logging(log_file: str = "errors.log"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),  # 'w' mode overwrites instead of append
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Generate Papyrus header files from source scripts")
    parser.add_argument("--base-dir", default="Data",
                       help="Directory containing the Data folder structure (default: Data)")
    parser.add_argument("--output-dir", default="Headers",
                       help="Output directory for header files (default: Headers)")
    parser.add_argument("--pattern", default="*.pex",
                       help="Pattern for files to process - uses word boundary matching (e.g., 'actor' matches 'Actor.psc' but not 'someactornamedclaude.psc')")
    parser.add_argument("--patternlist", default=None,
                       help="Comma-separated list of patterns to process (e.g., 'actor,potion,idle'). Overrides --pattern if specified.")
    parser.add_argument("--missing-log", default="missing_source.txt",
                       help="File to log missing source files (default: missing_source.txt)")
    parser.add_argument("--enable-bsa", action="store_true", default=False,
                       help="Enable BSA archive scanning (may be slow with many BSA files)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")

    args = parser.parse_args()

    # Normalize data directory path - handle both with and without trailing slash
    # Also strip any surrounding quotes that might be included from command line
    base_dir_str = args.base_dir.strip('"').strip("'")
    base_dir = Path(base_dir_str)

    # If the path ends with "Data" or points to a Data subdirectory, use it directly
    # Otherwise, assume it's the parent directory and append "Data"
    if base_dir.name.lower() == "data":
        scripts_dir = base_dir / "Scripts"
    else:
        scripts_dir = base_dir / "Data" / "Scripts"

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    setup_logging()

    logging.debug("Starting Papyrus Header Generator")
    logging.debug(f"Base directory: {base_dir}")
    logging.debug(f"Scripts directory: {scripts_dir}")
    logging.debug(f"Output directory: {args.output_dir}")
    logging.debug(f"Pattern: {args.pattern}")
    logging.debug(f"BSA support: {'enabled' if args.enable_bsa else 'disabled'}")

    try:
        scanner = FileScanner(str(scripts_dir), enable_bsa=args.enable_bsa)
        parser_instance = PapyrusParser()
        generator = HeaderGenerator(args.output_dir)

        os.makedirs(args.output_dir, exist_ok=True)


        # Step 1: Find and process all .psc source files first (highest priority)
        # Use pattern for .psc files, case-insensitive with word boundary matching
        import re
        
        # Determine which patterns to use
        if args.patternlist:
            patterns = [p.strip() for p in args.patternlist.split(',')]
            pattern_desc = f"patterns {patterns}"
        else:
            patterns = [args.pattern]
            pattern_desc = f"pattern '{args.pattern}'"
        
        # Create regex for each pattern and combine with OR
        pattern_regexes = [re.compile(r'\b' + re.escape(pattern) + r'\b', re.IGNORECASE) for pattern in patterns]
        
        def matches_any_pattern(filename_or_path):
            """Check if filename or path matches any of the patterns."""
            return any(regex.search(os.path.basename(str(filename_or_path)).replace('.psc', '')) or 
                      regex.search(str(filename_or_path)) for regex in pattern_regexes)
        
        psc_files = [f for f in scanner.find_psc_files() if matches_any_pattern(f)]
        logging.info(f"Found {len(psc_files)} .psc source files matching {pattern_desc} (case-insensitive, word boundaries)")

        # Track missing sources and processed count
        missing_sources = []
        processed_count = 0

        # Process .psc source files directly
        for psc_file in psc_files:
            logging.debug(f"Processing .psc source file: {psc_file}")
            try:
                # Parse source file
                parsed_data = parser_instance.parse_file(psc_file)

                # Generate header - use the .psc file's stem as the base name
                relative_path = scanner.get_relative_psc_path(psc_file)
                synthetic_pex_path = scripts_dir / relative_path.replace('.psc', '.pex')

                header_path = generator.generate_header(synthetic_pex_path, parsed_data)
                logging.debug(f"Generated header from .psc: {header_path}")
                processed_count += 1

            except Exception as e:
                logging.error(f"Error processing .psc file {psc_file}: {e}")
                missing_sources.append(str(psc_file))

        # Step 2: Find and process .pex files that don't have corresponding .psc files
        pex_without_psc = scanner.find_pex_without_psc(psc_files, args.pattern)
        # Filter .pex files by pattern, case-insensitive with word boundary matching
        pex_without_psc = [f for f in pex_without_psc if matches_any_pattern(f)]
        logging.info(f"Found {len(pex_without_psc)} .pex files without .psc sources matching {pattern_desc} (case-insensitive, word boundaries)")

        if pex_without_psc:
            # Find corresponding source files for .pex files (may be in BSA or need decompilation)
            source_matches = scanner.find_source_files(pex_without_psc)

            # Process each .pex file without .psc source
            for pex_file, source_file in source_matches.items():
                logging.debug(f"Processing .pex file: {pex_file}")

                if source_file is None:
                    logging.warning(f"No source available for .pex file: {pex_file}")
                    missing_sources.append(str(pex_file))
                    continue

                try:
                    # Parse source file (could be from BSA or decompiled)
                    parsed_data = parser_instance.parse_file(source_file)

                    # Generate header
                    header_path = generator.generate_header(pex_file, parsed_data)
                    logging.debug(f"Generated header from .pex: {header_path}")
                    processed_count += 1

                except Exception as e:
                    logging.error(f"Error processing .pex file {pex_file}: {e}")
                    missing_sources.append(str(pex_file))

        # Log missing sources
        if missing_sources:
            with open(args.missing_log, 'w') as f:
                for missing in missing_sources:
                    f.write(f"{missing}\n")
            logging.warning(f"Could not process {len(missing_sources)} files")
            logging.warning(f"Missing sources logged to: {args.missing_log}")

        logging.info(f"Successfully processed {processed_count} files")
        logging.info(f"Generated headers in: {args.output_dir}")

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
