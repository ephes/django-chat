# Django Chat — New Hero Header (Sandbox Handoff)

## Goal

Selbst-contained Sandbox für den neuen Django-Chat Hero-Header. Erst hier sauber zu Ende bauen, dann migrieren ins Hauptprojekt (`django_chat/templates/cast/django_chat/base.html` + `django_chat/static/django_chat/css/site.css`).

**Entwurf**: `/Users/katha/Desktop/Django-Header-Idee.jpg`
**Repo-Assets**: `frontend/sandbox/assets/` (Django-chat-logo, Headphones SVG, Hero-Hintergrundbild)

## Files

- `frontend/sandbox/new-header.html` — kompletter Sandbox-HTML mit eingebettetem CSS + JS + Tweak-Panel.
- `frontend/sandbox/assets/` — Logo, Headphones, Hero-BG.
- `frontend/sandbox/tweak-snapshot.json` — authoritative Snapshot der Panel-Anchors (extrahiert direkt aus Helium-LevelDB). `singles: {}` ist immer leer, weil keine statischen Slider angefasst wurden.
- `frontend/sandbox/tweak-snapshot.css` — legacy paste-ready CSS-Snippet (historisch, JSON ist der Wahrheits-Stand).

## Aktueller Stand (2026-05-22)

### Komposition

- **Topbar** (`.topbar`): sticky, einreihig, vertikal zentriert. Brand-Slot links (opacity:0 — reserved für Scroll-Morph, Schritt 3). Nav rechts. Auf Tablet+Mobile (≤820 cqw via @container) horizontal zentriert, Brand `display: none`.
- **Hero** (`.hero`): position:relative, padding-block 0 unten clamp(5rem, 14vh, 11rem). min-height anchored via `--tw-hero-min-h`.
- **`.hero__center`**: Grid mit logo-bubble + bubble in derselben grid-cell (z-stacking via DOM order + z-index). Rechts-aligned wenn nötig (über bubble-w-Anchors).
- **`.hero__bubble`**: Flex column, position relative. SVG sitzt absolut dahinter. Content (H1 + Subtitle + Subscribe) flex-zentriert. Padding-block + padding-inline für Insets (% von container-WIDTH, mit aspect-ratio-Compensator × 908/1039 für vertikale Paddings, damit Panel-`%`-Werte als "% der HÖHE" funktionieren).
- **`.hero__logo-bubble`**: position relative, aspect-ratio 442/399, transform translate(--tw-logo-tx, --tw-logo-ty). z-index 60.
- **`.hero__headphones`**: position absolute bottom-right. width / bottom / right alle anchored.
- **LISTEN UP** (`.listen-up`): position absolute bottom: 0 of stage. Fill + Outline mit translate-Y ~5%/-1% (Anschnitt-Effekt unter Viewport-Kante gewollt).
- **Episodes Hook** (`.hero__episodes`): position absolute. Wandert von kleinem Corner-Label (Desktop) zu großem Above-LISTEN-UP-Marker (Mobile) — komplett über Anchors gesteuert, ohne @container-Override.

### Anchor-System (Panel)

Pro Property eine Anchor-Liste mit `(viewport-breakpoint, value, unit)`. Pro Anchor eigene Unit wählbar via Dropdown in der Row. Sum-of-ramps Composer:

```
val₀<unit₀> + Σᵢ (valᵢ<unitᵢ> − valᵢ₋₁<unitᵢ₋₁>) × clamp(0, (100cqw − vwᵢ₋₁px) / spanᵢpx, 1)
```

- Wenn alle Anchors gleiche Unit haben: kompakte Delta-Form.
- Wenn gemischte Units: explizite `(b - a) * ramp` — CSS calc löst mixed-unit deltas zur Laufzeit (z.B. `(50svh - 76vw) * ramp`).
- Pro Property optional min/max bounds (`clamp(MIN, inner, MAX)` oder `min`/`max` wenn nur eines gesetzt).

**Container-Query-basiert**: `.dc-shell` wrappt topbar + hero, hat `container-type: inline-size; container-name: dc`. Alle Anchor-Formeln nutzen `100cqw` statt `100vw` — Header adaptiert auf seine Container-Breite, nicht auf den Viewport. Drop-in in beliebige Layouts möglich.

