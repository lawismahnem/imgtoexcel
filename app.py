from flask import Flask, render_template, request, send_file, jsonify
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pandas as pd
import io
import os
import re
from datetime import datetime
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure upload folder
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

def extract_text_from_image(image_path):
    """Extract text from image using OCR with multiple attempts"""
    # Preprocess image
    processed_img = preprocess_image(image_path)
    
    # Save processed image temporarily
    temp_path = os.path.join(tempfile.gettempdir(), 'processed.png')
    cv2.imwrite(temp_path, processed_img)
    
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
    
    # Also get data with bounding boxes for table structure
    data = pytesseract.image_to_data(temp_path, output_type=pytesseract.Output.DICT)
    
    os.remove(temp_path)
    
    return combined_text, data

def parse_credit_card_statement(text):
    """
    Parse credit card statement format with multiple columns:
    - Transaction Date
    - Posting Date  
    - Merchant/Description
    - Location (optional)
    - Amount
    """
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
    
    # Define headers
    headers = ['Transaction Date', 'Posting Date', 'Merchant', 'Location', 'Amount']
    
    return headers, data_rows

def parse_financial_data(text, ocr_data):
    """
    Main parsing function that tries different parsing strategies
    """
    # First, try the credit card statement parser
    headers, data_rows = parse_credit_card_statement(text)
    
    # If we got good results, use them
    if len(data_rows) > 0:
        return headers, data_rows
    
    # Fallback to generic financial data parser
    lines = text.split('\n')
    
    # Common patterns for financial data
    date_pattern = r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b'
    amount_pattern = r'[\$€£]?\s*\d{1,3}(?:,\d{3})*\.?\d{0,2}|\d+\.\d{2}'
    
    data_rows = []
    headers = []
    
    # Try to identify headers
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check if line looks like a header
        if any(keyword in line.lower() for keyword in ['date', 'description', 'amount', 'total', 'price', 'qty', 'item']):
            if not headers:
                headers = [col.strip() for col in line.split() if col.strip()]
            continue
        
        # Parse data rows
        row_data = {}
        
        # Extract date
        date_match = re.search(date_pattern, line)
        if date_match:
            row_data['Date'] = date_match.group(1)
        
        # Extract amounts
        amounts = re.findall(amount_pattern, line)
        if amounts:
            # Usually the last number is the total
            row_data['Amount'] = amounts[-1].replace('$', '').replace('€', '').replace('£', '').strip()
        
        # Extract description (remaining text)
        description = re.sub(date_pattern, '', line)
        description = re.sub(amount_pattern, '', description)
        description = description.strip()
        if description and len(description) > 2:
            row_data['Description'] = description
        
        if row_data:
            data_rows.append(row_data)
    
    # If no headers detected, create default ones
    if not headers and data_rows:
        headers = list(data_rows[0].keys())
    elif not headers:
        headers = ['Date', 'Description', 'Amount']
    
    return headers, data_rows

def create_excel(headers, data_rows):
    """Create Excel file from parsed data"""
    # Create DataFrame
    df = pd.DataFrame(data_rows)
    
    # Ensure all headers are present
    for header in headers:
        if header not in df.columns:
            df[header] = ''
    
    # Reorder columns to match headers
    df = df[headers]
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Financial Data', index=False)
        
        # Get workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets['Financial Data']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return output

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        # Save uploaded file
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        
        try:
            # Extract text from image
            text, ocr_data = extract_text_from_image(filename)
            
            # Parse financial data
            headers, data_rows = parse_financial_data(text, ocr_data)
            
            # Clean up uploaded file
            os.remove(filename)
            
            if not data_rows:
                return jsonify({
                    'error': 'No financial data detected in image',
                    'raw_text': text
                }), 400
            
            # Create Excel file
            excel_file = create_excel(headers, data_rows)
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'financial_data_{timestamp}.xlsx'
            
            return send_file(
                excel_file,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=output_filename
            )
            
        except Exception as e:
            if os.path.exists(filename):
                os.remove(filename)
            return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)