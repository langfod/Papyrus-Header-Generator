Attempt at generating Papyrus header files for offline usage of [russo-2025/papyrus-compiler](https://github.com/russo-2025/papyrus-compiler)

extract Champollion.exe from https://github.com/Orvid/Champollion/releases
```
usage: papyrus_header_generator.py [-h] [--base-dir BASE_DIR] [--output-dir OUTPUT_DIR] [--pattern PATTERN]
                                   [--missing-log MISSING_LOG] [--enable-bsa] [--verbose]

Generate Papyrus header files from source scripts

options:
  -h, --help            show this help message and exit
  --base-dir BASE_DIR   Directory containing the Data folder structure (default: Data)
  --output-dir OUTPUT_DIR
                        Output directory for header files (default: Headers)
  --pattern PATTERN     Pattern for files to process
  --pattern [PATTERN,PATTERN]     list of files to process
  --missing-log MISSING_LOG
                        File to log missing source files (default: missing_source.txt)
  --enable-bsa          Enable BSA archive scanning (may be slow with many BSA files)
  --verbose, -v         Enable verbose logging
```

so something like:
```
papyrus_header_generator.py --base-dir "D:\SteamLibrary\steamapps\common\Skyrim Special Edition" --enable-bsa
```
will scan all scripts in loose or in bsa's , find their sources files and create "header" files inside a Header directory.
