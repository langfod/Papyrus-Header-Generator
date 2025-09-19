# Papyrus Header Generator

Attempt at generating Papyrus header files for offline usage of [russo-2025/papyrus-compiler](https://github.com/russo-2025/papyrus-compiler).

This tool extracts function signatures, properties, and class declarations from Papyrus source files (.psc) and compiled scripts (.pex) to generate header files that speed up compilation by providing type information without full implementations.

## Features

- **Source File Processing**: Reads .psc source files directly for accurate headers
- **BSA Archive Support**: Extracts source files from BSA archives when available
- **Decompilation Support**: Uses Champollion to decompile .pex files when no source is available
- **Intelligent Fallback**: Tries source files first, then BSA archives, then decompilation as a last resort
- **Pattern Matching**: Supports wildcards and specific script targeting
- **Error Handling**: Comprehensive logging and error reporting

## Prerequisites

Extract Champollion.exe from https://github.com/Orvid/Champollion/releases for decompilation support.

## Usage

```
usage: papyrus_header_generator.py [-h] [--base-dir BASE_DIR] [--output-dir OUTPUT_DIR] [--pattern PATTERN]
                                   [--patternlist PATTERNLIST] [--missing-log MISSING_LOG] [--enable-bsa] 
                                   [--enable-decompile] [--champollion-path CHAMPOLLION_PATH] [--verbose]

Generate Papyrus header files from source scripts

options:
  -h, --help            show this help message and exit
  --base-dir BASE_DIR   Directory containing the Data folder structure (default: Data)
  --output-dir OUTPUT_DIR
                        Output directory for header files (default: Headers)
  --pattern PATTERN     Pattern for files to process - uses word boundary matching (e.g., 'actor' matches 'Actor.psc' but not 'someactornamedclaude.psc')
  --patternlist PATTERNLIST
                        Comma-separated list of patterns to process (e.g., 'actor,potion,idle'). Overrides --pattern if specified.
  --missing-log MISSING_LOG
                        File to log missing source files (default: missing_source.txt)
  --enable-bsa          Enable BSA archive scanning (may be slow with many BSA files)
  --enable-decompile    Enable decompilation of .pex files using Champollion when no .psc source is found
  --champollion-path CHAMPOLLION_PATH
                        Path to Champollion.exe or directory containing it (auto-detected if not specified)
  --verbose, -v         Enable verbose logging
```

## Examples

### Basic usage (scan all scripts with BSA support):
```bash
python papyrus_header_generator.py --base-dir "D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data" --enable-bsa
```

### With decompilation enabled:
```bash
python papyrus_header_generator.py --base-dir "D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data" --enable-bsa --enable-decompile --champollion-path "D:\opt\Champollion-V1.0.1-x64"
```

### Process specific scripts:
```bash
python papyrus_header_generator.py --base-dir "Data" --pattern "actor" --enable-decompile
```

### Process multiple specific patterns:
```bash
python papyrus_header_generator.py --base-dir "Data" --patternlist "actor,potion,idle" --enable-decompile
```

### Process wildcard patterns:
```bash
python papyrus_header_generator.py --base-dir "Data" --pattern "da04*" --enable-decompile
```

## Source Priority

The tool uses the following priority order when looking for script sources:

1. **Loose .psc files** - Highest priority, found in Data/Scripts/Source or Data/Source/Scripts
2. **BSA archive sources** - .psc files extracted from BSA archives 
3. **Decompilation** - .pex files decompiled using Champollion as a last resort

## Decompilation Support

When `--enable-decompile` is specified, the tool will:

1. Look for Champollion.exe in the specified path or common locations
2. Test that Champollion is working correctly
3. Decompile .pex files to temporary .psc files when no source is found
4. Process the decompiled sources to generate headers
5. Clean up temporary files automatically

Auto-detected Champollion locations:
- Current directory: `Champollion.exe`
- User specified default: `D:\opt\Champollion-V1.0.1-x64\Champollion.exe`
- Program Files: `C:\Program Files\Champollion\Champollion.exe`
- Program Files (x86): `C:\Program Files (x86)\Champollion\Champollion.exe`

## Output

The tool scans all scripts in loose files or BSAs, finds their source files, and creates "header" files inside the Headers directory.
