import os
import pandas as pd
import re
import ast

def process_segmentnr(x, is_translated):
    if is_translated:
        # For translated files, x is a string representation of a list
        try:
            segmentnr_list = ast.literal_eval(x)
            return str([process_single_segmentnr(item) for item in segmentnr_list])
        except:
            # If parsing fails, treat it as a single string
            return process_single_segmentnr(x)
    else:
        # For segment files, x is a single string
        return process_single_segmentnr(x)

def process_single_segmentnr(x):
    return 'SA_' + re.sub(r'^([A-Z0-9]+)', r'\1_', str(x))

def process_file(file_path, is_translated):
    # Extract file name and check if it contains 'SA_'
    dir_name, file_name = os.path.split(file_path)
    if 'SA_' in file_name:
        print(f"Skipping file containing 'SA_': {file_path}")
        return

    # Generate the new file path
    file_name_without_ext, file_ext = os.path.splitext(file_name)
    new_file_name = process_single_segmentnr(file_name_without_ext) + file_ext
    new_file_path = os.path.join(dir_name, new_file_name)

    # Check if the output file already exists
    if os.path.exists(new_file_path):
        print(f"Skipping: {file_path} (output file already exists)")
        return

    # Print filename before processing
    print(f"Processing: {file_path}")

    # Read the TSV file
    df = pd.read_csv(file_path, sep="\t", on_bad_lines="skip", engine="python")

    # Check if 'segmentnr' column exists
    if 'segmentnr' not in df.columns:
        print(f"Warning: 'segmentnr' column not found in {file_path}")
        return

    # Process the 'segmentnr' column
    df['segmentnr'] = df['segmentnr'].apply(lambda x: process_segmentnr(x, is_translated))

    # Save the modified DataFrame back to a new file
    df.to_csv(new_file_path, sep="\t", index=False)
    print(f"Saved as: {new_file_path}")


def process_folder(folder_path):
    is_translated = folder_path == 'translated'
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.tsv'):
                file_path = os.path.join(root, file)
                process_file(file_path, is_translated)

# Process both folders
folders = ['segments', 'translated']
folders = ['translated']
for folder in folders:
    print(f"Processing folder: {folder}")
    process_folder(folder)

print("All files processed successfully.")
