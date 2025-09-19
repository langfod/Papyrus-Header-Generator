"""
Champollion Decompiler Module

Handles decompilation of .pex files using the Champollion decompiler tool.
Provides fallback source code generation when no .psc source files are available.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class ChampollionDecompiler:
    """Handles decompilation of .pex files using Champollion."""
    
    def __init__(self, champollion_path: Optional[str] = None, enable_decompile: bool = False):
        """
        Initialize the decompiler.
        
        Args:
            champollion_path: Path to Champollion.exe executable
            enable_decompile: Whether to enable decompilation features
        """
        self.enable_decompile = enable_decompile
        self.champollion_path = None
        self.temp_dir = None
        
        if enable_decompile:
            self._validate_champollion_path(champollion_path)
            if self.champollion_path:
                # Create temporary directory for decompiled files
                self.temp_dir = Path(tempfile.mkdtemp(prefix="papyrus_decompile_"))
                logging.info(f"Decompilation enabled - temp dir: {self.temp_dir}")
        else:
            logging.info("Decompilation disabled")
    
    def __del__(self):
        """Cleanup temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logging.debug(f"Cleaned up decompile temp dir: {self.temp_dir}")
            except Exception as e:
                logging.warning(f"Could not clean up decompile temp dir {self.temp_dir}: {e}")
    
    def _validate_champollion_path(self, champollion_path: Optional[str]) -> None:
        """
        Validate and set the Champollion executable path.
        
        Args:
            champollion_path: Path to Champollion.exe or directory containing it
        
        Raises:
            RuntimeError: If decompilation is enabled but Champollion cannot be found
        """
        if not champollion_path:
            # Try some common locations
            common_paths = [
                "Champollion.exe",  # Current directory
                "D:\\opt\\Champollion-V1.0.1-x64\\Champollion.exe",  # User's specified default
                "C:\\Program Files\\Champollion\\Champollion.exe",
                "C:\\Program Files (x86)\\Champollion\\Champollion.exe",
            ]
            
            for path in common_paths:
                if Path(path).exists():
                    self.champollion_path = Path(path)
                    logging.info(f"Found Champollion at: {self.champollion_path}")
                    return
        else:
            # User provided a path
            path = Path(champollion_path)
            
            if path.is_file() and path.name.lower() == "champollion.exe":
                # Direct path to executable
                self.champollion_path = path
            elif path.is_dir():
                # Directory containing the executable
                exe_path = path / "Champollion.exe"
                if exe_path.exists():
                    self.champollion_path = exe_path
                else:
                    raise RuntimeError(f"Champollion.exe not found in directory: {path}")
            else:
                raise RuntimeError(f"Invalid Champollion path: {champollion_path}")
            
            logging.info(f"Using Champollion at: {self.champollion_path}")
            return
        
        # If we get here, Champollion was not found
        raise RuntimeError(
            "Decompilation is enabled but Champollion.exe was not found. "
            "Please specify the path using --champollion-path or ensure it's in a common location."
        )
    
    def is_available(self) -> bool:
        """Check if decompilation is available."""
        return self.enable_decompile and self.champollion_path is not None
    
    def decompile_pex(self, pex_file: Path) -> Optional[Path]:
        """
        Decompile a .pex file to get the source .psc file.
        
        Args:
            pex_file: Path to the .pex file to decompile
            
        Returns:
            Path to the decompiled .psc file, or None if decompilation failed
        """
        if not self.is_available():
            logging.debug("Decompilation not available")
            return None
        
        if not pex_file.exists():
            logging.error(f"PEX file does not exist: {pex_file}")
            return None
        
        try:
            # Create output directory for this decompilation
            output_dir = self.temp_dir / "decompiled"
            output_dir.mkdir(exist_ok=True)
            
            # Run Champollion
            cmd = [
                str(self.champollion_path),
                str(pex_file),
                "--psc",
                str(output_dir)
            ]
            
            logging.debug(f"Running Champollion: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            if result.returncode != 0:
                logging.error(f"Champollion failed for {pex_file.name}: {result.stderr}")
                return None
            
            # Find the decompiled .psc file
            expected_psc = output_dir / f"{pex_file.stem}.psc"
            if expected_psc.exists():
                logging.debug(f"Successfully decompiled {pex_file.name} -> {expected_psc}")
                return expected_psc
            else:
                logging.error(f"Expected decompiled file not found: {expected_psc}")
                return None
                
        except subprocess.TimeoutExpired:
            logging.error(f"Champollion timed out while decompiling {pex_file.name}")
            return None
        except Exception as e:
            logging.error(f"Error decompiling {pex_file.name}: {e}")
            return None
    
    def test_champollion(self) -> bool:
        """
        Test if Champollion is working correctly.
        
        Returns:
            True if Champollion is working, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Run Champollion with --help to test if it's working
            result = subprocess.run(
                [str(self.champollion_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Champollion outputs help text even with non-zero return code
            # Check if the output contains the expected help text
            if "Champollion PEX decompiler" in result.stdout:
                logging.debug("Champollion test successful")
                return True
            else:
                logging.error(f"Champollion test failed - unexpected output: {result.stdout}")
                logging.error(f"Champollion stderr: {result.stderr}")
                return False
                
        except Exception as e:
            logging.error(f"Error testing Champollion: {e}")
            return False
    
    def get_temp_dir(self) -> Optional[Path]:
        """Get the temporary directory used for decompilation."""
        return self.temp_dir