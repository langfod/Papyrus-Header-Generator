"""
Header Generator Module

Generates Papyrus header files from parsed script data.
"""

import logging
import os
from pathlib import Path
from typing import List

from .parser import ParsedScript, FunctionSignature, PropertySignature


class HeaderGenerator:
    """Generates header files from parsed Papyrus scripts."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def generate_header(self, pex_file: Path, parsed_data: ParsedScript) -> Path:
        """Generate a header file for the parsed script."""
        # Create output filename based on script name
        header_filename = f"{parsed_data.script_name}.psc"
        header_path = self.output_dir / header_filename

        # Generate header content
        content = self._generate_header_content(parsed_data)

        # Write header file
        os.makedirs(header_path.parent, exist_ok=True)
        with open(header_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.debug(f"Generated header: {header_path}")
        return header_path

    def _generate_header_content(self, parsed_data: ParsedScript) -> str:
        """Generate the actual header file content."""
        lines = []

        # Script declaration
        script_line = f"Scriptname {parsed_data.script_name}"
        if parsed_data.extends:
            script_line += f" extends {parsed_data.extends}"
        if parsed_data.flags:
            script_line += f" {' '.join(parsed_data.flags)}"
        lines.append(script_line)
        lines.append("")  # Empty line

        # Properties (if any)
        if parsed_data.properties:
            for prop in parsed_data.properties:
                prop_line = f"{prop.type_name} Property {prop.name}"
                if prop.flags:
                    prop_line += f" {' '.join(prop.flags)}"
                lines.append(prop_line)
            lines.append("")  # Empty line after properties

        # Functions
        if parsed_data.functions:
            for func in parsed_data.functions:
                func_line = self._format_function_signature(func)
                lines.append(func_line)

        # Events
        if parsed_data.events:
            if parsed_data.functions:
                lines.append("")  # Separator between functions and events
            for event in parsed_data.events:
                event_line = self._format_event_signature(event)
                lines.append(event_line)

        return '\n'.join(lines) + '\n'

    def _format_function_signature(self, func: FunctionSignature) -> str:
        """Format a function signature for the header."""
        # Build function signature
        parts = []

        # Return type (if not void)
        if func.return_type:
            parts.append(func.return_type)

        # Function keyword and name
        parts.append(f"Function {func.name}")

        # Parameters
        if func.parameters:
            params_str = f"({', '.join(func.parameters)})"
        else:
            params_str = "()"

        # Native keyword
        native_str = " native" if func.is_native else ""

        return f"{' '.join(parts)}{params_str}{native_str}"

    def _format_event_signature(self, event: FunctionSignature) -> str:
        """Format an event signature for the header."""
        # Parameters
        if event.parameters:
            params_str = f"({', '.join(event.parameters)})"
        else:
            params_str = "()"

        return f"Event {event.name}{params_str}"
