# Cap Stage – mise en ligne (≈10 min)

1. Créez un dépôt GitHub (public, pour avoir GitHub Pages gratuit) et déposez tout le contenu de ce dossier,
   y compris le dossier caché `.github/`.
2. **Settings → Pages** : Source = *Deploy from a branch*, branche `main`, dossier `/ (root)`. Le site sera sur `https://<pseudo>.github.io/<dépôt>/`.
3. **Settings → Actions → General → Workflow permissions** : cochez *Read and write permissions*.
4. **Actions → Collecte quotidienne → Run workflow** pour la première collecte. Ensuite, elle tourne chaque jour vers 6h UTC.
5. Ouvrez `data/offres.json` : le champ `errors` liste les entreprises dont le connecteur a échoué.

## Ajouter une entreprise (`companies.json`)
- **Workday** (adresse du type `xxx.wd3.myworkdayjobs.com/Site`) : `host` = `xxx.wd3.myworkdayjobs.com`, `tenant` = `xxx`, `site` = `Site`.
- **SmartRecruiters** (`jobs.smartrecruiters.com/Nom`) : `"ats":"smartrecruiters","company":"Nom"`.
- **Lever** (`jobs.lever.co/nom`) ou **Greenhouse** (`boards.greenhouse.io/nom`) : `"ats":"lever"` ou `"greenhouse"`, `"company":"nom"`.
Pour trouver l'outil d'une entreprise : ouvrez son site carrières, cliquez sur une offre et regardez l'adresse.

Airbus et Thales sont vérifiés. Boeing, Lockheed Martin, Northrop Grumman, Textron/Bell et MBDA sont écrits de mémoire : si l'un apparaît dans `errors`, corrigez `host/tenant/site` d'après l'adresse réelle de sa page carrières.
Les entreprises sur un autre système (Safran, Leonardo, Rheinmetall, BAE, Saab, RTX, OHB, ESA…) ne sont pas encore collectées.
