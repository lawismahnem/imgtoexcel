# Image to Excel Converter

A Flask web application that converts images of financial documents into Excel spreadsheets using OCR (Optical Character Recognition).

## Features

- **Image Preprocessing**: Automatically cleans and sharpens images for better text recognition
- **Financial Data Parsing**: Extracts dates, merchants, amounts, and other data from credit card statements and receipts
- **Excel Export**: Generates formatted Excel files with auto-adjusted column widths
- **Web Interface**: Simple drag-and-drop file upload

## Prerequisites

1. **Python 3.8 or higher**
2. **Tesseract OCR Engine**

Install Tesseract:
- **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr`
- **macOS:** `brew install tesseract`
- **Windows:** Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and add to System Environment Variables

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd imgtoexcel
   ```

2. Create a virtual environment (optional):
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your browser and go to: `http://localhost:5000`

3. Upload an image (JPG or PNG) to convert it to Excel

## Project Structure

- `app.py`: Main Flask application with OCR logic and routes
- `templates/index.html`: Frontend interface
- `requirements.txt`: Python dependencies
- `test_parser.py`: Optional testing script for parsing logic

## Important Notes

OCR accuracy depends on:
- Image quality (high resolution works best)
- Lighting (even lighting without shadows)
- Font type (standard printed fonts work better than handwriting)

Always review the generated Excel file for potential errors.
