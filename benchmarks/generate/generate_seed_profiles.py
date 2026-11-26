import argparse
import csv
import hashlib
import json
import random
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = uuid.UUID("5ee0d5ee-0000-4000-8000-0000005ee0d5")
BASE_DATE = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)  # fixed: deterministic

# --- vocabulary: every term is (greek, english) --------------------------------------
ARCHETYPES = {
    "food": {
        "sectors": ["food", "food", "food", "retail"],
        "types": {"sme": 0.80, "young_entrepreneur": 0.15, "freelancer": 0.05},
        "names": ["Αρτοποιείο {b}", "Ζαχαροπλαστείο {b}", "Φούρνος {b}", "{b} Bakery",
                  "{b} Pastry House", "{b} Catering"],
        "skills": [("ζαχαροπλαστική", "pastry"), ("ψήσιμο ψωμιού", "baking"),
                   ("υγιεινή τροφίμων", "food safety"), ("τοπικά προϊόντα", "local produce"),
                   ("έλεγχος ποιότητας", "quality control"), ("συσκευασία", "packaging"),
                   ("διαχείριση αποθήκης", "inventory management")],
        "services": [("φρέσκο ψωμί", "fresh bread"), ("γλυκά κατά παραγγελία", "custom cakes"),
                     ("catering εκδηλώσεων", "event catering"),
                     ("διανομή στο σπίτι", "home delivery"), ("χονδρική πώληση", "wholesale"),
                     ("παραδοσιακές συνταγές", "traditional recipes")],
    },
    "agritech": {
        "sectors": ["agritech", "agritech", "agriculture"],
        "types": {"sme": 0.30, "young_entrepreneur": 0.60, "freelancer": 0.10},
        "names": ["{b} AgroTech", "{b} Smart Farming", "Έξυπνη Γεωργία {b}", "{b} Agri Sensors"],
        "skills": [("αισθητήρες IoT", "IoT sensors"), ("ανάλυση δεδομένων", "data analysis"),
                   ("έξυπνη γεωργία", "smart farming"),
                   ("ενσωματωμένα συστήματα", "embedded systems"),
                   ("τηλεπισκόπηση", "remote sensing"), ("μηχανική μάθηση", "machine learning"),
                   ("ανάπτυξη backend", "backend development")],
        "services": [("παρακολούθηση καλλιεργειών", "crop monitoring"),
                     ("συστήματα άρδευσης", "irrigation systems"),
                     ("πρόβλεψη απόδοσης", "yield forecasting"),
                     ("drones ψεκασμού", "spraying drones"),
                     ("πλατφόρμα δεδομένων αγρότη", "farm data platform")],
    },
    "web": {
        "sectors": ["software", "software", "it_services"],
        "types": {"sme": 0.10, "young_entrepreneur": 0.20, "freelancer": 0.70},
        "names": ["{b} Web Studio", "{b} Software", "{b} Dev", "Ιστοσελίδες {b}"],
        "skills": [("ανάπτυξη ιστοσελίδων", "web development"), ("React", "React"),
                   ("Node.js", "Node.js"), ("βάσεις δεδομένων", "databases"),
                   ("εφαρμογές κινητού", "mobile app development"), ("DevOps", "DevOps"),
                   ("ασφάλεια εφαρμογών", "application security")],
        "services": [("κατασκευή ιστοσελίδων", "website development"),
                     ("ηλεκτρονικό κατάστημα", "online store"),
                     ("προσαρμοσμένο λογισμικό", "custom software"),
                     ("συντήρηση ιστοσελίδων", "website maintenance"),
                     ("ενσωμάτωση API", "API integration")],
    },
    "ux": {
        "sectors": ["design", "design", "software"],
        "types": {"sme": 0.05, "young_entrepreneur": 0.15, "freelancer": 0.80},
        "names": ["{b} Design Studio", "{b} UX", "Σχεδιασμός {b}", "{b} Creative"],
        "skills": [("έρευνα χρηστών", "user research"), ("σχεδίαση διεπαφής", "interface design"),
                   ("πρωτότυπα", "prototyping"), ("Figma", "Figma"),
                   ("προσβασιμότητα", "accessibility"), ("οπτική ταυτότητα", "visual identity"),
                   ("γραφιστική", "graphic design")],
        "services": [("σχεδίαση εμπειρίας χρήστη", "UX design"),
                     ("λογότυπο και branding", "logo and branding"),
                     ("πρωτότυπα εφαρμογών", "app prototypes"),
                     ("αξιολόγηση χρηστικότητας", "usability testing")],
    },
    "tourism": {
        "sectors": ["tourism", "tourism", "hospitality"],
        "types": {"sme": 0.80, "young_entrepreneur": 0.10, "freelancer": 0.10},
        "names": ["Ξενώνας {b}", "{b} Tours", "{b} Guesthouse", "Ταξίδια {b}"],
        "skills": [("φιλοξενία", "hospitality"), ("διαχείριση κρατήσεων", "reservation management"),
                   ("ξεναγήσεις", "guided tours"), ("εξυπηρέτηση πελατών", "customer service"),
                   ("ξένες γλώσσες", "foreign languages"),
                   ("διοργάνωση εκδηλώσεων", "event planning")],
        "services": [("ενοικιαζόμενα δωμάτια", "room rentals"),
                     ("τουριστικές εκδρομές", "sightseeing tours"),
                     ("εμπειρίες κρασιού", "wine experiences"),
                     ("μεταφορές επισκεπτών", "guest transfers"),
                     ("διαμονή σε παραδοσιακό ξενώνα", "boutique guesthouse stays")],
    },
    "marketing": {
        "sectors": ["marketing", "marketing", "advertising"],
        "types": {"sme": 0.25, "young_entrepreneur": 0.15, "freelancer": 0.60},
        "names": ["{b} Marketing", "{b} Digital", "Επικοινωνία {b}", "{b} Social"],
        "skills": [("SEO", "SEO"), ("μέσα κοινωνικής δικτύωσης", "social media"),
                   ("copywriting", "copywriting"), ("Google Ads", "Google Ads"),
                   ("email marketing", "email marketing"),
                   ("στρατηγική περιεχομένου", "content strategy"),
                   ("ανάλυση αγοράς", "market analysis")],
        "services": [("διαχείριση social media", "social media management"),
                     ("βελτιστοποίηση SEO", "SEO optimization"),
                     ("διαφημιστικές καμπάνιες", "advertising campaigns"),
                     ("γραφή κειμένων", "content writing"),
                     ("στρατηγική επωνυμίας", "brand strategy")],
    },
    "finance": {
        "sectors": ["finance", "finance", "consulting"],
        "types": {"sme": 0.50, "young_entrepreneur": 0.0, "freelancer": 0.50},
        "names": ["Λογιστικό Γραφείο {b}", "{b} Consulting", "{b} Accounting",
                  "Νομικό Γραφείο {b}"],
        "skills": [("λογιστική", "accounting"), ("φορολογική νομοθεσία", "tax law"),
                   ("συμβάσεις", "contracts"), ("ΦΠΑ", "VAT filing"),
                   ("μισθοδοσία", "payroll"),
                   ("χρηματοδοτικά προγράμματα ΕΣΠΑ", "EU funding programmes"),
                   ("επιχειρηματικό σχέδιο", "business planning")],
        "services": [("τήρηση βιβλίων", "bookkeeping"), ("σύσταση εταιρείας", "company registration"),
                     ("υποβολή φορολογικών δηλώσεων", "tax filing"),
                     ("νομική υποστήριξη", "legal support"),
                     ("συμβουλευτική χρηματοδότησης", "funding consulting")],
    },
    "crafts": {
        "sectors": ["crafts", "crafts", "retail"],
        "types": {"sme": 0.60, "young_entrepreneur": 0.25, "freelancer": 0.15},
        "names": ["Εργαστήριο {b}", "{b} Handmade", "{b} Crafts", "Κεραμικά {b}"],
        "skills": [("κεραμική", "ceramics"), ("χειροποίητα κοσμήματα", "handmade jewelry"),
                   ("ξυλουργική", "woodworking"), ("υφαντική", "weaving"),
                   ("λιανική πώληση", "retail sales"),
                   ("παρουσίαση προϊόντων", "visual merchandising")],
        "services": [("χειροποίητα δώρα", "handmade gifts"),
                     ("εργαστήρια δημιουργίας", "craft workshops"),
                     ("κατασκευές κατά παραγγελία", "custom-made pieces"),
                     ("ηλεκτρονικό κατάστημα χειροτεχνίας", "handicraft e-shop")],
    },
    "logistics": {
        "sectors": ["logistics", "logistics", "transport"],
        "types": {"sme": 0.80, "young_entrepreneur": 0.10, "freelancer": 0.10},
        "names": ["{b} Logistics", "{b} Courier", "Μεταφορές {b}", "{b} Transport"],
        "skills": [("εφοδιαστική αλυσίδα", "supply chain"), ("δρομολόγηση", "route planning"),
                   ("διαχείριση στόλου", "fleet management"),
                   ("τελωνειακές διαδικασίες", "customs procedures"),
                   ("αποθήκευση", "warehousing")],
        "services": [("μεταφορά εμπορευμάτων", "freight transport"),
                     ("ταχυμεταφορές", "courier delivery"),
                     ("αποθηκευτικός χώρος", "storage space"),
                     ("συσκευασία και αποστολή", "packing and shipping")],
    },
    "media": {
        "sectors": ["media", "media", "creative"],
        "types": {"sme": 0.10, "young_entrepreneur": 0.10, "freelancer": 0.80},
        "names": ["{b} Photo", "{b} Films", "Βίντεο {b}", "{b} Studio Photography"],
        "skills": [("φωτογραφία", "photography"), ("μοντάζ βίντεο", "video editing"),
                   ("λήψεις με drone", "drone filming"),
                   ("φωτογραφία προϊόντων", "product photography"), ("σκηνοθεσία", "directing")],
        "services": [("φωτογράφιση εκδηλώσεων", "event photography"),
                     ("διαφημιστικά βίντεο", "promotional videos"),
                     ("φωτογραφία ξενοδοχείων", "hotel photography"),
                     ("εναέρια λήψη", "aerial filming")],
    },
}

