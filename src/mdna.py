
# --- Nicolas: MD&A extractor development ---
# Code developed with assistance from ChatGPT.

from bs4 import BeautifulSoup
import re

from src.edgar import ticker_to_cik, list_10ks, _get

def find_mdna_start(text, matches):
    detected_starts = []

    for match in matches:
        snippet = text[match.start():match.start() + 500]

        if re.search(
            r"results of operations\s*\.?\s+the following\b",
            snippet,
            re.IGNORECASE
        ):
            detected_starts.append(match.start())

    if len(detected_starts) != 1:
        return None

    return detected_starts[0]

cik, company = ticker_to_cik("CAT")

if cik is None:
    print("Company not found")
else:
    filings = list_10ks(cik, how_many=1)

    if filings:
        print("Company:", company)
        print("10-K URL:", filings[0]["url"])
        response = _get(filings[0]["url"])
        print("Download status:", response.status_code)
        print("Document length:", len(response.text))

        # Convert the HTML filing into readable text
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # Find possible MD&A section headings
        pattern = r"\bitem\s+7\s*[.:\-]?\s*management"

        matches = list(re.finditer(pattern, text, re.IGNORECASE))

        print("Possible MD&A headings:", len(matches))

        for number, match in enumerate(matches, start=1):
            position = match.start()
            print("\nCandidate", number)
            print("Position:", position)
            print(text[position:position + 400])



        # Automatically identify the MD&A heading
        detected_starts = []

        for match in matches:
            snippet = text[match.start():match.start() + 500]

            if re.search(
                r"results of operations\s*\.?\s+the following\b",
                snippet,
                re.IGNORECASE
            ):
                detected_starts.append(match.start())

        if len(detected_starts) != 1:
            print("MD&A not found")
            raise SystemExit

        start = detected_starts[0]
        print("\nAutomatically detected MD&A:", start)

        # Find possible endings of the section
        for label, end_pattern in [
            ("Item 7A", r"\bitem\s+7a\s*[.:\-]?\s*quantitative"),
            ("Item 8", r"\bitem\s+8\s*[.:\-]?\s*financial"),
        ]:
            for match in re.finditer(end_pattern, text, re.IGNORECASE):
                if match.start() > start + 5000:
                    print("\nPossible ending:", label)
                    print("Position:", match.start())
                    print(text[match.start():match.start() + 180])
                    break
        # Find the end of the MD&A section
        
        ending = re.search(
            r"\bitem\s+(?:7a\s*[.:\-]?\s*quantitative|8\s*[.:\-]?\s*financial)",
            text[start + 5000:],
            re.IGNORECASE
        )

        if ending:
            end = start + 5000 + ending.start()
            mdna_text = text[start:end]

            print("\nEXTRACTED MD&A")
            print("Length:", len(mdna_text))
            print("Beginning:", mdna_text[:200])
            print("Ending:", mdna_text[-200:])
        else:
            print("MD&A not found")



    else:
        print("No 10-K found")