### 20 anchored Properties

| Property | Defaults | Units |
|---|---|---|
| `--tw-logo-tx` | 4 anchors @ 1920/-160%, 1400/-145%, 820/-60%, 400/-30% | %, rem, vw, svh, vh |
| `--tw-logo-ty` | 4 anchors @ 1400/-6vh, 1024/2vh, 737/4vh, 380/2vh | %, rem, vw, svh, vh |
| `--tw-logo-w` | 4 anchors @ 1920/17vw, 1360/22vw, 820/32vw, 400/20vh; min 9rem max 35rem | vw, rem, %, svh, vh |
| `--tw-bubble-tx` | 1 anchor @ 1024/0% | %, rem, vw, svh, vh |
| `--tw-bubble-ty` | 6 anchors @ 1920/-22%, 1400/-11.25vh, 1024/2.5vh, 820/11vh, 400/15.5vh, 380/12.25vh | %, rem, vw, svh, vh |
| `--tw-bubble-w` | 4 anchors @ 1920/50vw, 1400/59vw, 1024/84%, 600/90%; min 26rem max 56rem | vw, rem, %, svh, vh |
| `--tw-h1` | 3 anchors @ 1920/7rem, 1024/6rem, 400/3.5rem; min 2.5rem max 9rem | rem, em, vw, %, svh, vh |
| `--tw-subtitle` | 2 anchors @ 1920/1.55rem, 400/1.06rem; min 1.06rem max 1.55rem | rem, em, vw, %, svh, vh |
| `--tw-bubble-inset-top` | 3 anchors @ 1920/22%, 1400/24%, 820/12% | %, rem, svh, vh |
| `--tw-hp-w` | 3 anchors @ 1920/30vw, 1024/50vh, 400/26vh; min 5rem max 32rem | vw, rem, %, svh, vh, cqw |
| `--tw-hp-bottom` | 3 anchors @ 1024/13vw, 400/11vw, 380/9vh | vh, svh, rem, %, vw |
| `--tw-hp-right` | 2 anchors @ 1024/0%, 380/2rem | %, rem, vw, cqw |
| `--tw-ep-size` | 3 anchors @ 1920/2.5rem, 1024/4rem, 460/2rem; min 1rem max 7rem | rem, em, vw, %, svh, vh, cqw |
| `--tw-ep-tracking` | 2 anchors @ 1920/0.04em, 820/-0.045em | em, rem, % |
| `--tw-ep-arrow` | 2 anchors @ 1920/0.9em, 1024/1.5rem | em, rem, vw, cqw |
| `--tw-ep-gap` | 1 anchor @ 1024/0.1em | em, rem, % |
| `--tw-ep-right` | 2 anchors @ 1920/1.5rem, 1024/3rem | rem, vw, %, cqw |
| `--tw-ep-bottom` | 2 anchors @ 1920/1.5rem, 820/18vh | rem, vh, svh, %, cqw |
| `--tw-hero-min-h` | 2 anchors @ 820/50rem, 400/0rem; min calc(100svh − var(--tw-topbar-h, 5rem)) | rem, svh, vh, % |
| `--tw-topbar-h` | 2 anchors @ 1920/7rem, 1024/6rem | rem, vh, svh, % |

### Static Single-Sliders (im Panel, kein Anchor-System)

- `--tw-bubble-inset-bottom`: 15% (default)
- `--tw-bubble-inset-x`: 8.5%
- `--tw-sub-size` / `--tw-sub-py` / `--tw-sub-px`: Subscribe-Button (rem)
- `--tw-listen-size`, `--tw-listen-tracking`, `--tw-listen-fill-tx/ty`, `--tw-listen-outline-tx/ty`: LISTEN UP

### Panel-Features

- Pro Anchor-Group: Label + `+`-Button. Pro Anchor-Zeile: `@<vw>px` + Value + Unit-Dropdown + `×`-Button + Slider darunter. Output-Box zeigt das aktuell composte CSS.
- Min/Max-Inputs als freie CSS-Length-Strings (z.B. `calc(100svh - var(--tw-topbar-h, 5rem))`).
- Copy-Button gibt `:root { … }` paste-ready aus (achtung: enthält auch statische Slider-Defaults, die nicht unbedingt angewandt sind — siehe `singles: {}` im Snapshot).
- Reset gibt alle Properties auf die Code-Defaults zurück.
- Resizable Panel (CSS `resize: both`), draggable Header. Position + Größe + Hidden-State werden persistiert (`dc-tweak-pos`, `dc-tweak-size`, `dc-tweak-hidden`).
- Storage-Key: `dc-tweak-v5`. v1–v4 werden beim Laden geräumt.

