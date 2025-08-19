"""
Demo CSV Creator

This script creates sample CSV files to test the CSV merger functionality.
"""

import pandas as pd
import os

def create_demo_csvs():
    """Create sample CSV files for testing the merger."""
    
    # Create demo directory if it doesn't exist
    demo_dir = "demo_csvs"
    if not os.path.exists(demo_dir):
        os.makedirs(demo_dir)
    
    # Demo 1: Sales data for Q1
    sales_q1 = pd.DataFrame({
        'Date': ['2024-01-15', '2024-01-20', '2024-02-10', '2024-03-05'],
        'Product': ['Widget A', 'Widget B', 'Widget A', 'Widget C'],
        'Quantity': [10, 5, 8, 12],
        'Revenue': [1000.00, 500.00, 800.00, 1200.00],
        'Region': ['North', 'South', 'North', 'East']
    })
    
    # Demo 2: Sales data for Q2 (different columns)
    sales_q2 = pd.DataFrame({
        'Date': ['2024-04-12', '2024-05-18', '2024-06-22'],
        'Product': ['Widget B', 'Widget D', 'Widget A'],
        'Quantity': [15, 7, 9],
        'Revenue': [1500.00, 700.00, 900.00],
        'Salesperson': ['John', 'Jane', 'Mike']
    })
    
    # Demo 3: Inventory data
    inventory = pd.DataFrame({
        'Product': ['Widget A', 'Widget B', 'Widget C', 'Widget D'],
        'Stock': [100, 50, 75, 25],
        'Category': ['Electronics', 'Electronics', 'Tools', 'Tools'],
        'Supplier': ['Supplier A', 'Supplier B', 'Supplier C', 'Supplier D'],
        'Last_Updated': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01']
    })
    
    # Demo 4: Customer data
    customers = pd.DataFrame({
        'Customer_ID': [1, 2, 3, 4, 5],
        'Name': ['Alice Smith', 'Bob Johnson', 'Carol Davis', 'David Wilson', 'Eva Brown'],
        'Email': ['alice@email.com', 'bob@email.com', 'carol@email.com', 'david@email.com', 'eva@email.com'],
        'Phone': ['555-0101', '555-0102', '555-0103', '555-0104', '555-0105'],
        'Join_Date': ['2023-01-15', '2023-03-20', '2023-06-10', '2023-09-05', '2024-01-10']
    })
    
    # Save all demo files
    files_created = []
    
    sales_q1.to_csv(f"{demo_dir}/sales_q1.csv", index=False)
    files_created.append("sales_q1.csv")
    
    sales_q2.to_csv(f"{demo_dir}/sales_q2.csv", index=False)
    files_created.append("sales_q2.csv")
    
    inventory.to_csv(f"{demo_dir}/inventory.csv", index=False)
    files_created.append("inventory.csv")
    
    customers.to_csv(f"{demo_dir}/customers.csv", index=False)
    files_created.append("customers.csv")
    
    # Create a file with different separator (semicolon)
    sales_q1.to_csv(f"{demo_dir}/sales_q1_semicolon.csv", index=False, sep=';')
    files_created.append("sales_q1_semicolon.csv")
    
    # Create a file with different encoding (latin-1)
    sales_q2.to_csv(f"{demo_dir}/sales_q2_latin.csv", index=False, encoding='latin-1')
    files_created.append("sales_q2_latin.csv")
    
    print("✅ Demo CSV files created successfully!")
    print(f"📁 Files saved in: {demo_dir}/")
    print("\n📋 Files created:")
    for file in files_created:
        print(f"   - {file}")
    
    print("\n🚀 You can now test the CSV Merger with these files!")
    print("   Run: streamlit run csv_merger.py")
    
    return demo_dir

if __name__ == "__main__":
    create_demo_csvs()
