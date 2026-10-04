import requests
from bs4 import BeautifulSoup


URL = "https://www.pnb.bank.in/EAuction.aspx"

session = requests.Session()

# Load listing page
response = session.get(URL, timeout=20)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
form = soup.find("form")

data = {}

for field in form.find_all("input", type="hidden"):
    name = field.get("name")
    if name:
        data[name] = field.get("value", "")

# Click auction row 1
data["__EVENTTARGET"] = (
    "ctl00$ContentPlaceHolder1$rptGrid$ctl01$lbtnTenderTitle"
)
data["__EVENTARGUMENT"] = ""

post_response = session.post(
    URL,
    data=data,
    timeout=20,
)

post_response.raise_for_status()

print("FINAL URL:", post_response.url)
print("BYTES:", len(post_response.content))

auction_soup = BeautifulSoup(post_response.text, "html.parser")

# Search page text for useful auction-related terms
text = auction_soup.get_text(" ", strip=True)

keywords = [
    "Reserve Price",
    "Reserve price",
    "EMD",
    "Auction Date",
    "Auction date",
    "Property",
    "Borrower",
    "Description",
    "Address",
    "Area",
    "Survey",
    "Notice",
    "Download",
]

print("\nMATCHES:\n")

for keyword in keywords:
    position = text.lower().find(keyword.lower())

    if position != -1:
        print("\n---", keyword, "---")
        print(text[max(0, position - 300):position + 1000])

# Look for interesting links
print("\n\nINTERESTING LINKS:\n")

for link in auction_soup.find_all("a", href=True):
    label = link.get_text(" ", strip=True)
    href = link["href"]

    combined = (label + " " + href).lower()

    if any(
        word in combined
        for word in [
            "auction",
            "notice",
            "download",
            "document",
            "view",
            "pdf",
        ]
    ):
        print(label, "=>", href)