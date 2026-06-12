# Compendium Publish Checklist — MUST-Gate vor jedem Push

> Kein Artikel-Push, bevor ALLE drei Blöcke grün sind. Kein „publiziert"-Melden
> ohne kompletten Gate + Live-Verifikation. (Mike-Regel 2026-06-11.)

## 1 · Strukturell (Referenz: lead-scoring / brand-recommendation-share)
- [ ] metastrip vollständig UND konsistent: `Type` passt zu `Term maturity`
      („Consensus concept" nur bei established; hypothesis/emerging → „Practitioner concept")
- [ ] secnav: jeder `href="#…"` hat eine existierende `id` (programmatisch prüfen)
- [ ] Sektionen: Lede · Key takeaways · Konsens-/Operator-Karte · Operational use ·
      Measurement boundary · Distinct from · Obstacles+Resolutions · Common mistakes ·
      Where consensus is missing · Sources · Cite-Box · Cadence · Related terms

## 2 · Inhaltlich
- [ ] Typografie: 1–10 `<strong>` (tragende Aussagen), `<em>` für Kontraste
- [ ] **0 literale Markdown-Reste:** `grep -E '\*[a-zA-Z][^*<>]{1,30}\*'` leer
- [ ] Pre-Flight-Grep: twin / Einzelfälle / Branchen-Anker / KB-Referenzen
- [ ] Epistemik: Claims ↔ maturity-Badges konsistent, kein Overclaiming
- [ ] Zahlen in Beispielen nachgerechnet · Jargon glossiert
- [ ] Quellen: URL mit curl-200 ODER explizite src-internal-Konvention —
      nie „verified" ohne prüfbares Ziel

## 3 · Technisch
- [ ] HTML/JSON/XML parse-valide · JSON-LD valide, Term im DefinedTermSet
- [ ] Relative Links: Ziele existieren · Externe Links: curl-200
- [ ] Domain-Regel (verschärft 2026-06-12): **ALLE** Compendium-URLs — klickbare Links
      UND canonical/og:*/twitter:*/JSON-LD — → `https://insights.rhinegold.de/compendium/…`.
      KEIN `rhinegold.de/compendium` irgendwo im Dokument (Framer-404; ein Canonical
      auf 404 blockiert die Indexierung des Eintrags — Vorfall 2026-06-12).
      Links zur Hauptsite (Logo, /contact, /methodology, /about) bleiben `rhinegold.de`.
- [ ] Verdrahtet: Index-Card (alphabetisch) + JSON-LD + `feed.json` + `compendium/rss.xml`
- [ ] Sitemap regeneriert (nach jedem Artikel-Add/-Edit):
      `cd ~/PycharmProjects/se4b && python -m compendium.build.sitemap ~/PycharmProjects/mapgap/compendium`

## 4 · Erst nach 1–3: Push + Live-Verifikation
- [ ] commit + push
- [ ] Live-URL curl: HTTP 200 + **exakter** Inhalts-Diskriminator (Titel, kein Substring)
- [ ] feed.json same-origin frisch · jsDelivr-Purge (Framer-Embed)

---

## Architektur-Regel: EINE Wahrheit (Mike-Entscheid 2026-06-12)
- **Wahrheit = das HTML in diesem Repo (mapgap).** Was live liegt, gilt.
- Die se4b-Pipeline (`compendium/entries/` + `python -m compendium.build.build`) ist ein
  **Autoren-Werkzeug** — ihr Output wird hierher deployed, danach gilt wieder das HTML.
- **Gate gilt für ALLE Artikel gleich** — hand-geschrieben oder generiert. Standalone:
  `cd ~/PycharmProjects/se4b && python -m compendium.build.qa ~/PycharmProjects/mapgap/compendium [--online]`
- Entries, die hinter dem Live-Stand zurückliegen, NIE blind über Live-HTML syncen.
  Corpus-Slugs ohne Entry (lead-scoring, mql, sql, touchpoints, invisible-shortlist)
  sind in `schema.CORPUS_SLUGS`/`renderer.CORPUS_LABELS` whitelisted und verlinkbar.
