import re
from datetime import datetime

from app.schemas import ExtractedProperty

def clean_property_address(
    address: str,
    area_sqft: float | None,
    survey_number: str | None,
) -> str:

    # Remove survey number prefix
    if survey_number:
        address = re.sub(
            rf"\bSy\s+No\s+{re.escape(survey_number)}\s*-\s*",
            "",
            address,
            flags=re.IGNORECASE,
        )

    # Remove area information
    if area_sqft is not None:
        area_number = str(area_sqft).removesuffix(".0")

        address = re.sub(
            rf"\b{re.escape(area_number)}\s*Sq\s*Ft\s*-?\s*",
            "",
            address,
            flags=re.IGNORECASE,
        )

    # Clean up leftover separators
    address = re.sub(r"\s*-\s*", " ", address)
    address = re.sub(r"\s+", " ", address)

    return address.strip()
def extract_properties_from_text(
    text: str,
) -> list[ExtractedProperty]:

    properties = []

    auction_number_match = re.search(
        r"Auction No:\s*(.+)",
        text,
        re.IGNORECASE,
    )

    seller_match = re.search(
        r"Seller:\s*(.+)",
        text,
        re.IGNORECASE,
    )

    auction_start_match = re.search(
        r"Scheduled Auction Start:\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})",
        text,
        re.IGNORECASE,
    )

    auction_close_match = re.search(
        r"Scheduled Auction Close:\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})",
        text,
        re.IGNORECASE,
    )

    auction_number = (
        auction_number_match.group(1).strip()
        if auction_number_match
        else None
    )

    seller_name = (
        seller_match.group(1).strip()
        if seller_match
        else None
    )

    auction_start = None
    if auction_start_match:
        auction_start = datetime.strptime(
            f"{auction_start_match.group(1)} "
            f"{auction_start_match.group(2)}",
            "%d-%m-%y %H:%M",
        )

    auction_close = None
    if auction_close_match:
        auction_close = datetime.strptime(
            f"{auction_close_match.group(1)} "
            f"{auction_close_match.group(2)}",
            "%d-%m-%y %H:%M",
        )

    lot_sections = re.split(
        r"Lot No - Doc No",
        text,
        flags=re.IGNORECASE,
    )

    for section in lot_sections[1:]:

        document_match = re.search(
            r"\s*(\d+/\d+)",
            section,
        )

        if not document_match:
            continue

        document_number = document_match.group(1)

        area_match = re.search(
            r"(\d+(?:\.\d+)?)\s*Sq\s*Ft",
            section,
            re.IGNORECASE,
        )

        opening_bid_match = re.search(
            r"Start Price in INR\s*-\s*([\d.]+)",
            section,
            re.IGNORECASE,
        )

        pre_bid_emd_match = re.search(
            r"PRE BID EMD:\s*([\d.]+)",
            section,
            re.IGNORECASE,
        )

        increment_match = re.search(
            r"Minimum\s+Increment:\s*([\d.]+)",
            section,
            re.IGNORECASE,
        )

        post_emd_match = re.search(
            r"Post Bid EMD %\s*-\s*([\d.]+)",
            section,
            re.IGNORECASE,
        )

        survey_match = re.search(
            r"(?:Sy No|Survey No)\s*:?\s*([0-9/]+)",
            section,
            re.IGNORECASE,
        )

        property_type_match = re.search(
            r"Product Type\s*-\s*(.*?)\n",
            section,
            re.IGNORECASE,
        )

        category_match = re.search(
            r"Category\s*-\s*(.*?)\n",
            section,
            re.IGNORECASE,
        )

        sub_category_match = re.search(
            r"Sub Category\s*-\s*(.*?)\n",
            section,
            re.IGNORECASE,
        )

        defaulter_match = re.search(
            r"Defaulter Name:\s*(.*?)\n",
            section,
            re.IGNORECASE,
        )

        lot_location_match = re.search(
            r"Lot Location\s*-\s*(.*?)(?=\nState\s*:)",
            section,
            re.IGNORECASE | re.DOTALL,
        )

        state_match = re.search(
            r"Lot State\s*-\s*(.*?)(?=\n|$)",
            section,
            re.IGNORECASE,
        )

        address = None

        if lot_location_match:
            address = re.sub(
                r"\s+",
                " ",
                lot_location_match.group(1),
            ).strip()

        pincode = None
        if address:
            pincode_match = re.search(
                r"\b(\d{6})\b",
                address,
            )

            if pincode_match:
                pincode = pincode_match.group(1)

        city = None

        if address:
            city_match = re.search(
                r",\s*([A-Za-z ]+)\s+\d{6}\s*$",
                address,
            )

            if city_match:
                city = city_match.group(1).strip()


            cleaned_address = clean_property_address(
            address=address,
            area_sqft=(
                float(area_match.group(1))
                if area_match
                else None
            ),
            survey_number=(
                survey_match.group(1)
                if survey_match
                else None
            ),
)    
        property_data = ExtractedProperty(
            lot_number=document_number,
            document_number=document_number,

            property_type=(
                property_type_match.group(1).strip()
                if property_type_match
                else None
            ),

            category=(
                category_match.group(1).strip()
                if category_match
                else None
            ),

            sub_category=(
                sub_category_match.group(1).strip()
                if sub_category_match
                else None
            ),

            defaulter_name=(
                defaulter_match.group(1).strip()
                if defaulter_match
                else None
            ),

            address=cleaned_address,
            city=city,

            state=(
                state_match.group(1).strip()
                if state_match
                else None
            ),

            pincode=pincode,

            area_sqft=(
                float(area_match.group(1))
                if area_match
                else None
            ),

            survey_number=(
                survey_match.group(1)
                if survey_match
                else None
            ),

            opening_bid=(
                float(opening_bid_match.group(1))
                if opening_bid_match
                else None
            ),

            pre_bid_emd=(
                float(pre_bid_emd_match.group(1))
                if pre_bid_emd_match
                else None
            ),

            minimum_increment=(
                float(increment_match.group(1))
                if increment_match
                else None
            ),

            post_bid_emd_percent=(
                float(post_emd_match.group(1))
                if post_emd_match
                else None
            ),

            auction_number=auction_number,
            auction_start=auction_start,
            auction_close=auction_close,
            seller_name=seller_name,
        )

        properties.append(property_data)

    return properties