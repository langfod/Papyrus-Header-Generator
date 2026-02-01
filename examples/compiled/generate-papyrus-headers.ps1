#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Scans Papyrus .psc files for external dependencies and generates headers using papyrus_header_generator.exe

.DESCRIPTION
    This script analyzes .psc files in the Source/Scripts directory to:
    - Find type declarations and function calls
    - Identify types and functions used but not defined in the same file
    - Exclude built-in types (Bool, Float, Int, String)
    - Generate header files using papyrus_header_generator.exe for missing dependencies

.PARAMETER SourcePath
    Path to the directory containing .psc files (default: Source/Scripts)

.PARAMETER BaseDir
    Base directory for Skyrim Special Edition Data (default: "D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data")

.PARAMETER OutputDir
    Output directory for generated headers (default: "headers")

.PARAMETER EnableDecompile
    If specified, enables decompilation of .pex files using Champollion when no .psc source is found

.PARAMETER ChampollionPath
    Path to Champollion.exe or directory containing it (auto-detected if not specified)

.PARAMETER DryRun
    If specified, only shows what commands would be run without executing them

.EXAMPLE
    .\generate-papyrus-headers.ps1
    .\generate-papyrus-headers.ps1 -DryRun
    .\generate-papyrus-headers.ps1 -SourcePath "MyMod\Scripts" -OutputDir "MyHeaders"
    .\generate-papyrus-headers.ps1 -EnableDecompile -ChampollionPath "D:\opt\Champollion-V1.0.1-x64"
#>

param(
    [string]$SourcePath = "Data\Scripts\Source",
    [string]$BaseDir = "D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data",
    [string]$OutputDir = "headers",
    [switch]$EnableDecompile,
    [string]$ChampollionPath = $null,
    [switch]$DryRun
)

# Set up script variables
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$HeaderGenerator = Join-Path $ScriptPath "papyrus_header_generator.exe"
$BuiltInTypes = @("Bool", "Float", "Int", "String")

