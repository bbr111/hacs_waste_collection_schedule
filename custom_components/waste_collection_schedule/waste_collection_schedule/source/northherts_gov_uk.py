import re
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, cast

import requests
from waste_collection_schedule import Collection

TITLE = "North Herts Council"
DESCRIPTION = "Source for www.north-herts.gov.uk services for North Herts Council."
URL = "https://www.north-herts.gov.uk/"
TEST_CASES = {
    "Example": {
        "address_postcode": "SG4 9QY",
        "address_name_numer": "26",
        "address_street": "BENSLOW RISE",
    },
    "Example No Postcode Space": {
        "address_postcode": "SG49QY",
        "address_name_numer": "26",
        "address_street": "BENSLOW RISE",
    },
    "Example fuzzy matching": {
        "address_postcode": "SG6 4EG",
        "address_name_numer": "4",
        "address_street": "Wilbury Road",
    },
}
ICON_MAP = {
    "Refuse Collection": "mdi:trash-can",
    "Refuse": "mdi:trash-can",
    "Residual Waste": "mdi:trash-can",
    "Mixed Recycling Collection": "mdi:recycle",
    "Mixed Recycling": "mdi:recycle",
    "Dry Recycling": "mdi:recycle",
    "Garden Collection": "mdi:leaf",
    "Garden Waste": "mdi:leaf",
    "Food Collection": "mdi:food-apple",
    "Food Waste": "mdi:food-apple",
    "Paper/Card Collection": "mdi:package-variant",
    "Paper & Card": "mdi:package-variant",
}

_ICON_KEYWORDS = {
    "refuse": "mdi:trash-can",
    "residual": "mdi:trash-can",
    "recycle": "mdi:recycle",
    "recycling": "mdi:recycle",
    "garden": "mdi:leaf",
    "food": "mdi:food-apple",
    "paper": "mdi:package-variant",
    "card": "mdi:package-variant",
}

API_DOMAIN = "https://apps.cloud9technologies.com"
API_BASE = "/citizenmobile/mobileapi"
AUTHORITY = "northherts"
ADDRESSES_PATH = "/addresses"
WASTE_PATH = "/wastecollections"
REQUEST_TIMEOUT = 30

BASIC_TOKEN = "Y2xvdWQ5OmlkQmNWNGJvcjU="
BASE_HEADERS = {
    "Authorization": f"Basic {BASIC_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-api-version": "2",
}

POSTCODE_PATTERN = re.compile(r"([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})", re.IGNORECASE)
ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

Address = dict[str, Any]
JSONDict = dict[str, Any]
ADDRESS_FIELDS = (
    "fullAddress",
    "singleLineAddress",
    "address",
    "addressLine1",
    "addressLine2",
    "addressLine3",
    "town",
    "buildingName",
    "buildingNumber",
    "propertyNumber",
    "street",
    "postcode",
)


def build_headers() -> dict[str, str]:
    return dict(BASE_HEADERS)


def normalise_postcode(text: str | None) -> str | None:
    if not text:
        return None
    match = POSTCODE_PATTERN.search(text)
    if not match:
        return None
    return f"{match.group(1).upper()} {match.group(2).upper()}"


def _address_to_string(address: Address) -> str:
    return " ".join(str(value) for key in ADDRESS_FIELDS for value in [address.get(key)] if value not in (None, "")).strip()


def _clean_type_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned.lower().endswith("collection"):
        cleaned = cleaned[: -len("collection")].strip()
    if cleaned.lower().endswith("bin"):
        cleaned = cleaned[: -len("bin")].strip()
    return cleaned or name


def _icon_for(label: str) -> str | None:
    if label in ICON_MAP:
        return ICON_MAP[label]
    lowered = label.lower()
    for keyword, icon in _ICON_KEYWORDS.items():
        if keyword in lowered:
            return icon
    return None


