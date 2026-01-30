# Image to Excel Converter 📸➡️📊

A simple yet powerful Flask web application that converts images of financial documents (like credit card statements or receipts) into organized Excel spreadsheets.

It uses Optical Character Recognition (OCR) to read text from images, intelligently parses the data into columns (Dates, Merchants, Amounts, etc.), and exports it as a downloadable `.xlsx` file.

## ✨ Features

*   **Smart Image Preprocessing:** Automatically cleans, resizes, and sharpens images to improve text recognition accuracy.
*   **Financial Data Parsing:**
    *   Specialized parser for Credit Card Statements (extracts Transaction Date, Posting Date, Merchant, Location, and Amount).
    *   Generic parser fallback for other financial documents.
*   **Excel Export:** Generates formatted Excel files with auto-adjusted column widths.
*   **Simple Web Interface:** Easy drag-and-drop or file selection upload.

## 🛠️ Prerequisites

Before running the app, you need to have the following installed on your system:

1.  **Python 3.8+**
2.  **Tesseract OCR Engine** (Required for the text recognition to work)

    *   **Ubuntu/Debian:**
        ```bash
        sudo apt-get install tesseract-ocr
        ```
    *   **macOS (Homebrew):**
        ```bash
        brew install tesseract
        ```
    *   **Windows:**
        Download the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and add the installation path to your System Environment Variables.

## 🚀 Installation

1.  **Clone the repository** (or download the files):
    ```bash
    git clone <repository-url>
    cd imgtoexcel
    ```

2.  **Create a virtual environment (Optional but recommended):**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 🏃‍♂️ How to Run

1.  **Start the Flask server:**
    ```bash
    python app.py
    ```

2.  **Open the application:**
    Open your web browser and go to: `http://localhost:5000`

3.  **Convert an image:**
    *   Click the upload button to select an image (JPG, PNG).
    *   The app will process the image and automatically download the converted Excel file.

## 📂 Project Structure

*   `app.py`: The main Flask application containing the OCR logic, parsing algorithms, and routes.
*   `templates/index.html`: The frontend HTML interface.
*   `requirements.txt`: List of Python libraries required.
*   `test_parser.py`: (Optional) Script for testing the parsing logic on local images.

## ⚠️ Note on Accuracy

OCR technology is not perfect. The accuracy depends heavily on:
*   **Image Quality:** High resolution and clear scans work best.
*   **Lighting:** Even lighting without shadows is ideal.
*   **Font:** Standard, printed fonts are recognized much better than handwriting.

Always review the generated Excel file for potential errors!
