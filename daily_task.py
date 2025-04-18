from crypto_report2 import generate_report, save_report, save_structured_data

if __name__ == "__main__":
    report, structured_data = generate_report()
    save_report(report)
    save_structured_data(structured_data)
    print(f"✅ Daily report generated: {structured_data['date']}")