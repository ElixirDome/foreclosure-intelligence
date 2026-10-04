from pathlib import Path

from app.ingestion.pnb_source import PNBSourceAdapter


pdf_path = Path("pnb_test_notice.pdf")

source_url = (
    "https://www.pnb.bank.in/ViewTenderEauction.aspx"
    "?type=Eauction"
    "&tenid=mELirpUhRYksFj7k8/XBcQ=="
    "&fileid=/ZmC6Ak4F1mHNFqwUGjkmA=="
)

adapter = PNBSourceAdapter(
    pdf_path=pdf_path,
    source_url=source_url,
)

items = adapter.fetch()

print("FETCHED:", len(items))

property_data = adapter.extract(items[0])

print("\nEXTRACTED PROPERTY")
print("------------------")

for key, value in property_data.items():
    print(f"{key}: {value}")

documents = adapter.get_documents(items[0])

print("\nDOCUMENT")
print("--------")

for key, value in documents[0].items():
    if key == "content":
        print("content:", len(value), "bytes")
    else:
        print(f"{key}: {value}")
        