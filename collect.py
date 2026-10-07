"""Collecte les offres de stage hors France sur les sites carrières (Workday, SmartRecruiters, Lever, Greenhouse)."""
import json, re, time, hashlib, datetime, urllib.request, urllib.parse, pathlib
ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "data" / "offres.json"
HDR = {"User-Agent": "Mozilla/5.0 (CapStage veille perso)", "Accept": "application/json", "Content-Type": "application/json"}
KW = re.compile(r"\b(intern|internship|stage|stagiaire|praktik\w*|werkstudent|trainee|placement|co-?op|thesis|tesi|tirocinio|becario|pr[aá]cticas|estagi\w*)\b", re.I)
QUERIES = ["intern", "internship", "stage", "praktikum", "working student", "placement", "trainee"]
ISO = {"de": "Allemagne", "gb": "Royaume-Uni", "uk": "Royaume-Uni", "it": "Italie", "es": "Espagne", "be": "Belgique", "nl": "Pays-Bas",
       "ch": "Suisse", "se": "Suède", "no": "Norvège", "pl": "Pologne", "us": "États-Unis", "ca": "Canada", "br": "Brésil", "in": "Inde",
       "ae": "Émirats arabes unis", "sg": "Singapour", "jp": "Japon", "au": "Australie", "fr": "France", "pt": "Portugal", "fi": "Finlande",
       "dk": "Danemark", "cz": "Tchéquie", "ro": "Roumanie", "tr": "Turquie", "sa": "Arabie saoudite", "mx": "Mexique", "kr": "Corée du Sud"}
EN = {"germany": "Allemagne", "united kingdom": "Royaume-Uni", "great britain": "Royaume-Uni", "italy": "Italie", "spain": "Espagne", "belgium": "Belgique",
      "netherlands": "Pays-Bas", "switzerland": "Suisse", "sweden": "Suède", "norway": "Norvège", "poland": "Pologne", "united states": "États-Unis",
      "usa": "États-Unis", "canada": "Canada", "brazil": "Brésil", "india": "Inde", "united arab emirates": "Émirats arabes unis", "singapore": "Singapour",
      "japan": "Japon", "australia": "Australie", "france": "France", "portugal": "Portugal", "finland": "Finlande", "denmark": "Danemark",
      "czech republic": "Tchéquie", "romania": "Roumanie", "turkey": "Turquie", "saudi arabia": "Arabie saoudite", "mexico": "Mexique", "south korea": "Corée du Sud"}
FR_CITIES = re.compile(r"\b(france|toulouse|paris|bordeaux|m[ée]rignac|marignane|v[ée]lizy|[ée]lancourt|les mureaux|cannes|issy|gennevilliers|brest|colomiers|blagnac|saint-m[ée]dard|le haillan)\b", re.I)

def http(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def country_of(raw, text=""):
    raw = (raw or "").strip()
    if raw.lower() in ISO: return ISO[raw.lower()]
    if raw.lower() in EN: return EN[raw.lower()]
    if raw: return raw
    for k, v in EN.items():
        if re.search(r"\b" + re.escape(k) + r"\b", text, re.I): return v
    return "France" if FR_CITIES.search(text) else "À préciser"

def workday(c):
    base = f"https://{c['host']}"; api = f"{base}/wday/cxs/{c['tenant']}/{c['site']}"; seen, out = set(), []
    for q in QUERIES:
        off = 0
        while off < 200:
            d = http(api + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": off, "searchText": q})
            ps = d.get("jobPostings", [])
            if not ps: break
            for p in ps:
                path = p["externalPath"]
                if path in seen or not KW.search(p["title"]): continue
                seen.add(path)
                try: det = http(api + path).get("jobPostingInfo", {})
                except Exception: det = {}
                loc = det.get("location") or p.get("locationsText", "")
                out.append(dict(title=p["title"], city=loc, country=country_of((det.get("country") or {}).get("descriptor"), loc),
                                url=det.get("externalUrl") or f"{base}/{c['site']}{path}"))
                time.sleep(.2)
            off += 20
            if off >= d.get("total", 0): break
    return out

def smartrecruiters(c):
    seen, out = set(), []
    for q in QUERIES[:4]:
        d = http(f"https://api.smartrecruiters.com/v1/companies/{c['company']}/postings?limit=100&q={urllib.parse.quote(q)}")
        for p in d.get("content", []):
            if p["id"] in seen: continue
            seen.add(p["id"]); loc = p.get("location", {})
            if not (KW.search(p["name"]) or "intern" in (p.get("typeOfEmployment", {}).get("label", "")).lower()): continue
            out.append(dict(title=p["name"], city=loc.get("city", ""), country=country_of(loc.get("country")),
                            url=f"https://jobs.smartrecruiters.com/{c['company']}/{p['id']}"))
    return out

def lever(c):
    return [dict(title=p["text"], city=p["categories"].get("location", ""), country=country_of(p.get("country"), p["categories"].get("location", "")), url=p["hostedUrl"])
            for p in http(f"https://api.lever.co/v0/postings/{c['company']}?mode=json") if KW.search(p["text"])]

def greenhouse(c):
    return [dict(title=p["title"], city=p["location"]["name"], country=country_of("", p["location"]["name"]), url=p["absolute_url"])
            for p in http(f"https://boards-api.greenhouse.io/v1/boards/{c['company']}/jobs").get("jobs", []) if KW.search(p["title"])]

CONNECTORS = {"workday": workday, "smartrecruiters": smartrecruiters, "lever": lever, "greenhouse": greenhouse}

def main():
    old = {}
    if OUT.exists():
        try: old = {o["id"]: o for o in json.load(open(OUT, encoding="utf-8"))["offers"]}
        except Exception: pass
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    offers, errors, seen_keys = {}, {}, set()
    for c in json.load(open(ROOT / "companies.json", encoding="utf-8")):
        try: found = CONNECTORS[c["ats"]](c)
        except Exception as e:
            errors[c["name"]] = f"{type(e).__name__}: {e}" + ("" if c.get("verified") else " (connecteur non vérifié : contrôlez host/tenant/site)")
            continue
        for o in found:
            if o["country"] == "France": continue            # hors France uniquement
            key = (c["name"], re.sub(r"\W", "", o["title"].lower()), re.sub(r"\W", "", o["city"].lower()))
            if key in seen_keys: continue                     # doublon
            seen_keys.add(key)
            oid = hashlib.sha1(f"{c['name']}{o['url']}".encode()).hexdigest()[:12]
            offers[oid] = dict(id=oid, company=c["name"], sector=c["sector"], source="Site entreprise", first_seen=old.get(oid, {}).get("first_seen", now), **o)
        print(f"{c['name']}: {sum(1 for x in offers.values() if x['company']==c['name'])} offres")
    # une entreprise en erreur garde ses anciennes offres
    for oid, o in old.items():
        if o["company"] in errors and oid not in offers: offers[oid] = o
    data = {"updated": now, "errors": errors, "offers": sorted(offers.values(), key=lambda o: o["first_seen"], reverse=True)}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(offers)} offres, {len(errors)} entreprises en erreur")

if __name__ == "__main__":
    main()
