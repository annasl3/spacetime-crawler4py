import os
from analytics import Analytics, load_stop_words

def main():
    """Generate a text report from saved crawl statistics."""
    if not os.path.isfile("analytics.json"):
        print("analytics.json not found. Run the crawler first.")
        return

    analytics = Analytics()
    stop_words = load_stop_words("stopwords.txt")
    text = analytics.report(stop_words)

    with open("report.txt", "w", encoding="utf-8") as file:
        file.write(text)

    print("Report saved to report.txt")

if __name__ == "__main__":
    main()