# Who needs whom: the real matchmaking signal (a bakery needs web + marketing...).
NEED_LINKS = {
    "food": ["web", "marketing", "logistics"], "agritech": ["web", "ux", "finance"],
    "web": ["marketing", "ux", "finance"], "ux": ["web", "marketing"],
    "tourism": ["web", "media", "marketing"], "marketing": ["media", "web"],
    "finance": ["web", "marketing"], "crafts": ["web", "media", "logistics", "marketing"],
    "logistics": ["web", "finance"], "media": ["marketing", "web"],
}

GENERIC = [("επικοινωνία", "communication"), ("ομαδική εργασία", "teamwork"),
           ("διαχείριση έργων", "project management"), ("δημιουργικότητα", "creativity"),
           ("οργάνωση", "organisation"), ("καινοτομία", "innovation")]

BRANDS = ("Nova Helios Atlas Aegean Olympus Thalassa Kosmos Ariadne Delta Meraki Zephyr Pelagos "
          "Oasis Argo Orion Pegasus Lyra Kalli Iris Elpida Anemos Gaia Selene Hermes Athena Dion "
          "Aeolus Phoebe Nikis Orfeas Kymata Ilios Notos Vorias Amalthia Pindos Navarino Cyclades "
          "Rodon Kritis Nafsika Sparta Delos Mykonos Patmos Lefkada Ithaki Olive Cypress Thyme "
          "Saffron Meltemi Alonissos Pelion Meteora Zagori Mani Chios Lesvos Samos Naxos Paros").split()

