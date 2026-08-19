"""D-53: lookup tables + compiled patterns for core/normalizer.py, split out to stay under 250 lines."""
import re

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
COUNTRY_ALIASES = {
    "uae": "UAE", "u.a.e": "UAE", "united arab emirates": "UAE",
    "ksa": "Saudi Arabia", "saudi": "Saudi Arabia", "saudi arabia": "Saudi Arabia",
    "kingdom of saudi arabia": "Saudi Arabia",
    "egypt": "Egypt", "jordan": "Jordan", "lebanon": "Lebanon", "qatar": "Qatar",
}
ROLE_CITY_COUNTRY = {"Dubai": "UAE", "Abu Dhabi": "UAE", "Riyadh": "Saudi Arabia", "Cairo": "Egypt"}
_LADDER_KEYWORDS = [
    (["manager", "head", "director", "principal", "vp", "vice president", "chief",
      "controller", "counsel", "partner", "architect"], 2.0),
    (["senior", "sr.", "lead"], 1.5),
    (["junior", "intern", "graduate", "entry", "trainee", "fresher", "associate"], 0.0),
    (["specialist", "analyst", "engineer", "executive", "coordinator", "generalist",
      "recruiter", "developer", "marketer", "accountant", "consultant", "representative", "officer"], 1.0),
]
SENIORITY_LADDER = [
    (re.compile(r"(?<!\w)(?:" + "|".join(re.escape(k) for k in kws) + r")(?!\w)"), value)
    for kws, value in _LADDER_KEYWORDS
]
HTML_TAG_RE = re.compile(r"<[^>]+>")
ENCODING_ARTIFACT_RE = re.compile(r"[ÃÂ][-¿]|Ã[©¨ª«]")
YEAR_RANGE_RE = re.compile(r"(\d{4})\s*[‐-―-]\s*(\d{4})")
FREE_TEXT_FIELDS = ["headline", "past_roles", "certifications", "education", "projects", "extra_curriculars"]
NON_ID_FIELDS = FREE_TEXT_FIELDS + ["skills", "experience_years", "location", "notice_period"]
DUP_CONFLICT_FIELDS = ["experience_years", "location", "notice_period", "education", "past_roles", "certifications"]