### Tooling

- Server: `python3 -m http.server 8765` im `frontend/sandbox/` Ordner.
- Playwright-Verify-Skript: `/tmp/dc-shots/devices.js` (deckt iPhone SE, XR, Galaxy S8+, Pixel 7, Surface Duo, iPad Pro, Tablet 768 ab). Output in `/tmp/dc-shots/*.png`. Vor jedem Screenshot wird localStorage geclearet (Code-Defaults werden gerendert).
- **localStorage aus dem Helium-Browser auslesen** (User benutzt Helium, nicht Chrome): `strings -a ~/Library/Application\ Support/net.imput.helium/Default/Local\ Storage/leveldb/*.{log,ldb} 2>/dev/null | grep "dc-tweak-v5" -A0 | tail -1` liefert das letzte JSON.

## Schritte / Offene Punkte

1. **Schritt 1 + 2 (erledigt)**: statisches Layout, responsive Verhalten, Komposition. Alle 20 anchored Properties getunt, Headphones + Episodes promoted.
2. **Schritt 3 (offen) — Scroll-Morph**: Logo + „Django Chat" beim Scrollen aus Hero in die Topbar wandern lassen. Plan: pure CSS via `animation-timeline: scroll(root block)` + `@keyframes logo-morph`. Topbar `.topbar__brand` ist schon als Landing-Slot vorhanden (opacity:0, layout-relevant, links neben Nav).
3. **Schritt 4 (offen) — Maus-Parallax**: Headphones + LISTEN-UP-Layer leicht mit Maus-Position bewegen. Pure CSS möglich via `mouse-tracking` ist nicht standardisiert — vermutlich kleinem JS-Snippet.
4. **Schritt 5 (offen) — Migration ins Hauptprojekt**:
   - Templates: `django_chat/templates/cast/django_chat/base.html` (Topbar + Hero einsetzen, `source_metadata.visible_menu_links` für Nav).
   - CSS: in `site.css` integrieren. Vor Migration `git log -p django_chat/static/django_chat/css/site.css django_chat/templates/cast/django_chat/base.html` checken: User erinnerte sich, dass es früher schon mal ein vergleichbares Mobile-Verhalten gab (Brand unsichtbar, Nav zentriert), Endzustand soll dazu passen.
   - Panel + tweak-snapshot.json bleiben in der Sandbox, fließen NICHT in die Production. Aus dem Panel via Copy oder direkt aus dem Snapshot extrahieren.
   - LevelDB-Backup empfehlen vor Migration, falls User später noch tunen will.

## Wichtige Conventions

- **Niemals eigenmächtig committen/pushen** (siehe `~/.claude/projects/-Users-katha-gitprojects-django-chat/memory/feedback_no_auto_commit.md`).
- User benutzt **Helium-Browser** (Chromium-basiert). localStorage liegt in `~/Library/Application Support/net.imput.helium/Default/Local Storage/leveldb/` (nicht Chrome).
- **CSS first, JS als Fallback/Progressive Enhancement** — siehe `~/.claude/CLAUDE.md` Frontend Principles.
- Für UI-Arbeit: `frontend-design` und `every-layout` Skills proaktiv nutzen, Every-Layout-Primitives (Stack, Cluster, Sidebar, Switcher, Cover, Grid, Frame, Reel, …) vor ad-hoc Media-Queries.
- **Commit-Messages**: nie Selbstreferenzen / "Claude" / „Generated with …". Siehe `~/.claude/CLAUDE.md`.
- Slider-Werte ≠ angewandte Werte: das Panel-Copy gibt ALLE Slider-Defaults aus, auch unangetastete. Die `state.singles`-Map ist die Source of Truth für tatsächlich gesetzte single-slider Werte. Anchor-State ist immer angewandt.
