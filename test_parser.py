"""
Test script to verify OCR parsing on your credit card statement.
Run this to test the parsing logic without the web interface.
"""

import pytesseract
from PIL import Image
import cv2
import numpy as np
import pandas as pd
import re
import sys
import os

def preprocess_image(image_path):
    """Preprocess image for better OCR accuracy"""
    # Read image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
    
    # Get original dimensions
    height, width = img.shape[:2]
    
    # Resize if image is too small (helps OCR accuracy)
    min_dimension = 1000
    if max(height, width) < min_dimension:
        scale_factor = min_dimension / max(height, width)
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply contrast enhancement
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    
    # Apply mild sharpening
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    # Apply Otsu's thresholding for better binarization
    _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return thresh

def extract_text(image_path):
    """Extract text from image with multiple PSM modes"""
    processed = preprocess_image(image_path)
    temp_path = 'temp_processed.png'
    cv2.imwrite(temp_path, processed)
    
    # Try multiple PSM modes for better results
    texts = []
    psm_modes = [6, 4, 3, 11]  # Different page segmentation modes
    
    for psm in psm_modes:
        custom_config = f'--oem 3 --psm {psm}'
        text = pytesseract.image_to_string(temp_path, config=custom_config)
        if text.strip():
            texts.append(text)
    
    # Combine unique texts
    combined_text = "\n".join(texts)
    
    os.remove(temp_path)
    
    return combined_text

def parse_statement(text):
    """Parse credit card statement with improved logic and duplicate removal"""
    lines = text.split('\n')
    data_rows = []
    seen_transactions = set()  # Track unique transactions to avoid duplicates
    
    # Pattern to match month names followed by day - more flexible
    month_pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[\.\s]*(\d{1,2})\b'
    
    # Pattern to match amounts - handles various formats
    amount_pattern = r'\b\d{1,3}(?:,\d{3})*\.\d{2}\b'
    
    # Alternative amount pattern for OCR errors
    amount_pattern_loose = r'[\d,]+\.\d{2}'
    
    # Known location keywords
    location_keywords = ['cebu', 'manila', 'mandaue', 'liloan', 'vn', 'vietnam', 'city', 'mall', 'park']
    
    # Skip patterns
    skip_patterns = ['installment', 'amortization', 'lawrence', '418898', 'credit-to-cash', 'credit to cash']
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip header/footer lines (case insensitive)
        line_lower = line.lower()
        if any(skip in line_lower for skip in skip_patterns):
            continue
        
        # Clean up common OCR artifacts
        line = re.sub(r'[°""""''`]', '', line)  # Remove degree symbols and quotes
        line = re.sub(r'\s+', ' ', line)  # Normalize whitespace
        line = re.sub(r'\*+', '', line)  # Remove asterisks
        line = re.sub(r'\|+', '', line)  # Remove pipe characters
        
        # Find all dates in the line
        dates_found = re.findall(month_pattern, line, re.IGNORECASE)
        
        # Find all amounts in the line
        amounts_found = re.findall(amount_pattern, line)
        
        # If no strict amounts found, try loose pattern
        if not amounts_found:
            amounts_found = re.findall(amount_pattern_loose, line)
        
        # We need at least one date and one amount to consider this a transaction row
        if len(dates_found) >= 1 and amounts_found:
            row_data = {}
            
            # First date is usually Transaction Date, second is Posting Date
            trans_date = f"{dates_found[0][0]} {dates_found[0][1]}"
            row_data['Transaction Date'] = trans_date
            
            if len(dates_found) >= 2:
                row_data['Posting Date'] = f"{dates_found[1][0]} {dates_found[1][1]}"
            else:
                row_data['Posting Date'] = ''
            
            # Remove dates and amounts from line to get description
            description_line = line
            
            # Remove all dates
            for month, day in dates_found:
                description_line = re.sub(re.escape(f"{month} {day}"), '', description_line, flags=re.IGNORECASE)
                description_line = re.sub(re.escape(f"{month}{day}"), '', description_line, flags=re.IGNORECASE)
            
            # Remove all amounts
            for amount in amounts_found:
                description_line = description_line.replace(amount, '')
            
            # Clean up the description
            description_line = description_line.strip()
            description_line = re.sub(r'^[\)\]\}]+', '', description_line)  # Remove leading brackets
            description_line = re.sub(r'[\(\[\{]+$', '', description_line)  # Remove trailing brackets
            description_line = re.sub(r'\d+', '', description_line)  # Remove stray numbers
            description_line = description_line.strip()
            
            # Try to split description into merchant and location
            parts = [p.strip() for p in description_line.split() if p.strip()]
            
            merchant_parts = []
            location_parts = []
            
            # Look for location keywords
            for part in parts:
                part_lower = part.lower()
                # Skip single characters and very short fragments
                if len(part) <= 1:
                    continue
                is_location = any(keyword in part_lower for keyword in location_keywords)
                
                if is_location:
                    location_parts.append(part)
                else:
                    merchant_parts.append(part)
            
            # If no location found but we have parts, check if last part might be location
            if not location_parts and len(parts) > 2:
                last_part = parts[-1]
                # If last part is short and capitalized, it might be a location
                if len(last_part) < 20 and any(c.isupper() for c in last_part):
                    location_parts = [last_part]
                    merchant_parts = parts[:-1]
                else:
                    merchant_parts = parts
            
            merchant = ' '.join(merchant_parts) if merchant_parts else 'Unknown'
            location = ' '.join(location_parts) if location_parts else ''
            
            # Clean up merchant name (remove common OCR artifacts)
            merchant = re.sub(r'[\(\)\[\]\{\}]', '', merchant)
            merchant = re.sub(r'\s+', ' ', merchant).strip()
            
            row_data['Merchant'] = merchant
            row_data['Location'] = location
            
            # Use the last amount found (usually the transaction amount)
            if amounts_found:
                # Clean up the amount (remove any stray characters)
                amount_clean = re.sub(r'[^\d.,]', '', amounts_found[-1])
                row_data['Amount'] = amount_clean
            
            # Create a unique key for this transaction to detect duplicates
            # Use transaction date, merchant (first 20 chars), and amount
            unique_key = f"{trans_date}_{merchant[:20]}_{amounts_found[-1] if amounts_found else ''}"
            
            if unique_key not in seen_transactions:
                seen_transactions.add(unique_key)
                data_rows.append(row_data)
    
    return data_rows

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_parser.py <image_path>")
        print("Example: python test_parser.py statement.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    print("🔍 Extracting text from image...")
    text = extract_text(image_path)
    
    print("\n📝 Raw OCR Text:")
    print("-" * 80)
    print(text)
    print("-" * 80)
    
    print("\n📊 Parsing financial data...")
    data = parse_statement(text)
    
    if data:
        print(f"\n✅ Found {len(data)} unique transactions:")
        df = pd.DataFrame(data)
        print("\n" + df.to_string(index=False))
        
        # Save to Excel for verification
        output_file = 'test_output.xlsx'
        df.to_excel(output_file, index=False)
        print(f"\n💾 Saved to: {output_file}")
    else:
        print("\n❌ No transactions found. Check the raw text above.")
