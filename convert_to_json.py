import pandas as pd
import sys
from pathlib import Path

def convert_tsv_to_json(input_file, output_file):
    # Read TSV file
    df = pd.read_csv(input_file, sep='\t')
    
    # Convert to JSON and write to file
    df.to_json(output_file, orient='records', force_ascii=False, indent=2)

def process_folder(folder_path):
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"Error: {folder_path} is not a valid directory")
        return

    for tsv_file in folder.glob('*.tsv'):
        json_file = tsv_file.with_suffix('.json')
        print(f"Converting {tsv_file} to {json_file}")
        convert_tsv_to_json(tsv_file, json_file)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    process_folder(folder_path)
    print("Conversion complete")