REGIONS = [("Attica", 30), ("Central Macedonia", 18), ("Crete", 9), ("Thessaly", 7),
           ("Peloponnese", 7), ("Western Greece", 6), ("Epirus", 4), ("South Aegean", 7),
           ("North Aegean", 3), ("Ionian Islands", 4), ("Eastern Macedonia and Thrace", 3),
           ("Western Macedonia", 2)]

DESC_EL = ["{name}: εξειδικευόμαστε σε {s1} και {s2}. Προσφέρουμε {v1} και {v2}.",
           "Στην {name} προσφέρουμε {v1}, {v2} και υπηρεσίες γύρω από {s1}.",
           "Εμπειρία σε {s1} και {s2}. Οι υπηρεσίες μας: {v1}, {v2}."]
DESC_EN = ["{name} specialises in {s1} and {s2}. We offer {v1} and {v2}.",
           "At {name} we provide {v1}, {v2} and services built around {s1}.",
           "Experienced in {s1} and {s2}. Our services: {v1}, {v2}."]
FILLER_EL = ["Πάνω από πέντε χρόνια εμπειρίας.", "Ευέλικτη συνεργασία με νέες ομάδες.",
             "Ανοιχτοί σε συνεργασίες.", "Εξυπηρετούμε πελάτες σε όλη την Ελλάδα."]
