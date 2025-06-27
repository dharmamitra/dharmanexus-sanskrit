#!/usr/bin/env python3
"""
Script to harvest metadata from individual JSON files in metadata/ directory
and merge them into SA_files.json
"""

import json
import os
import glob
from pathlib import Path


def load_existing_sa_files(sa_files_path):
    """Load existing SA_files.json content"""
    try:
        with open(sa_files_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validate that we loaded a list
            if not isinstance(data, list):
                print(f"Warning: {sa_files_path} does not contain a list, treating as empty")
                return []
            print(f"✅ Successfully loaded {len(data)} existing entries from {sa_files_path}")
            return data
    except FileNotFoundError:
        print(f"Warning: {sa_files_path} not found, creating new list")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error reading {sa_files_path}: {e}")
        print("❌ ABORTING to prevent data loss!")
        raise
    except Exception as e:
        print(f"❌ Unexpected error reading {sa_files_path}: {e}")
        print("❌ ABORTING to prevent data loss!")
        raise


def load_metadata_files(metadata_dir):
    """Load all metadata JSON files from the metadata directory"""
    metadata_files = glob.glob(os.path.join(metadata_dir, "*-metadata.json"))
    metadata_entries = []
    
    for file_path in metadata_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                metadata_entries.append(metadata)
                print(f"Loaded: {os.path.basename(file_path)}")
        except json.JSONDecodeError as e:
            print(f"Error reading {file_path}: {e}")
        except Exception as e:
            print(f"Unexpected error reading {file_path}: {e}")
    
    return metadata_entries


def convert_metadata_to_sa_format(metadata_entry):
    """Convert metadata entry to SA_files.json format"""
    # Extract the base filename from tsadraCatalogID
    tsadra_id = metadata_entry.get('tsadraCatalogID', '')
    filename = metadata_entry.get('filename', tsadra_id)
    
    # Map metadata fields to SA_files format
    sa_entry = {
        'category': metadata_entry.get('collection', ''),
        'textname': metadata_entry.get('textname', filename),
        'filename': filename,
        'link': metadata_entry.get('itemURL', ''),
        'alt_filename': '',  # Not available in metadata
        'displayName': metadata_entry.get('displayName', ''),
        'filenr': 0,  # Default value
        'collection': metadata_entry.get('collection', ''),
        'new_filename': filename
    }
    
    # Add additional metadata fields that don't exist in original SA_files format
    if 'author' in metadata_entry:
        sa_entry['author'] = metadata_entry['author']
    if 'tags' in metadata_entry:
        sa_entry['tags'] = metadata_entry['tags']
    if 'source' in metadata_entry:
        sa_entry['source'] = metadata_entry['source']
    if 'sourceID' in metadata_entry:
        sa_entry['sourceID'] = metadata_entry['sourceID']
    if 'publicationDate' in metadata_entry:
        sa_entry['publicationDate'] = metadata_entry['publicationDate']
    if 'tsadraCatalogID' in metadata_entry:
        sa_entry['tsadraCatalogID'] = metadata_entry['tsadraCatalogID']
    
    return sa_entry


def merge_metadata_to_sa_files(metadata_dir='metadata', input_sa_files='SA_files.json', output_sa_files='SA_files_updated.json', backup=True):
    """Main function to merge metadata into SA_files.json"""
    
    # Create backup of output file if it exists and backup is requested
    if backup and os.path.exists(output_sa_files):
        backup_path = f"{output_sa_files}.backup"
        print(f"Creating backup of output file: {backup_path}")
        with open(output_sa_files, 'r', encoding='utf-8') as src, \
             open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    # Load existing SA_files.json (INPUT)
    print(f"Loading existing data from {input_sa_files}...")
    sa_entries = load_existing_sa_files(input_sa_files)
    print(f"Found {len(sa_entries)} existing entries")
    
    # Load metadata files
    print(f"Loading metadata files from {metadata_dir}/...")
    metadata_entries = load_metadata_files(metadata_dir)
    print(f"Found {len(metadata_entries)} metadata files")
    
    # Convert and add metadata entries
    print("Converting metadata to SA_files format...")
    new_entries = []
    existing_filenames = {entry.get('filename', '') for entry in sa_entries}
    
    for metadata in metadata_entries:
        sa_entry = convert_metadata_to_sa_format(metadata)
        filename = sa_entry['filename']
        
        # Check if entry already exists
        if filename not in existing_filenames:
            new_entries.append(sa_entry)
            existing_filenames.add(filename)
        else:
            print(f"Skipping duplicate entry: {filename}")
    
    # Merge entries
    all_entries = sa_entries + new_entries
    print(f"Total entries after merge: {len(all_entries)} ({len(new_entries)} new)")
    
    # SAFETY CHECK: Ensure we're not about to write empty data
    if len(sa_entries) > 0 and len(all_entries) == 0:
        raise ValueError("❌ CRITICAL ERROR: About to write empty data when existing entries exist! ABORTING!")
    
    if len(all_entries) < len(sa_entries):
        raise ValueError(f"❌ CRITICAL ERROR: Merged data ({len(all_entries)}) has fewer entries than original ({len(sa_entries)})! ABORTING!")
    
    # Write updated SA_files.json (OUTPUT)
    print(f"Writing merged data to {output_sa_files}...")
    try:
        with open(output_sa_files, 'w', encoding='utf-8') as f:
            json.dump(all_entries, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully wrote {len(all_entries)} entries to {output_sa_files}")
    except Exception as e:
        print(f"❌ Error writing to {output_sa_files}: {e}")
        if backup and os.path.exists(f"{output_sa_files}.backup"):
            print(f"❌ Output file backup available at: {output_sa_files}.backup")
        raise
    
    print("Metadata harvest completed successfully!")
    print(f"📄 Original file: {input_sa_files} (UNCHANGED)")
    print(f"📄 Updated file: {output_sa_files} (with {len(new_entries)} new entries)")
    return len(new_entries)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Harvest metadata and merge into SA_files.json")
    parser.add_argument("--metadata-dir", default="../metadata", 
                       help="Directory containing metadata JSON files (default: metadata)")
    parser.add_argument("--sa-files", default="../SA_files.json",
                       help="Path to INPUT SA_files.json to read from (default: ../SA_files.json)")
    parser.add_argument("--output", default="../SA_files_updated.json",
                       help="Path to OUTPUT file to write merged data (default: ../SA_files_updated.json)")
    parser.add_argument("--no-backup", action="store_true",
                       help="Don't create backup of output file")
    
    args = parser.parse_args()
    
    try:
        new_count = merge_metadata_to_sa_files(
            metadata_dir=args.metadata_dir,
            input_sa_files=args.sa_files,
            output_sa_files=args.output,
            backup=not args.no_backup
        )
        print(f"\n✅ Successfully added {new_count} new entries to {args.output}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)
