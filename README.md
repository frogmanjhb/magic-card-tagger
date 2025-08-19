# Magic Card Tagger with CSV Merger

A comprehensive Streamlit application for Magic card management and CSV data processing, featuring an integrated CSV merger tool.

## 🚀 Features

### 🃏 Magic Card Management
- Card data enrichment from Scryfall API
- Price conversion (USD to South African Rands)
- Shopify CSV generation with proper formatting
- Direct Shopify upload via API
- Support for various input formats (text lists, CSV)
- Deckbox collection value calculator
- Price checking and updating tools

### 🔗 CSV Merger (Integrated)
- Multiple file upload support
- Flexible merge strategies (Union, Intersection, Custom mapping)
- Duplicate handling options
- Data validation and preview
- Multiple export formats (CSV, Excel)
- Column conflict resolution

## 📋 Requirements

- Python 3.7+
- Streamlit
- Pandas
- Requests
- Python-dotenv
- BeautifulSoup4
- OpenPyXL (for Excel export)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd magic-card-tagger-1
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables (for Magic Card Tagger):**
   Create a `.env` file in the project root:
   ```env
   SHOPIFY_API_KEY=your_api_key
   SHOPIFY_API_SECRET=your_api_secret
   SHOPIFY_STORE_URL=your_store_url
   ```

## 🚀 Usage

### Launch the Application
```bash
streamlit run magic_card_tagger.py
```

This will open the main application where you can access all features including the integrated CSV Merger.

## 📖 Magic Card Tagger Usage

1. **Input Format:** Upload a text file or CSV with card lists
2. **Data Enrichment:** The app fetches card data from Scryfall
3. **Price Conversion:** USD prices are converted to South African Rands
4. **CSV Generation:** Creates Shopify-compatible CSV files
5. **Upload (Optional):** Direct upload to Shopify via API

### Input Format Examples:
```
4 Lightning Bolt
2 Counterspell
1 Black Lotus
```

## 📊 CSV Merger Usage

1. **Upload Files:** Select multiple CSV files to merge
2. **Configure Options:**
   - **Merge Strategy:** Choose how to handle columns
   - **Duplicate Handling:** Configure duplicate row behavior
   - **File Format:** Set separator and encoding
3. **Merge & Preview:** Review the merged data
4. **Download:** Export as CSV or Excel

### Merge Strategies:
- **Union:** Keep all columns from all files
- **Intersection:** Keep only columns present in all files
- **Custom Mapping:** Use first file as template

## 🔧 Configuration

### Magic Card Tagger
- Scryfall API integration
- Forex API for USD to ZAR conversion
- Shopify API configuration
- Custom column mappings

### CSV Merger
- Configurable separators (comma, semicolon, tab, pipe)
- Multiple encoding support
- Flexible duplicate handling
- Custom merge strategies

## 📁 File Structure

```
magic-card-tagger-1/
├── magic_card_tagger.py    # Main application with integrated CSV Merger
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── logo.png               # Application logo
├── create_demo_csvs.py    # Demo CSV file generator for testing
├── run_magic_tagger.bat   # Windows batch file for easy launching
└── .env                   # Environment variables (create this)
```

## 🐛 Troubleshooting

### Common Issues:

1. **Import Errors:**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`

2. **API Errors:**
   - Check your `.env` file configuration
   - Verify API keys and store URLs

3. **File Upload Issues:**
   - Ensure CSV files are properly formatted
   - Check file encoding (UTF-8 recommended)

4. **Memory Issues:**
   - For large CSV files, consider splitting them before merging
   - Use appropriate merge strategies to reduce memory usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Scryfall API for Magic card data
- Frankfurter API for forex rates
- Shopify API for e-commerce integration
- Streamlit for the web application framework
- Pandas for data manipulation

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the help sections in each application
3. Open an issue on GitHub
4. Check the documentation

---

**Happy coding! 🎉**