FILLER_EN = ["Over five years of experience.", "Flexible collaboration with new teams.",
             "Open to partnerships.", "We serve clients across Greece."]

NOISE = {"other_term": 0.20, "typo": 0.03, "null_sector": 0.08, "null_region": 0.08,
         "no_needs": 0.10, "no_website": 0.30}


def typo(rng: random.Random, text: str) -> str:
    if len(text) < 6:
        return text
    i = rng.randrange(1, len(text) - 2)
    return text[:i] + text[i + 1] + text[i] + text[i + 2:]


def render(rng: random.Random, term: tuple, mode: str) -> str:
    if mode == "both":
        lang = rng.choice((0, 1))
    else:
        lang = 0 if mode == "el" else 1
    text = term[lang]
    return typo(rng, text) if rng.random() < NOISE["typo"] else text


def pick_terms(rng, key, field, k, mode):
    own = list(ARCHETYPES[key][field])
    rng.shuffle(own)
    out = []
    for term in own[:k]:
        if rng.random() < NOISE["other_term"]:
            if rng.random() < 0.5:
                term = rng.choice(GENERIC)
            else:
                other = rng.choice([a for a in ARCHETYPES if a != key])
                term = rng.choice(ARCHETYPES[other][field])
        out.append(render(rng, term, mode))
    return list(dict.fromkeys(out))  # de-duplicate, keep order


