import os
import re
import click
from core.utils import intro, prompt, object
from cifkit.utils import folder

def remove_elements_from_cif_files(cif_dir_path: str) -> None:
    """
    Remove specified elements from CIF files in the given directory.
    """
    intro.prompt_element_intro()
    
    elements_input = click.prompt(
        "Enter the elements to remove, separated by a space (Ex: 'Er Co')",
        type=str,
    ).strip()
    elements_to_remove = [element.strip() for element in elements_input.split() if element.strip()]

    if not elements_to_remove:
        click.echo("No elements specified for removal. Exiting.")
        return

    # Create destination folder
    folder_name = os.path.basename(cif_dir_path)
    elements_str = "_".join(elements_to_remove)
    destination_path = os.path.join(cif_dir_path, f"{folder_name}_Remove_{elements_str}")
    
    # Create the destination directory if it doesn't exist
    os.makedirs(destination_path, exist_ok=True)

    # Get all CIF files in the directory
    cif_files = [f for f in os.listdir(cif_dir_path) if f.endswith('.cif')]
    modified_file_paths = []
    
    click.echo(f"Processing {len(cif_files)} CIF files...")
    click.echo(f"Creating cleaned files in: {destination_path}")
    
    for cif_file in cif_files:
        file_path = os.path.join(cif_dir_path, cif_file)
        destination_file_path = os.path.join(destination_path, cif_file)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Process the CIF file with structure awareness
            original_line_count = len(lines)
            filtered_lines = []
            in_loop = False
            i = 0
            
            while i < len(lines):
                line = lines[i]
                stripped_line = line.strip()
                
                # Check if we're entering a loop section
                if stripped_line == 'loop_':
                    filtered_lines.append(line)
                    in_loop = True
                    i += 1
                    continue
                
                # If we're in a loop section
                if in_loop:
                    # Check if this is a data row in a loop section
                    should_remove = False
                    parts = stripped_line.split()

                    for element in elements_to_remove:
                        # For atom site data: check if line starts with element symbol or contains element as second field
                        if len(parts) >= 2 and (re.match(rf'^{re.escape(element)}(\d+|$)', parts[0]) and not re.search(r'[A-Za-z]', parts[0][1:])):
                            should_remove = True
                            break

                        # For geometry data: check if any atom labels contain the element
                        if len(parts) >= 2:
                            for j in range(min(3, len(parts))):
                                atom_label = parts[j]
                                if re.match(rf'^{re.escape(element)}(\d+|$)', atom_label) and not re.search(r'[A-Za-z]', atom_label[1:]):
                                    should_remove = True
                                    break
                            if should_remove:
                                break

                    if not should_remove:
                        filtered_lines.append(line)
                    else:
                        # Skip the line if it matches the removal criteria
                        pass

                # Handle chemical formula lines
                elif '_chemical_formula_sum' in stripped_line or '_chemical_formula_moiety' in stripped_line:
                    # Update chemical formulas to remove specified elements
                    updated_line = line
                    for element in elements_to_remove:
                        # Remove element and its count (e.g., "Cl6" -> "", "N6" -> "")
                        # Match complete elements only, ensuring no partial matches
                        pattern = rf'(?<![A-Za-z]){re.escape(element)}(\d+|\b)(?![A-Za-z])'
                        updated_line = re.sub(pattern, '', updated_line)
                    
                    # Clean up extra spaces and commas
                    updated_line = re.sub(r',\s*,', ',', updated_line)  # Remove double commas
                    updated_line = re.sub(r"'\s*,\s*'", "'", updated_line)  # Remove empty parts in quotes
                    updated_line = re.sub(r"',\s*'", " ", updated_line)  # Clean up quote separators
                    updated_line = re.sub(r'\s+', ' ', updated_line)  # Normalize spaces
                    
                    filtered_lines.append(updated_line)
                
                # Regular lines - check for geometry sections and atom type sections
                elif any(keyword in stripped_line for keyword in ['_geom_', '_atom_type_symbol']):
                    if in_loop or stripped_line == 'loop_':
                        in_loop = True
                        filtered_lines.append(line)
                    else:
                        # Check if this is a data line with elements to remove
                        should_remove = False
                        for element in elements_to_remove:
                            if stripped_line.startswith(element + ' ') or element in stripped_line.split():
                                should_remove = True
                                break
                        
                        if not should_remove:
                            filtered_lines.append(line)
                
                else:
                    # Regular line, keep it
                    filtered_lines.append(line)
                
                i += 1
            
            # Write the filtered content to the destination file
            with open(destination_file_path, 'w', encoding='utf-8') as f:
                f.writelines(filtered_lines)
            
            # Track files that had elements removed
            if len(filtered_lines) != original_line_count:
                modified_file_paths.append(destination_file_path)
                click.echo(f"Processed: {cif_file} (removed {original_line_count - len(filtered_lines)} lines)")
            else:
                click.echo(f"Copied: {cif_file} (no changes needed)")
        
        except Exception as e:
            click.echo(f"Error processing {cif_file}: {str(e)}")
    
    # Show summary
    click.echo(f"\nSummary: Processed {len(cif_files)} CIF files.")
    click.echo(f"Files with removed elements: {len(modified_file_paths)}")
    click.echo(f"Cleaned files saved to: {destination_path}")
    prompt.print_done_with_option("remove elements from CIF files")


def move_files_based_on_elements(
    cif_dir_path: str,
    is_interactive_mode=True,
    elements: list[str] = None,
    option: int = None,
) -> None:
    """
    Move CIF files based on elements specified by the user, with the option
    to exactly match or contain the elements in the file's composition.
    """

    if is_interactive_mode:
        elements_input = click.prompt(
            "Q1. Enter the elements to filter by, separated by a space (Ex: 'Er Co')",
            type=str,
        ).strip()
        elements = [element for element in elements_input.split() if element]
        elements_str = "_".join(elements)

        # Ask user for the type of filter
        click.echo("\nQ2. Now choose your option:")
        click.echo("[1] Move files exactly matching the elements")
        click.echo("[2] Move files containing at least one of the elements")
        filter_choice = click.prompt("Enter your choice (1 or 2)", type=int)
    else:
        elements_str = "_".join(elements)
        filter_choice = option

    # Folder info
    folder_name = os.path.basename(cif_dir_path)

    if filter_choice == 1:
        filtered_file_paths = ensemble.filter_by_elements_exact_matching(elements)
        destination_path = os.path.join(
            cif_dir_path, f"{folder_name}_exact_{elements_str}"
        )
    else:
        filtered_file_paths = ensemble.filter_by_elements_containing(elements)
        destination_path = os.path.join(
            cif_dir_path, f"{folder_name}_contain_{elements_str}"
        )

    if filtered_file_paths:
        # Move files
        folder.move_files(destination_path, filtered_file_paths)

    # Show summary of files moved
    prompt.print_moved_files_summary(
        filtered_file_paths, ensemble.file_count, destination_path
    )
    prompt.print_done_with_option("filter by elements")
