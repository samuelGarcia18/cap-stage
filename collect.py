"""Collecte les offres de stage hors France sur les sites carrières.
Connecteurs : Workday, SmartRecruiters, Lever, Greenhouse, Personio, Recruitee.
Pour une entreprise sans connecteur renseigné, le script cherche tout seul le système de recrutement
dans la page carrières ("url") ; s'il n'en trouve pas, l'entreprise est listée dans "manual"."""
import json, re, time, hashlib, datetime, urllib.request, urllib.parse, pathlib
ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "data" / "offres.json"
UA = "Mozilla/5.0 (CapStage veille perso)"
HDR = {"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"}
KW = re.compile(r"\b(intern|internship|stage|stagiaire|praktik\w*|werkstudent|trainee|placement|co-?op|thesis|tesi|tirocinio|becario|pr[aá]cticas|estagi\w*|v\.?i\.?e)\b", re.I)
QUERIES = ["intern", "internship", "stage", "praktikum", "working student", "placement", "trainee"]
ISO = {"de": "Allemagne", "gb": "Royaume-Uni", "uk": "Royaume-Uni", "it": "Italie", "es": "Espagne", "be": "Belgique", "nl": "Pays-Bas",
       "ch": "Suisse", "se": "Suède", "no": "Norvège", "pl": "Pologne", "us": "États-Unis", "ca": "Canada", "br": "Brésil", "in": "Inde",
       "ae": "Émirats arabes unis", "sg": "Singapour", "jp": "Japon", "au": "Australie", "fr": "France", "pt": "Portugal", "fi": "Finlande",
       "dk": "Danemark", "cz": "Tchéquie", "ro": "Roumanie", "tr": "Turquie", "sa": "Arabie saoudite", "mx": "Mexique", "kr": "Corée du Sud"}
EN = {"germany": "Allemagne", "deutschland": "Allemagne", "united kingdom": "Royaume-Uni", "great britain": "Royaume-Uni", "england": "Royaume-Uni",
      "italy": "Italie", "spain": "Espagne", "belgium": "Belgique", "netherlands": "Pays-Bas", "switzerland": "Suisse", "sweden": "Suède",
      "norway": "Norvège", "poland": "Pologne", "united states": "États-Unis", "usa": "États-Unis", "canada": "Canada", "brazil": "Brésil",
      "india": "Inde", "united arab emirates": "Émirats arabes unis", "singapore": "Singapour", "japan": "Japon", "australia": "Australie",
      "france": "France", "portugal": "Portugal", "finland": "Finlande", "denmark": "Danemark", "czech republic": "Tchéquie",
      "romania": "Roumanie", "turkey": "Turquie", "saudi arabia": "Arabie saoudite", "mexico": "Mexique", "south korea": "Corée du Sud"}
FR_CITIES = re.compile(r"\b(france|toulouse|paris|bordeaux|m[ée]rignac|marignane|v[ée]lizy|[ée]lancourt|les mureaux|cannes|issy|gennevilliers|brest|colomiers|blagnac|saint-m[ée]dard|le haillan|malakoff|bourges|satory|roanne|saint-nazaire|guyancourt|bourges|la courneuve|montigny|massy|vernon|le bourget)\b", re.I)

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

def personio(c):
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(f"https://{c['company']}.jobs.personio.de/xml", headers={"User-Agent": UA})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read()); out = []
    for p in root.iter("position"):
        g = lambda t: (p.findtext(t) or "").strip()
        if not (g("employmentType").lower() == "intern" or g("seniority").lower() == "student" or KW.search(g("name"))): continue
        out.append(dict(title=g("name"), city=g("office"), country=country_of("", g("office")), url=f"https://{c['company']}.jobs.personio.de/job/{g('id')}"))
    return out

def recruitee(c):
    return [dict(title=o["title"], city=o.get("city", ""), country=country_of(o.get("country_code") or o.get("country"), o.get("location", "")), url=o["careers_url"])
            for o in http(f"https://{c['company']}.recruitee.com/api/offers/").get("offers", [])
            if KW.search(o["title"]) or "intern" in str(o.get("employment_type_code", "")).lower()]

CONNECTORS = {"workday": workday, "smartrecruiters": smartrecruiters, "lever": lever, "greenhouse": greenhouse, "personio": personio, "recruitee": recruitee}

SIGS = [("workday", re.compile(r"https?://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)", re.I)),
        ("smartrecruiters", re.compile(r"(?:jobs|careers|api)\.smartrecruiters\.com/(?:v1/companies/)?([\w-]+)", re.I)),
        ("greenhouse", re.compile(r"(?:boards|job-boards)(?:-api)?\.greenhouse\.io/(?:v1/boards/|embed/job_board\?for=)?([\w-]+)", re.I)),
        ("lever", re.compile(r"jobs\.lever\.co/([\w-]+)", re.I)),
        ("personio", re.compile(r"([\w-]+)\.jobs\.personio\.(?:de|com)", re.I)),
        ("recruitee", re.compile(r"([\w-]+)\.recruitee\.com", re.I))]
BAD = {"embed", "api", "www", "jobs", "careers", "v1", "boards"}

def detect(url):
    """Cherche, dans la page carrières, un lien vers un système de recrutement connu."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = url + " " + urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    for ats, rx in SIGS:
        for m in rx.finditer(html):
            if ats == "workday":
                return {"ats": ats, "host": f"{m.group(1)}.{m.group(2)}.myworkdayjobs.com", "tenant": m.group(1), "site": m.group(3)}
            if m.group(1).lower() not in BAD:
                return {"ats": ats, "company": m.group(1)}
    return None

def main():
    old = {}
    if OUT.exists():
        try: old = {o["id"]: o for o in json.load(open(OUT, encoding="utf-8"))["offers"]}
        except Exception: pass
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    offers, errors, seen_keys, manual = {}, {}, set(), []
    for c in json.load(open(ROOT / "companies.json", encoding="utf-8")):
        if c.get("ats") not in CONNECTORS:                    # pas de connecteur renseigné : détection automatique
            why = "système de recrutement non détecté (page chargée par JavaScript ou outil maison)"
            try: det = detect(c["url"]) if c.get("url") else None
            except Exception as e: det, why = None, f"page inaccessible ({type(e).__name__})"
            if not det:
                manual.append(dict(name=c["name"], sector=c.get("sector", ""), url=c.get("url", ""), why=why))
                print(f"{c['name']}: à consulter manuellement"); continue
            c = {**c, **det}; print(f"{c['name']}: détecté {c['ats']}")
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
    for oid, o in old.items():                                # une entreprise en erreur garde ses anciennes offres
        if o["company"] in errors and oid not in offers: offers[oid] = o
    data = {"updated": now, "errors": errors, "manual": manual, "offers": sorted(offers.values(), key=lambda o: o["first_seen"], reverse=True)}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(offers)} offres, {len(errors)} entreprises en erreur, {len(manual)} à consulter manuellement")

if __name__ == "__main__":
    main()