def _parse_date_string(value: Any) -> date | None:
    """Handle the varied date formats returned by the Cloud 9 API."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    iso_candidate = candidate
    if iso_candidate.endswith("Z"):
        iso_candidate = iso_candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass
    iso_match = ISO_DATE_PATTERN.search(candidate)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(), "%Y-%m-%d").date()
        except ValueError:
            pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _extract_dates(details: dict[str, Any]) -> list[date]:
    """Collect date fields from the different container schemas the API returns."""
    values: list[Any] = [details.get(key) for key in ("collectionDate", "nextCollectionDate", "nextCollection")]
    values.extend(details.get("collectionDates") or [])
    values.extend(
        (
            (entry.get("collectionDate") or entry.get("nextCollectionDate") or entry.get("date"))
            if isinstance(entry, dict)
            else entry
        )
        for entry in details.get("futureCollections") or []
    )
    next_collection = cast(dict[str, Any], details.get("nextCollection") or {})
    values.append(
        next_collection.get("collectionDate") or next_collection.get("nextCollectionDate") or next_collection.get("date")
    )

    return sorted({parsed for parsed in map(_parse_date_string, values) if parsed is not None})


class Source:
    def __init__(
        self,
        address_name_numer: str | None = None,
        address_street: str | None = None,
        street_town: str | None = None,
        address_postcode: str | None = None,
    ):
        self._address_name_numer = address_name_numer
        self._address_street = address_street
        self._street_town = street_town
        self._address_postcode = address_postcode

    def fetch(self) -> list[Collection]:
        headers = build_headers()
        session = requests.Session()

        search_query = self._compose_search_query()
        postcode = normalise_postcode(self._address_postcode)

        addresses = self._lookup_addresses(session, headers, search_query, postcode)
        selected = self._select_address(addresses, search_query, postcode)
        uprn = selected.get("uprn")
        if not uprn:
            raise ValueError("Selected address does not expose a UPRN.")

        payload = self._fetch_waste_collections(session, headers, uprn)
        entries = self._build_collections(payload)
        if not entries:
            raise ValueError("No collection data returned for the selected address.")

        entries.sort(key=lambda item: item.date)
        return entries

    def _compose_search_query(self) -> str:
        parts = [
            self._address_name_numer,
            self._address_street,
            self._street_town,
            self._address_postcode,
        ]
        return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())

    def _lookup_addresses(
        self,
        session: requests.Session,
        headers: dict[str, str],
        query: str,
        postcode: str | None,
    ) -> list[Address]:
        address_line = " ".join(
            part.strip() for part in (self._address_name_numer, self._address_street) if isinstance(part, str) and part.strip()
        )
        url = f"{API_DOMAIN}/{AUTHORITY}{API_BASE}{ADDRESSES_PATH}"
        seen: set[tuple[str, str]] = set()
        attempts: list[tuple[str, str | None]] = [
            ("postcode", postcode),
            ("postcode", self._address_postcode),
            ("address", query),
            ("query", query),
            ("address", address_line),
            ("query", address_line),
            ("query", self._address_street),
        ]
        for param, value in attempts:
            cleaned = (value or "").strip()
            if not cleaned:
                continue
            key = (param, cleaned.lower())
            if key in seen:
                continue
            seen.add(key)
            response = session.get(
                url,
                headers=headers,
                params={param: cleaned},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload_json: JSONDict = response.json()
            addresses_data = payload_json.get("addresses")
            if isinstance(addresses_data, list):
                return addresses_data

        raise ValueError("No matching addresses were returned by the API.")

    def _select_address(
        self,
        addresses: Sequence[Address],
        query: str,
        postcode: str | None,
    ) -> Address:
        """Choose the best candidate using simple scoring heuristics since we need the UPRN."""
        if not addresses:
            raise ValueError("Address lookup returned no results.")

        query_lower = query.lower() if query else ""
        postcode_lower = postcode.lower() if postcode else None

        best_score = -1
        best_address: Address | None = None

        for address in addresses:
            full = _address_to_string(address)
            lowered = full.lower()
            score = 0

            candidate_postcode = normalise_postcode(address.get("postcode"))
            if postcode_lower and candidate_postcode and candidate_postcode.lower() == postcode_lower:
                score += 100
            elif postcode_lower and postcode_lower in lowered:
                score += 60

            if self._address_street and self._address_street.lower() in lowered:
                score += 30

            if self._address_name_numer:
                number = str(self._address_name_numer).strip().lower()
                if re.search(rf"\b{re.escape(number)}\b", lowered):
                    score += 25

            if self._street_town and self._street_town.lower() in lowered:
                score += 15

            if query_lower and query_lower in lowered:
                score += 10

            if score > best_score:
                best_score = score
                best_address = address

        if best_address is None:
            return addresses[0]

        # Guard against poor matches by falling back to the first address if nothing matched above heuristics.
        if best_score <= 0:
            return addresses[0]

        return best_address

    def _fetch_waste_collections(
        self,
        session: requests.Session,
        headers: dict[str, str],
        uprn: str,
    ) -> JSONDict:
        url = f"{API_DOMAIN}/{AUTHORITY}{API_BASE}{WASTE_PATH}/{uprn}"
        response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return cast(JSONDict, response.json())

    def _build_collections(self, payload: JSONDict) -> list[Collection]:
        collection_data = cast(
            JSONDict,
            payload.get("wasteCollectionDates") or payload.get("WasteCollectionDates") or payload,
        )

        entries: list[Collection] = []
        seen: set[tuple[date, str]] = set()

        for key, details in self._collection_items(collection_data):
            if not details:
                continue
            raw_label = (
                details.get("containerDescription") or details.get("containerName") or details.get("collectionType") or key
            )
            if not isinstance(raw_label, str):
                raw_label = str(raw_label)
            label = _clean_type_name(raw_label)
            icon = _icon_for(label)
            for collection_date in _extract_dates(details):
                identifier = (collection_date, label)
                if identifier in seen:
                    continue
                seen.add(identifier)
                entries.append(Collection(date=collection_date, t=label, icon=icon))

        return entries

    @staticmethod
    def _collection_items(
        collection_data: JSONDict,
    ) -> list[tuple[str, dict[str, Any]]]:
        collections_section = cast(dict[str, dict[str, Any]] | None, collection_data.get("collections"))
        if collections_section:
            return list(collections_section.items())
        items: list[tuple[str, dict[str, Any]]] = []
        for key, value in collection_data.items():
            if not key.lower().endswith("collectiondetails"):
                continue
            if isinstance(value, list):
                for idx, entry in enumerate(value, start=1):
                    if entry:
                        items.append((f"{key}_{idx}", cast(dict[str, Any], entry)))
            elif value:
                items.append((key, cast(dict[str, Any], value)))
        return items
