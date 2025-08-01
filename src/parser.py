"""
Papyrus Parser Module

Parses Papyrus source files (.psc) to extract script signatures, function declarations,
events, and properties for header generation.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class FunctionSignature:
    """Represents a function signature."""
    name: str
    return_type: Optional[str]
    parameters: List[str]
    is_native: bool
    is_event: bool = False


@dataclass
class PropertySignature:
    """Represents a property signature."""
    name: str
    type_name: str
    flags: List[str]  # Auto, AutoReadOnly, etc.


@dataclass
class ParsedScript:
    """Represents a parsed Papyrus script."""
    script_name: str
    extends: Optional[str]
    flags: List[str]  # Hidden, etc.
    functions: List[FunctionSignature]
    events: List[FunctionSignature]
    properties: List[PropertySignature]


class PapyrusParser:
    """Parses Papyrus source files to extract signatures."""

    def __init__(self):
        # Regex patterns for parsing
        self.script_pattern = re.compile(
            r'^\s*Scriptname\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+(Hidden))?\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        # Updated function pattern to handle multiline declarations better
        self.function_pattern = re.compile(
            r'^\s*(?:(\w+)\s+)?Function\s+(\w+)\s*\([^)]*\)(?:\s+(native))?\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        self.event_pattern = re.compile(
            r'^\s*Event\s+(\w+)\s*\([^)]*\)\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        self.property_pattern = re.compile(
            r'^\s*(\w+)\s+Property\s+(\w+)(?:\s*=\s*[^;\r\n]*)?(?:\s+(Auto(?:ReadOnly)?))?\s*$',
            re.IGNORECASE | re.MULTILINE
        )

    def parse_file(self, file_path: Path) -> ParsedScript:
        """Parse a Papyrus source file."""
        logging.debug(f"Parsing file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, 'r', encoding='latin1') as f:
                content = f.read()

        # Clean up content - remove comments and normalize whitespace
        content = self._preprocess_content(content)

        # Parse script declaration
        script_name, extends, flags = self._parse_script_declaration(content)

        # Parse functions
        functions = self._parse_functions(content)

        # Parse events
        events = self._parse_events(content)

        # Parse properties
        properties = self._parse_properties(content)

        return ParsedScript(
            script_name=script_name,
            extends=extends,
            flags=flags,
            functions=functions,
            events=events,
            properties=properties
        )

    def _preprocess_content(self, content: str) -> str:
        """Preprocess content to handle comments and normalize formatting."""
        lines = []
        in_block_comment = False

        for line in content.split('\n'):
            # Handle block comments
            if ';/' in line:
                in_block_comment = True
            if '/;' in line:
                in_block_comment = False
                continue
            if in_block_comment:
                continue

            # Remove line comments
            if ';' in line:
                line = line[:line.index(';')]

            # Keep the line if it has content
            if line.strip():
                lines.append(line)

        return '\n'.join(lines)

    def _parse_script_declaration(self, content: str) -> tuple[str, Optional[str], List[str]]:
        """Parse the Scriptname declaration."""
        match = self.script_pattern.search(content)
        if not match:
            raise ValueError("Could not find Scriptname declaration")

        script_name = match.group(1)
        extends = match.group(2)
        flags = [match.group(3)] if match.group(3) else []

        logging.debug(f"Script: {script_name}, extends: {extends}, flags: {flags}")
        return script_name, extends, flags

    def _parse_functions(self, content: str) -> List[FunctionSignature]:
        """Parse function declarations using a more robust approach."""
        functions = []

        # Split content into lines for line-by-line processing
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Look for function declarations
            if re.match(r'^\s*(?:\w+\s+)?Function\s+\w+', line, re.IGNORECASE):
                # Extract the complete function declaration (may span multiple lines)
                func_declaration = line

                # Check if the function declaration continues on next lines
                while i + 1 < len(lines) and not re.search(r'\)', func_declaration):
                    i += 1
                    func_declaration += ' ' + lines[i].strip()

                # Parse the function declaration
                func_data = self._parse_single_function(func_declaration)
                if func_data:
                    functions.append(func_data)
                    logging.debug(f"Function: {func_data.return_type or 'void'} {func_data.name}({', '.join(func_data.parameters)}) {'native' if func_data.is_native else ''}")

            i += 1

        return functions

    def _parse_single_function(self, declaration: str) -> Optional[FunctionSignature]:
        """Parse a single function declaration."""
        # Pattern to match function declaration
        pattern = r'^\s*(?:(\w+)\s+)?Function\s+(\w+)\s*\((.*?)\)(?:\s+(native))?\s*$'
        match = re.match(pattern, declaration, re.IGNORECASE | re.DOTALL)

        if not match:
            return None

        return_type = match.group(1)
        name = match.group(2)
        params_str = match.group(3)
        is_native = match.group(4) is not None

        parameters = self._parse_parameters(params_str) if params_str.strip() else []

        return FunctionSignature(
            name=name,
            return_type=return_type,
            parameters=parameters,
            is_native=is_native
        )

    def _parse_events(self, content: str) -> List[FunctionSignature]:
        """Parse event declarations using a more robust approach."""
        events = []

        # Split content into lines for line-by-line processing
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Look for event declarations
            if re.match(r'^\s*Event\s+\w+', line, re.IGNORECASE):
                # Extract the complete event declaration (may span multiple lines)
                event_declaration = line

                # Check if the event declaration continues on next lines
                while i + 1 < len(lines) and not re.search(r'\)', event_declaration):
                    i += 1
                    event_declaration += ' ' + lines[i].strip()

                # Parse the event declaration
                event_data = self._parse_single_event(event_declaration)
                if event_data:
                    events.append(event_data)
                    logging.debug(f"Event: {event_data.name}({', '.join(event_data.parameters)})")

            i += 1

        return events

    def _parse_single_event(self, declaration: str) -> Optional[FunctionSignature]:
        """Parse a single event declaration."""
        # Pattern to match event declaration
        pattern = r'^\s*Event\s+(\w+)\s*\((.*?)\)\s*$'
        match = re.match(pattern, declaration, re.IGNORECASE | re.DOTALL)

        if not match:
            return None

        name = match.group(1)
        params_str = match.group(2)

        parameters = self._parse_parameters(params_str) if params_str.strip() else []

        return FunctionSignature(
            name=name,
            return_type=None,
            parameters=parameters,
            is_native=False,
            is_event=True
        )

    def _parse_properties(self, content: str) -> List[PropertySignature]:
        """Parse property declarations."""
        properties = []

        for match in self.property_pattern.finditer(content):
            type_name = match.group(1)
            name = match.group(2)
            flags = [match.group(3)] if match.group(3) else []

            properties.append(PropertySignature(
                name=name,
                type_name=type_name,
                flags=flags
            ))

            logging.debug(f"Property: {type_name} {name} {' '.join(flags)}")

        return properties

    def _parse_parameters(self, params_str: str) -> List[str]:
        """Parse function parameters."""
        if not params_str.strip():
            return []

        parameters = []
        # Split by comma but be careful of default values with commas
        param_parts = []
        paren_depth = 0
        current_part = ""

        for char in params_str:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                param_parts.append(current_part.strip())
                current_part = ""
                continue
            current_part += char

        if current_part.strip():
            param_parts.append(current_part.strip())

        for param in param_parts:
            param = param.strip()
            if param:
                parameters.append(param)

        return parameters
