# Fahrradtouren im Kreis Bergstraße

Mehrseitige, statische Neugestaltung von harsche.com. Die GitHub Pages-Ausgabe liegt in `docs/` und enthält die 28 veröffentlichten WordPress-Seiten, 22 Beiträge, Kategorie- und Monatsarchive sowie Suchfunktion und lokale Medien.

## Neu bauen

```bash
python3 tools/export_wordpress.py
python3 tools/build_site.py
python3 tools/test_site.py
```

GitHub Pages wird aus `main` und dem Ordner `/docs` veröffentlicht. Die Domain `fahrradtouren.online` ist nicht auf dieses Projekt umgestellt.
