import json
import os
from glob import glob

def validate_catalog(catalog_file, segments_folder):
    # Load the catalog
    with open(catalog_file, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    # Create a set of all new_filename entries
    catalog_filenames = set(entry['filename'] for entry in catalog)

    # Get all files in the segments folder
    segment_files = set(os.path.splitext(os.path.basename(f))[0] for f in glob(os.path.join(segments_folder, '*.tsv')))

    # Check for entries in catalog but not in segments folder
    missing_in_segments = catalog_filenames - segment_files
    if missing_in_segments:
        print(f"Files in catalog but missing in segments folder:")
        for filename in missing_in_segments:
            print(f"  {filename}")
    else:
        print("All catalog entries have corresponding files in the segments folder.")

    # Check for files in segments folder but not in catalog
    missing_in_catalog = segment_files - catalog_filenames
    if missing_in_catalog:
        print(f"\nFiles in segments folder but missing in catalog:")
        for filename in missing_in_catalog:
            print(f"  {filename}")
    else:
        print("\nAll files in the segments folder have corresponding entries in the catalog.")

    # Summary
    print(f"\nSummary:")
    print(f"Total entries in catalog: {len(catalog_filenames)}")
    print(f"Total files in segments folder: {len(segment_files)}")
    print(f"Entries missing in segments folder: {len(missing_in_segments)}")
    print(f"Files missing in catalog: {len(missing_in_catalog)}")

# Usage
catalog_file = 'SA-files.json'
segments_folder = 'segments/'
validate_catalog(catalog_file, segments_folder)