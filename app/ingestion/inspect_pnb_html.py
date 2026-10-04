import requests


url = (
    "https://www.pnb.bank.in/ViewTenderEauction.aspx"
    "?type=Eauction"
    "&tenid=mELirpUhRYksFj7k8/XBcQ=="
    "&fileid=/ZmC6Ak4F1mHNFqwUGjkmA=="
)

response = requests.get(url, timeout=20)
response.raise_for_status()

output_path = "pnb_test_notice.pdf"

with open(output_path, "wb") as file:
    file.write(response.content)

print("STATUS:", response.status_code)
print("CONTENT-TYPE:", response.headers.get("Content-Type"))
print("BYTES:", len(response.content))
print("SAVED:", output_path)