def make_profile(rng, i, key, used_names):
    a = ARCHETYPES[key]
    ptype = rng.choices(list(a["types"]), weights=list(a["types"].values()))[0]
    mode = rng.choices(["el", "en", "both"], weights=[30, 30, 40])[0]
    langs = {"el": ["el"], "en": ["en"], "both": ["el", "en"]}[mode]

    patterns = [p for p in a["names"] if p.isascii()] if mode == "en" else a["names"]
    name = None
    for _ in range(60):
        name = rng.choice(patterns).format(b=rng.choice(BRANDS))
        if name not in used_names:
            break
    else:  # brand pool exhausted for this archetype: disambiguate
        name = f"{name} {rng.randrange(2, 99)}"
    used_names.add(name)

    skills = pick_terms(rng, key, "skills", rng.randint(3, 5), mode)
    services = pick_terms(rng, key, "services", rng.randint(2, 4), mode)

    needs = []
    if rng.random() >= NOISE["no_needs"]:
        for _ in range(rng.randint(1, 3)):
            target = rng.choice(NEED_LINKS[key])
            needs.append(render(rng, rng.choice(ARCHETYPES[target]["services"]), mode))
        needs = list(dict.fromkeys(needs))

    desc_lang = "el" if mode == "el" else "en" if mode == "en" else rng.choice(["el", "en"])
    tpl = rng.choice(DESC_EL if desc_lang == "el" else DESC_EN)
    s = skills + skills  # guard against short lists
    v = services + services
    desc = tpl.format(name=name, s1=s[0], s2=s[1], v1=v[0], v2=v[1])
    if ptype != "freelancer" and rng.random() < 0.6:
        desc += " " + rng.choice(FILLER_EL if desc_lang == "el" else FILLER_EN)
    if rng.random() < 0.15:
        desc = desc.split(".")[0] + "."  # some profiles have one terse line

    sector = None if rng.random() < NOISE["null_sector"] else rng.choice(a["sectors"])
    region = None if rng.random() < NOISE["null_region"] else rng.choices(
        [r for r, _ in REGIONS], weights=[w for _, w in REGIONS])[0]
    website = None
    if rng.random() >= NOISE["no_website"]:
        slug = "".join(c for c in name.lower() if c.isascii() and c.isalnum()) or f"p{i}"
        website = f"https://www.{slug}{i}.gr"

    # Source A serves SMEs and startups, source B serves freelancers. The draw below is
    # kept (and ignored) so the random stream, and therefore every profile, stays the same.
    if ptype == "young_entrepreneur":
        rng.choice(["source_a", "source_b"])
    source = "source_b" if ptype == "freelancer" else "source_a"
    updated = BASE_DATE - timedelta(days=rng.randint(0, 180), minutes=rng.randint(0, 1439))

    return {
        "n": i, "archetype": key, "mode": mode, "id": uuid.uuid5(NAMESPACE, f"profile-{i}"),
        "record_id": uuid.uuid5(NAMESPACE, f"record-{i}"), "source": source, "type": ptype,
        "source_id": f"{'a' if source == 'source_a' else 'b'}-seed-{i}",
        "name": name, "description": desc, "sector": sector, "region": region,
        "skills": skills, "services": services, "needs": needs, "languages": langs,
        "website": website, "updated_at": updated,
    }


# --- SQL output -----------------------------------------------------------------------
def q(value) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def arr(items) -> str:
    inner = ",".join('"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"' for s in items)
    return q("{" + inner + "}")


