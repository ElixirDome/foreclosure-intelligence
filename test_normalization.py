from app.services.normalization import normalize_address

addresses = [
    "No 5, Somasundaram Mudali Street, Chennai - 600079",
    "NO 5 somasundaram Mudali streeet Chennai 600079",
    "  Sy No 6657/1 - 1824 Sq Ft - No 5 Somasundaram Mudali Street Chennai 600079  ",
]

for address in addresses:
    print("Original :", address)
    print("Normalized:", normalize_address(address))
    print()