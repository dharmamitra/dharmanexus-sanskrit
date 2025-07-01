import json

def fix_categories():
    # Load the JSON file
    with open('../SA_files.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    fixed_count = 0
    
    # Process each entry
    for entry in data:
        # Check if category equals collection
        if entry.get('category') == entry.get('collection'):
            # Extract category from filename by splitting on '_' and taking index 1
            filename = entry.get('filename', '')
            if filename.startswith('SA_'):
                parts = filename.split('_')
                if len(parts) > 1:
                    new_category = parts[1]
                    print(f"Fixing entry: {filename}")
                    print(f"  Old category: {entry['category']}")
                    print(f"  New category: {new_category}")
                    entry['category'] = new_category
                    fixed_count += 1
    
    print(f"\nFixed {fixed_count} entries")
    
    # Save the updated JSON file
    with open('SA_files.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Updated SA_files.json saved")

if __name__ == "__main__":
    fix_categories()
