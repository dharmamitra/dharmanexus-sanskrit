import os
import json
import random
from tqdm import tqdm  # Import tqdm for progress tracking

# Define the directory paths
segments_dir = '../segments/'
samples_dir = '../samples/'

# Ensure the samples directory exists
os.makedirs(samples_dir, exist_ok=True)

# Function to extract category from filename
def get_category(filename):
    return filename.split('_')[1]

# Dictionary to store sentences by category
category_sentences = {}

# Iterate over all files in the segments directory with progress tracking
for filename in tqdm(os.listdir(segments_dir), desc="Processing files"):
    if filename.endswith('.json'):
        category = get_category(filename)
        file_path = os.path.join(segments_dir, filename)
        
        # Read the JSON file
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            # Extract 'original' sentences
            sentences = [segment['original'] for segment in data]
            
            # Add sentences to the category list
            if category not in category_sentences:
                category_sentences[category] = []
            category_sentences[category].extend(sentences)

# Sample 100 sentences from each category and write to a file with progress tracking
for category, sentences in tqdm(category_sentences.items(), desc="Sampling categories"):
    sampled_sentences = random.sample(sentences, min(100, len(sentences)))
    sample_file_path = os.path.join(samples_dir, f'{category}.txt')
    
    with open(sample_file_path, 'w', encoding='utf-8') as sample_file:
        for sentence in sampled_sentences:
            sample_file.write(sentence + '\n')

print("Sampling complete. Check the samples directory for output files.")
