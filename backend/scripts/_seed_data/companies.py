"""Realistic US-trucking & specialty-insurance company name fragments.

Used by ``generators.make_supplier`` to compose 50+ unique-looking legal
names that pattern-match what a real Demo-Specialty MGA's book of business
would contain: retail brokerages, wholesale brokers, MGA partners,
program administrators and a handful of single-state captives.

Every list is *deterministically ordered* — do not rely on alphabetical or
hash-based ordering. Adding entries is fine; removing or reordering breaks
seed determinism for existing entries.
"""

from __future__ import annotations

from typing import Final

NAME_PREFIXES: Final[tuple[str, ...]] = (
    "Alpine", "Beacon", "Cascade", "Cornerstone", "Crossroads",
    "Eagle", "Evergreen", "Frontier", "Granite", "Harbor",
    "Heartland", "Heritage", "Horizon", "Ironclad", "Keystone",
    "Lakeside", "Liberty", "Lighthouse", "Lone Star", "Magnolia",
    "Meridian", "Midwest", "Mountain View", "Northstar", "Oakwood",
    "Pacific", "Pathfinder", "Patriot", "Pinnacle", "Pioneer",
    "Prairie", "Premier", "Redwood", "Reliant", "Ridgeline",
    "Riverbend", "Sentinel", "Silverline", "Skyline", "Southport",
    "Stagecoach", "Stoneridge", "Summit", "Sunbelt", "Thoroughbred",
    "Tidewater", "Trailhead", "Tri-State", "Vanguard", "Vermillion",
    "Watchtower", "Westgate", "Whitetail", "Wilshire", "Wolverine",
    "Yellowstone", "Allegheny", "Bluegrass", "Chesapeake", "Dixie",
)

NAME_CORES: Final[tuple[str, ...]] = (
    "Freight", "Carriers", "Logistics", "Trucking", "Transit",
    "Risk", "Underwriters", "Specialty", "Commercial", "Mutual",
    "Surety", "Brokerage", "Agency", "Programs", "Assurance",
    "Insurance", "Indemnity", "Coverage", "Holdings", "Partners",
    "Capital", "Group", "Advisors", "Solutions", "Services",
    "Markets", "Network", "Alliance", "Standard", "Federal",
)

CORP_SUFFIXES: Final[tuple[str, ...]] = (
    "Insurance Services, Inc.",
    "Insurance Agency, LLC",
    "Underwriters, Inc.",
    "Specialty Risk LLC",
    "Brokerage Group, Inc.",
    "MGA Partners LLC",
    "Risk Solutions, Inc.",
    "Insurance Holdings, LLC",
    "Coverage Group, Inc.",
    "Indemnity Co.",
    "Mutual Insurance Co.",
    "Specialty Programs, LLC",
    "Wholesale, Inc.",
    "& Associates LLC",
)

CITY_STATE_ZIP: Final[tuple[tuple[str, str, str], ...]] = (
    ("Atlanta", "GA", "30303"),
    ("Austin", "TX", "78701"),
    ("Birmingham", "AL", "35203"),
    ("Boise", "ID", "83702"),
    ("Boston", "MA", "02108"),
    ("Charlotte", "NC", "28202"),
    ("Chicago", "IL", "60601"),
    ("Cincinnati", "OH", "45202"),
    ("Cleveland", "OH", "44114"),
    ("Columbus", "OH", "43215"),
    ("Dallas", "TX", "75201"),
    ("Denver", "CO", "80202"),
    ("Des Moines", "IA", "50309"),
    ("Detroit", "MI", "48226"),
    ("Fort Worth", "TX", "76102"),
    ("Houston", "TX", "77002"),
    ("Indianapolis", "IN", "46204"),
    ("Jacksonville", "FL", "32202"),
    ("Kansas City", "MO", "64108"),
    ("Las Vegas", "NV", "89101"),
    ("Los Angeles", "CA", "90014"),
    ("Louisville", "KY", "40202"),
    ("Memphis", "TN", "38103"),
    ("Miami", "FL", "33130"),
    ("Milwaukee", "WI", "53202"),
    ("Minneapolis", "MN", "55401"),
    ("Nashville", "TN", "37203"),
    ("New Orleans", "LA", "70112"),
    ("Oklahoma City", "OK", "73102"),
    ("Omaha", "NE", "68102"),
    ("Orlando", "FL", "32801"),
    ("Philadelphia", "PA", "19103"),
    ("Phoenix", "AZ", "85003"),
    ("Pittsburgh", "PA", "15222"),
    ("Portland", "OR", "97204"),
    ("Raleigh", "NC", "27601"),
    ("Richmond", "VA", "23219"),
    ("Sacramento", "CA", "95814"),
    ("Salt Lake City", "UT", "84111"),
    ("San Antonio", "TX", "78205"),
    ("San Diego", "CA", "92101"),
    ("San Francisco", "CA", "94104"),
    ("Seattle", "WA", "98104"),
    ("St. Louis", "MO", "63102"),
    ("Tampa", "FL", "33602"),
    ("Tucson", "AZ", "85701"),
    ("Tulsa", "OK", "74103"),
    ("Virginia Beach", "VA", "23451"),
    ("Wichita", "KS", "67202"),
    ("Winston-Salem", "NC", "27101"),
)

NAICS_CODES: Final[tuple[str, ...]] = (
    "484121", "484122", "484110", "488510",
    "524210", "524291", "524292", "524298",
)

CONTACT_FIRST_NAMES: Final[tuple[str, ...]] = (
    "Alex", "Avery", "Blake", "Cameron", "Casey", "Dakota", "Devon",
    "Drew", "Elliot", "Emerson", "Finley", "Harper", "Hayden", "Hunter",
    "Jamie", "Jordan", "Kendall", "Logan", "Morgan", "Parker",
    "Peyton", "Quinn", "Reese", "Riley", "Rowan", "Sage", "Skyler",
    "Taylor", "Tyler", "Wren",
)

CONTACT_LAST_NAMES: Final[tuple[str, ...]] = (
    "Anderson", "Bennett", "Carter", "Coleman", "Donovan", "Ellis",
    "Foster", "Garrett", "Hayes", "Iverson", "Johnston", "Kowalski",
    "Lambert", "Mercer", "Norris", "Osborne", "Powell", "Quigley",
    "Reyes", "Sutherland", "Tate", "Underwood", "Vasquez", "Whitaker",
    "Yates", "Zimmerman", "Alvarez", "Brennan", "Caldwell", "Delgado",
)


__all__ = [
    "NAME_PREFIXES", "NAME_CORES", "CORP_SUFFIXES", "CITY_STATE_ZIP",
    "NAICS_CODES", "CONTACT_FIRST_NAMES", "CONTACT_LAST_NAMES",
]