def batches(rows, size=500):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def write_sql(profiles, path: Path, seed: int):
    out = [f"-- Generated by benchmarks/generate/generate_seed_profiles.py "
           f"(seed={seed}, n={len(profiles)}). Do not edit; re-run the script.",
           "-- Synthetic data. Safe to run repeatedly (ON CONFLICT DO NOTHING).",
           "SET client_encoding = 'UTF8';", "BEGIN;",
           "-- Same rows as 001_dev.sql, so this file also works on its own.",
           "INSERT INTO sources VALUES",
           " ('source_a','http://mock-sources:4000/a','Synthetic SME platform'),",
           " ('source_b','http://mock-sources:4000/b','Synthetic freelancer export')"
           " ON CONFLICT DO NOTHING;"]

    def block(head, rows, tail="ON CONFLICT DO NOTHING;"):
        for chunk in batches(rows):
            out.append(head + "\n " + ",\n ".join(chunk) + "\n" + tail)

    recs = []
    for p in profiles:
        digest = hashlib.sha1(json.dumps(
            [p["name"], p["description"], p["skills"], p["services"], p["needs"]],
            ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        sid = p["source_id"]
        recs.append(f"({q(p['record_id'])},{q(p['source'])},{q(sid)},'{{}}',{q(digest)},"
                    f"{q(digest)},{q('https://example.org/' + p['source'] + '/' + sid)})")
    block("INSERT INTO source_records (id,source,source_id,raw,hash,resolved_hash,original_url) VALUES", recs)

    rows = [f"({q(p['id'])},{q(p['type'])},{q(p['name'])},{q(p['description'])},{q(p['sector'])},"
            f"{q(p['region'])},{arr(p['skills'])},{arr(p['services'])},{arr(p['needs'])},"
            f"{arr(p['languages'])},{q(p['website'])},{q(p['updated_at'].isoformat())})"
            for p in profiles]
    block("INSERT INTO profiles (id,type,name,description,sector,region,skills,services,needs,"
          "languages,website,updated_at) VALUES", rows)

    links = [f"({q(p['record_id'])},{q(p['id'])},'new',1)" for p in profiles]
    block("INSERT INTO profile_sources (source_record_id,profile_id,match_method,confidence) VALUES", links)

    out.append("COMMIT;")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_source_a(p) -> dict:
    """Source A (SME platform): company-style field names, REST/JSON."""
    return {
        "id": p["source_id"], "company_name": p["name"],
        "category": "SME" if p["type"] == "sme" else "Startup",
        "summary": p["description"], "industry": p["sector"], "location": p["region"],
        "capabilities": p["skills"], "products": p["services"], "looking_for": p["needs"],
        "languages": p["languages"], "website": p["website"],
        "profile_url": f"https://example.org/{p['source']}/{p['source_id']}",
        "last_modified": iso(p["updated_at"]),
    }


def to_source_b(p) -> dict:
    """Source B (freelancer export): different names, plus two fields no one should keep.

    hourlyRate and availability are not in the common schema. They exist so Role 3's
    connector proves it stores only allowlisted fields (architecture rule 2).
    Both are derived from the index, not the random stream, so profiles never change.
    """
    n = p["n"]
    return {
        "ref": p["source_id"], "fullName": p["name"], "bio": p["description"],
        "field": p["sector"], "area": p["region"], "expertise": p["skills"],
        "offers": p["services"], "seeking": p["needs"], "speaks": p["languages"],
        "homepage": p["website"],
        "profileLink": f"https://example.org/{p['source']}/{p['source_id']}",
        "modifiedAt": iso(p["updated_at"]),
        "hourlyRate": 20 + (n * 37) % 71,
        "availability": ("full-time", "part-time", "weekends")[n % 3],
    }


def write_sources(profiles, outdir: Path):
    """Fixture files served by services/mock-sources (sorted oldest-first for stable paging)."""
    outdir.mkdir(parents=True, exist_ok=True)
    for source, convert in (("source_a", to_source_a), ("source_b", to_source_b)):
        rows = sorted((p for p in profiles if p["source"] == source),
                      key=lambda p: (p["updated_at"], p["n"]))
        path = outdir / f"{source}.json"
        with path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump([convert(p) for p in rows], f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"wrote {len(rows):>4} records -> {path}")


def write_truth(profiles, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["profile_id", "archetype", "language_mode"])
        for p in profiles:
            w.writerow([p["id"], p["archetype"], p["mode"]])


def main():
    ap = argparse.ArgumentParser(description="Generate the 2,000-profile dev seed and mock-source fixtures.")
    ap.add_argument("--count", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-sql", type=Path, default=ROOT / "db/seeds/002_profiles.sql")
    ap.add_argument("--out-truth", type=Path,
                    default=ROOT / "benchmarks/ground_truth/seed_profiles.csv")
    ap.add_argument("--out-sources", type=Path, default=ROOT / "services/mock-sources/fixtures")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    keys = list(ARCHETYPES)
    used = set()
    # i % 10 gives every archetype exactly count / 10 profiles
    profiles = [make_profile(rng, i, keys[i % len(keys)], used) for i in range(1, args.count + 1)]
    rng.shuffle(profiles)  # so row order does not reveal the archetype

    write_sql(profiles, args.out_sql, args.seed)
    write_truth(profiles, args.out_truth)
    write_sources(profiles, args.out_sources)

    print(f"wrote {len(profiles)} profiles -> {args.out_sql}")
    print(f"wrote ground truth       -> {args.out_truth}")
    print("per archetype:", dict(Counter(p["archetype"] for p in profiles)))
    print("per type     :", dict(Counter(p["type"] for p in profiles)))
    print("per language :", dict(Counter(p["mode"] for p in profiles)))
    print("per source   :", dict(Counter(p["source"] for p in profiles)))


if __name__ == "__main__":
    main()