# Logging function
function Write-Log {
    param($Message, $Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

# Check if required files exist
function Test-Prerequisites {
    if (-not (Test-Path $HeaderGenerator)) {
        Write-Log "ERROR: papyrus_header_generator.exe not found at $HeaderGenerator" "ERROR"
        exit 1
    }
    
    if (-not (Test-Path $SourcePath)) {
        Write-Log "ERROR: Source path $SourcePath not found" "ERROR"
        exit 1
    }
    
    if (-not (Test-Path $BaseDir)) {
        Write-Log "WARNING: Base directory $BaseDir not found. Headers may not generate correctly." "WARN"
    }
}

# Parse a single .psc file for types and function calls
function Get-PapyrusDependencies {
    param([string]$FilePath)
    
    $content = Get-Content $FilePath -Raw
    $definedTypes = @()
    $usedTypes = @()
    $definedFunctions = @()
    $usedFunctions = @()
    $imports = @()
    
    # Papyrus language keywords to exclude
    $papyrusKeywords = @(
        "if", "else", "elseif", "endif", "while", "endwhile", "return", "extends", "as", "new",
        "auto", "autoreadonly", "hidden", "native", "global", "event", "endevent", "function", 
        "endfunction", "property", "endproperty", "import", "scriptname", "state", "endstate",
        "true", "false", "none", "self", "parent", "on"
    )
    
    # Common words that are not types (often come from strings or variable names)
    $nonTypes = @(
        "active", "immediately", "get_dressed", "mainhand", "offhand", "left", "right", "equipped",
        "unequipped", "worn", "carry", "inventory", "chest", "container", "target", "source",
        "destination", "position", "direction", "distance", "speed", "time", "duration",
        "health", "stamina", "magicka", "skill", "level", "experience", "damage", "value",
        "weight", "name", "description", "id", "type", "category", "group", "gender",
        "Cauldron", "Palace", "Hall", "Inn", "Keep", "Stables", "House", "Temple", "College", "Hearth"
    )
    
    # Common Skyrim built-in types and functions to exclude from dependency generation
    $builtInFunctions = @(
        "GetPlayer", "Wait", "Trace", "Notification", "PlayIdle", "GetDisplayName", "GetActorValue",
        "SetActorValue", "GetWornForm", "EquipItem", "UnequipItem", "AddItem", "RemoveItem",
        "IsDead", "IsEquipped", "GetItemCount", "EvaluatePackage", "GetBaseObject"
    )
    
    # Get the scriptname (this file defines this type) and extends clause
    if ($content -match 'Scriptname\s+(\w+)(?:\s+extends\s+(\w+))?') {
        $definedTypes += $matches[1]
        # If there's a parent type from 'extends', add it as a dependency
        if ($matches[2]) {
            $usedTypes += $matches[2]
        }
    }
    
    # Get import statements - these are dependencies we should generate headers for
    $importMatches = [regex]::Matches($content, 'Import\s+(\w+)', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($match in $importMatches) {
        $importName = $match.Groups[1].Value
        $imports += $importName
        # Imports are explicit dependencies
        $usedTypes += $importName
    }
    
    # Get property types
    $propertyMatches = [regex]::Matches($content, '(\w+)\s+Property\s+\w+', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($match in $propertyMatches) {
        $type = $match.Groups[1].Value
        if ($type -notin $BuiltInTypes -and $type -notin $papyrusKeywords -and $type -notin $nonTypes) {
            $usedTypes += $type
        }
    }
    
    # Get function definitions (return types and parameter types)
    $functionMatches = [regex]::Matches($content, '(?:(\w+)\s+)?Function\s+(\w+)\s*\(([^)]*)\)', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($match in $functionMatches) {
        $returnType = $match.Groups[1].Value
        $functionName = $match.Groups[2].Value
        $parameters = $match.Groups[3].Value
        
        $definedFunctions += $functionName
        
        # Add return type if not built-in
        if ($returnType -and $returnType -notin $BuiltInTypes -and $returnType -notin $papyrusKeywords -and $returnType -notin $nonTypes) {
            $usedTypes += $returnType
        }
        
        # Parse parameter types
        if ($parameters) {
            $paramMatches = [regex]::Matches($parameters, '(\w+)\s+\w+', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            foreach ($paramMatch in $paramMatches) {
                $paramType = $paramMatch.Groups[1].Value
                if ($paramType -notin $BuiltInTypes -and $paramType -notin $papyrusKeywords -and $paramType -notin $nonTypes) {
                    $usedTypes += $paramType
                }
            }
        }
    }
    
    # Remove string literals as a simple attempt to avoid false positives from words inside strings
    $contentWithoutStrings = [regex]::Replace($content, '"[^"]*"', '""', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $contentWithoutStrings = [regex]::Replace($contentWithoutStrings, "'[^']*'", "''", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    
    # Get object type references from method calls (Object.Method())
    $objectCallMatches = [regex]::Matches($contentWithoutStrings, '(\w+)\.(\w+)\s*\(', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($match in $objectCallMatches) {
        $objectType = $match.Groups[1].Value
        $methodName = $match.Groups[2].Value
        
        # Special cases for Papyrus built-in objects that don't follow capitalization convention
        $papyrusBuiltInObjects = @("game", "debug", "utility", "math", "ui", "weather")
        
        # Add object type if it looks like a type (starts with uppercase) or is a known Papyrus built-in object
        # and not in exclusion lists
        if (($objectType -cmatch '^[A-Z]' -or $objectType.ToLower() -in $papyrusBuiltInObjects) -and 
            $objectType -notin $BuiltInTypes -and $objectType -notin $papyrusKeywords -and $objectType -notin $nonTypes) {
            $usedTypes += $objectType
        }
    }
    
    # Get variable declarations (Type variableName = ...)
    # More precise regex to avoid matching strings and other false positives
    $varMatches = [regex]::Matches($contentWithoutStrings, '(?:^\s*|\n\s*)(\w+)\s+(\w+)\s*=\s*(?!["''])', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Multiline)
    foreach ($match in $varMatches) {
        $type = $match.Groups[1].Value
        $varName = $match.Groups[2].Value
        
        # Only include if it looks like a type (starts with uppercase), isn't a keyword, and isn't obviously a variable name
        if ($type -cmatch '^[A-Z]' -and $type -notin $BuiltInTypes -and $type -notin $papyrusKeywords -and $type -notin $nonTypes -and $varName -notmatch '^[A-Z]') {
            $usedTypes += $type
        }
    }
    
    # Get type casts (as TypeName)
    $castMatches = [regex]::Matches($content, 'as\s+(\w+)', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    foreach ($match in $castMatches) {
        $type = $match.Groups[1].Value
        if ($type -notin $BuiltInTypes -and $type -notin $papyrusKeywords -and $type -notin $nonTypes) {
            $usedTypes += $type
        }
    }
    
    return @{
        FilePath         = $FilePath
        DefinedTypes     = $definedTypes | Sort-Object -Unique
        UsedTypes        = $usedTypes | Sort-Object -Unique
        DefinedFunctions = $definedFunctions | Sort-Object -Unique
        UsedFunctions    = $usedFunctions | Sort-Object -Unique
        Imports          = $imports | Sort-Object -Unique
    }
}

# Generate headers for a list of patterns
function GenerateHeaders {
    param([array]$Patterns)
    
    if ($Patterns.Count -eq 0) {
        Write-Log "No patterns to generate headers for."
        return
    }
    
    Write-Log "Generating headers for $($Patterns.Count) patterns..."
    
    $patternList = ($Patterns | Sort-Object -Unique) -join ","
    
    # Build command arguments
    $cmdArgs = @(
        "--verbose",
        "--enable-bsa",
        "--base-dir", "`"$BaseDir`"",
        "--output-dir", "`"$OutputDir`"",
        "--patternlist", "`"$patternList`""
    )
    
    # Add decompilation parameters if enabled
    if ($EnableDecompile) {
        $cmdArgs += "--enable-decompile"
        if ($ChampollionPath) {
            $cmdArgs += "--champollion-path", "`"$ChampollionPath`""
        }
    }
    
    $command = "`"$HeaderGenerator`" " + ($cmdArgs -join " ")
    
    if ($DryRun) {
        Write-Log "[DRY RUN] Would execute: $command"
        Write-Log "[DRY RUN] Pattern list: $patternList"
    } else {
        Write-Log "Executing: papyrus_header_generator.py --patternlist with $($Patterns.Count) patterns"
        Write-Log "Pattern list: $patternList"
        if ($EnableDecompile) {
            Write-Log "Decompilation enabled: $EnableDecompile"
            if ($ChampollionPath) {
                Write-Log "Champollion path: $ChampollionPath"
            }
        }
        try {
            # Build argument list for call operator
            $execArgs = @("--verbose", "--enable-bsa", "--base-dir", $BaseDir, "--output-dir", $OutputDir, "--patternlist", $patternList)
            if ($EnableDecompile) {
                $execArgs += "--enable-decompile"
                if ($ChampollionPath) {
                    $execArgs += "--champollion-path"
                    $execArgs += $ChampollionPath
                }
            }
            $result = & "$HeaderGenerator" @execArgs 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Log "SUCCESS: Generated headers for all patterns in batch"
            } else {
                Write-Log "FAILED: Header generation failed with exit code $LASTEXITCODE" "ERROR"
                Write-Log "Output: $result" "ERROR"
            }
        } catch {
            Write-Log "ERROR: Exception running header generator - $($_.Exception.Message)" "ERROR"
        }
    }
}

# Main execution
function Main {
    Write-Log "Starting Papyrus dependency analysis..."
    Write-Log "Source Path: $SourcePath"
    Write-Log "Base Dir: $BaseDir"
    Write-Log "Output Dir: $OutputDir"
    Write-Log "Enable Decompile: $EnableDecompile"
    if ($ChampollionPath) {
        Write-Log "Champollion Path: $ChampollionPath"
    }
    Write-Log "Dry Run: $DryRun"
    
    Test-Prerequisites
    
    # Track all patterns already processed
    $processedPatterns = @()
    $iterationCount = 0
    $maxIterations = 10  # Safety limit to prevent infinite loops
    
    do {
        $iterationCount++
        Write-Log "=== Iteration $iterationCount ==="
        
        $scanPaths = @($SourcePath)
        if ($iterationCount -gt 1) {
            # After first iteration, also scan the headers directory for new dependencies
            if (Test-Path $OutputDir) {
                $scanPaths += $OutputDir
                Write-Log "Including headers directory in scan: $OutputDir"
            }
        }
        
        $allPscFiles = @()
        foreach ($scanPath in $scanPaths) {
            $pscFiles = Get-ChildItem -Path $scanPath -Filter "*.psc" -Recurse
            $allPscFiles += $pscFiles
            Write-Log "Found $($pscFiles.Count) .psc files in $scanPath"
        }
        
        Write-Log "Total files to analyze: $($allPscFiles.Count)"
        
        if ($allPscFiles.Count -eq 0) {
            Write-Log "No .psc files found" "WARN"
            break
        }
        
        $allDependencies = @()
        $allDefinedTypes = @()
        $allDefinedFunctions = @()
        
        foreach ($file in $allPscFiles) {
            Write-Log "Analyzing: $($file.Name)"
            $deps = Get-PapyrusDependencies -FilePath $file.FullName
            $allDependencies += $deps
            $allDefinedTypes += $deps.DefinedTypes
            $allDefinedFunctions += $deps.DefinedFunctions
        }
        
        # Collect all unique types and functions defined in this project + headers
        $projectTypes = $allDefinedTypes | Sort-Object -Unique
        $projectFunctions = $allDefinedFunctions | Sort-Object -Unique
        
        Write-Log "Analysis complete: $($projectTypes.Count) types and $($projectFunctions.Count) functions defined"
        
        # Find external dependencies
        $externalTypes = @()
        
        foreach ($deps in $allDependencies) {
            # Types used but not defined in project + headers
            foreach ($type in $deps.UsedTypes) {
                if ($type -notin $projectTypes -and $type -notin $BuiltInTypes -and $type -notin $externalTypes) {
                    $externalTypes += $type
                }
            }
        }
        
        # Filter out patterns already processed
        $newPatterns = @()
        foreach ($type in $externalTypes) {
            if ($type -notin $processedPatterns) {
                $newPatterns += $type
            }
        }
        
        Write-Log "Found $($externalTypes.Count) total external types, $($newPatterns.Count) are new"
        
        if ($newPatterns.Count -gt 0) {
            Write-Log "New external types found:"
            foreach ($type in $newPatterns | Sort-Object) {
                Write-Log "  - $type"
            }
            
            # Generate headers for new patterns only
            GenerateHeaders -Patterns $newPatterns
            
            # Add new patterns to processed list
            $processedPatterns += $newPatterns
        } else {
            Write-Log "No new external dependencies found. Analysis complete!"
            break
        }
        
        if ($iterationCount -ge $maxIterations) {
            Write-Log "Maximum iterations ($maxIterations) reached. Stopping to prevent infinite loop." "WARN"
            break
        }
        
    } while ($newPatterns.Count -gt 0)
    
    Write-Log "=== Final Summary ==="
    Write-Log "Total iterations: $iterationCount"
    Write-Log "Total patterns processed: $($processedPatterns.Count)"
    Write-Log "All processed patterns:"
    foreach ($pattern in $processedPatterns | Sort-Object) {
        Write-Log "  - $pattern"
    }
    Write-Log "Header generation complete!"
}

Main