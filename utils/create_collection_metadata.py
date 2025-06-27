#!/usr/bin/env python3
"""
Script to create BO_collections.json metadata file from BO_files.json
Extracts unique collection values and creates metadata following BO_category-names.json structure
"""

import json
import os
from collections import Counter

def main():
    # File paths
    input_file = "../BO_files.json"
    output_file = "../BO_collection-names.json"
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found!")
        return
    
    print(f"Reading {input_file}...")
    
    # Read the BO_files.json
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract all collection values
    collections = []
    for item in data:
        if 'collection' in item and item['collection']:
            collections.append(item['collection'])
    
    # Count occurrences and get unique collections
    collection_counts = Counter(collections)
    unique_collections = sorted(collection_counts.keys())
    
    print(f"Found {len(unique_collections)} unique collections:")
    for collection in unique_collections:
        print(f"  - {collection}: {collection_counts[collection]} files")
    
    # Create the metadata structure following BO_category-names.json format
    # Adding an 'order' field for database sorting
    collections_metadata = []
    
    for order, collection in enumerate(unique_collections, 1):
        collections_metadata.append({
            "collection": collection,
            "displayName": collection
        })
    
    # Write the output file
    print(f"\nWriting {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(collections_metadata, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully created {output_file} with {len(collections_metadata)} collections")
    print("\nGenerated collections metadata:")
    for item in collections_metadata:
        print(f"  {item['collection']} ({collection_counts[item['collection']]} files)")

if __name__ == "__main__":
    main()
