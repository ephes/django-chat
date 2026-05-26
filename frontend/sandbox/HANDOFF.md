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

## Aktueller Stand (2026-05-26)

### Komposition

- **Topbar** (`.topbar`): sticky. Auf Desktop (>1200 cqw) einreihig, vertikal zentriert: Brand-Slot links (Landeplatz des Scroll-Morphs, statisch `opacity:0` — der @supports-Block oder der JS-Polyfill promotet ihn auf opacity:1), Nav rechts. Auf Tablet/Mobile (≤1200 cqw via @container) zweireihig (`flex-direction: column`): Nav oben, Brand-Slot zentriert darunter. Brand bleibt überall im Flow (kein `display: none`), Morph läuft auf jedem Viewport.
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
| `--tw-logo-tx` | **Nur in Mobile-Range (≤1200 cqw)**. 4 anchors @ 1920/-159.5%, 1400/-145%, 820/-60%, 400/-30%. Auf Desktop (>1200 cqw) wird das Logo via reiner CSS-calc-Formel positioniert (siehe `.hero__logo-bubble` `@container`-Rule). Die wide-Anchors (1400, 1920) bleiben als no-@container CSS-Fallback. | %, rem, vw, svh, vh |
| `--tw-logo-ty` | 3 anchors @ 1024/2vh, 737/4vh, 380/2vh. Calc-rule übernimmt ab >1200 vollständig; deshalb keine wide-Anchors. | %, rem, vw, svh, vh |
| `--tw-logo-w` | 6 anchors @ 1920/17vw, 1360/22vw, 1070/22vw, 1024/24vw, 820/32vw, 400/20vh; min 9rem **max 20rem** (kompakt — die calc-Positionierung sorgt für die H1-Clearance unabhängig von der Logo-Größe, also braucht das Logo bei wide Viewports nicht weiter zu wachsen). | vw, rem, %, svh, vh |
| `--tw-bubble-tx` | 1 anchor @ 1024/0% | %, rem, vw, svh, vh |
| `--tw-bubble-ty` | 6 anchors @ 1920/**-12rem** (fix in rem, damit ultra-wide nicht weiter nach oben rutscht), 1400/-10vw, 1024/2.5vh, 820/11vh, 400/15.5vh, 380/12.25vh. **Unit-Liste: nur rem/vw/svh/vh** — `%` ist bewusst aus dem Panel-Dropdown raus, weil die Y-calc-Rule die Variable im Logo-Transform wiederverwendet und `%` dort fälschlich auf logo.height bezogen würde. | rem, vw, svh, vh |
| `--tw-bubble-w` | 4 anchors @ 1920/50vw, 1400/59vw, 1024/84vw, 600/90vw; min 26rem **max 56rem** (cappt bei ~1792 cqw). **Unit-Liste: nur vw/rem/svh/vh** — gleicher Grund wie bubble-ty, die Variable wird in der Y-calc-Rule wiederverwendet. | vw, rem, svh, vh |
| `--tw-h1` | 3 anchors @ 1920/7rem, 1024/6rem, 400/3.5rem; min 2.5rem max 9rem | rem, em, vw, %, svh, vh |
| `--tw-subtitle` | 2 anchors @ 1920/1.55rem, 400/1.06rem; min 1.06rem max 1.55rem | rem, em, vw, %, svh, vh |
| `--tw-bubble-inset-top` | 3 anchors @ 1920/22%, 1400/24%, 820/12% | %, rem, svh, vh |
| `--tw-hp-w` | 3 anchors @ 1920/30vw, 1024/50vh, 400/26vh; min 5rem max 32rem | vw, rem, %, svh, vh, cqw |
| `--tw-hp-bottom` | 3 anchors @ 1024/13vw, 400/11vw, 380/9vh | vh, svh, rem, %, vw |
| `--tw-hp-right` | 2 anchors @ 1024/0%, 380/2rem | %, rem, vw, cqw |
| `--tw-ep-size` | 2 anchors @ 1030/2.5rem, 1024/5.15cqw; min 1rem max 7rem (sharp 6 px ramp = step at the mobile↔desktop boundary) | rem, em, vw, %, svh, vh, cqw |
| `--tw-ep-tracking` | 2 anchors @ 1920/0.04em, 820/-0.045em | em, rem, % |
| `--tw-ep-arrow` | 1 anchor @ 1024/1.75rem | em, rem, vw, cqw |
| `--tw-ep-gap` | 1 anchor @ 1024/0.1em | em, rem, % |
| `--tw-ep-right` | 2 anchors @ 1920/1.5rem, 1024/5.3cqw | rem, vw, %, cqw |
| `--tw-ep-bottom` | 2 anchors @ 1030/1.5rem, 1024/16cqw (sharp 6 px ramp) | rem, vh, svh, %, cqw |
| `--tw-hero-min-h` | 3 anchors @ 1400/50rem, 820/50rem, 400/0rem; min `calc(100svh - var(--tw-topbar-h, 5rem))`. The composed value is wrapped in `min(…, svh-topbar)` inside the `.hero` rule and capped by `max-height: svh-topbar` so the rem floor can never push hero below the viewport fold. | rem, svh, vh, % |
| `--tw-topbar-h` | 3 anchors @ 1920/7rem, 1024/6rem, 820/7.5rem (mobile 2-row) | rem, vh, svh, % |

### Static Single-Sliders (im Panel, kein Anchor-System)

- `--tw-bubble-inset-bottom`: 15% (default)
- `--tw-bubble-inset-x`: 8.5%
- `--tw-sub-size` / `--tw-sub-py` / `--tw-sub-px`: Subscribe-Button (rem)
- `--tw-listen-size`, `--tw-listen-tracking`, `--tw-listen-fill-tx/ty`, `--tw-listen-outline-tx/ty`: LISTEN UP
- **Scroll-Morph**: Slider `--tw-brand-logo-h` (3rem, gedockte Logo-Höhe), `--tw-morph-start` (0vh), `--tw-morph-end` (30vh), `--tw-morph-text-start` (25vh), `--tw-morph-text-end` (32vh). Snap-in: Wordmark erscheint zeitgleich mit Andocken des Logos. `--tw-morph-scale/-tx/-ty` sind KEINE Slider — werden vom Auto-Fit-Script gemessen. Das Hero-Logo bekommt `visibility: hidden` (innerhalb `@supports`); das pixelgenau positionierte Flug-Logo (Topbar-Brand img) ist das einzige sichtbare Logo — kein Cross-Fade.

### Panel-Features

- Pro Anchor-Group: Label + `+`-Button. Pro Anchor-Zeile: `@<vw>px` + Value + Unit-Dropdown + `×`-Button + Slider darunter. Output-Box zeigt das aktuell composte CSS.
- Min/Max-Inputs als freie CSS-Length-Strings (z.B. `calc(100svh - var(--tw-topbar-h, 5rem))`).
- Copy-Button gibt `:root { … }` paste-ready aus (achtung: enthält auch statische Slider-Defaults, die nicht unbedingt angewandt sind — siehe `singles: {}` im Snapshot).
- Reset gibt alle Properties auf die Code-Defaults zurück.
- Resizable Panel (CSS `resize: both`), draggable Header. Position + Größe + Hidden-State werden persistiert (`dc-tweak-pos`, `dc-tweak-size`, `dc-tweak-hidden`).
- Storage-Key: `dc-tweak-v6`. v1–v5 werden beim Laden geräumt. v5→v6 wurde gebumpt, weil die Y-calc-Logik einheits-clean Anchors (kein `%` in bubble-ty/bubble-w) braucht und alte localStorage-States das gebrochen haben.

### Tooling

- Server: `python3 -m http.server 8765` im `frontend/sandbox/` Ordner.
- Playwright-Verify-Skript: `/tmp/dc-shots/devices.js` (deckt iPhone SE, XR, Galaxy S8+, Pixel 7, Surface Duo, iPad Pro, Tablet 768 ab). Output in `/tmp/dc-shots/*.png`. Vor jedem Screenshot wird localStorage geclearet (Code-Defaults werden gerendert).
- **localStorage aus dem Helium-Browser auslesen** (User benutzt Helium, nicht Chrome): `strings -a ~/Library/Application\ Support/net.imput.helium/Default/Local\ Storage/leveldb/*.{log,ldb} 2>/dev/null | grep "dc-tweak-v6" -A0 | tail -1` liefert das letzte JSON. (Storage-Key wird bei Anchor-Default-Breaks gebumpt; immer den aktuellen Wert von `STORAGE_KEY` in `new-header.html` nutzen.)

## Schritte / Offene Punkte

1. **Schritt 1 + 2 (erledigt)**: statisches Layout, responsive Verhalten, Komposition. Alle 20 anchored Properties getunt, Headphones + Episodes promoted.
2. **Schritt 3 — Scroll-Morph (erledigt)**: „Echter Flug" — *ein* travelling Element. Pure CSS via `animation-timeline: scroll(root block)` mit JS-Polyfill für ältere Browser. Start-Geometrie per Mess-Script.
   - **Flugobjekt**: `.topbar__brand img`. Startet hochskaliert (`scale(--tw-morph-scale)` + Offset `--tw-morph-tx/ty`) exakt auf dem Hero-Logo, schrumpft beim Scrollen über `[--tw-morph-start, --tw-morph-end]` auf den echten Topbar-Slot. `transform` skaliert nur das Visual — die `--tw-brand-logo-h`-Layout-Box bewegt sich nie, Nav verschiebt sich nicht. `transform-origin: left center` ist sowohl im `@supports`-Block (CSS) als auch im Polyfill (JS inline) gesetzt, weil das Auto-Fit-Script darauf basiert.
   - **Hero-Logo** (`.hero__logo-bubble`): bekommt im `@supports`-Block (bzw. via Polyfill JS) `visibility: hidden` — der Flug-Logo deckt es pixelgenau ab, kein Cross-Fade nötig. Bei nicht-unterstützten Browsern *und* ausgeschaltetem JS bleibt das Hero-Logo sichtbar (statischer Fallback ohne Morph).
   - **Wordmark** (`.topbar__brand span`): faded via `dc-brand-text` Keyframe über `[--tw-morph-text-start, --tw-morph-text-end]` ein.
   - **Auto-Fit-Script** (eigener `<script>`-Block, bei Migration MITNEHMEN): misst Hero-Logo + Brand-Slot per `getBoundingClientRect()` und schreibt `--tw-morph-scale/-tx/-ty` exakt nach `:root`. Läuft bei load / `fonts.ready` / resize (rAF-throttled) / Änderung von `--tw-brand-logo-h`. Während des Measure-Reads wird `animationName = 'none'` gesetzt und danach auf den vorigen Wert restored (damit der Polyfill-Override nicht verloren geht).
   - **Native Pfad**: `@media (prefers-reduced-motion: no-preference) { @supports (animation-timeline: scroll(root)) { … } }` — Chrome/Edge 115+, Safari 26+.
   - **Polyfill** (`<script>`-Block direkt nach Auto-Fit): aktiv wenn `CSS.supports('animation-timeline', 'scroll(root block)')` false. Setzt inline `brand.opacity = 1`, `heroLogo.visibility = hidden`, `brandImg.animationName = 'none'`, `brandImg.transformOrigin = 'left center'` (muss mit dem @supports-Block matchen), `brandSpan.animationName = 'none'`. Treibt den Morph dann per scroll-listener + rAF + CSS-Var-Reads. Ease-out `1-(1-t)³` matched `cubic-bezier(.2,.7,.2,1)` visuell. `prefers-reduced-motion: reduce` deaktiviert ihn ebenso wie den nativen Pfad.
   - **Mobile/Tablet-Topbar (≤1200 cqw)**: `flex-direction: column`, zwei Reihen — Nav-Links oben, Logo+Wordmark zentriert darunter. Schwelle bei 1200, weil darunter eine Side-by-Side-Komposition den Logo am narrow Viewport-Rand off-screen drücken würde. `--tw-topbar-h` @ 820 = 7.5rem gibt die Höhe für zwei Reihen. Brand bleibt im Flow (kein `display: none`), Morph läuft auch hier. Auto-Fit misst die jeweilige Brand-Position und schreibt den Start-State pixel-genau.
   - **Mobile-Logo-Lift**: Im selben `@container dc (max-width: 1200px)`-Block bekommt `.hero__logo-bubble` ein `translate: 0 -1rem`. Der Logo-Container's Bbox (inkl. der Whitespace-Quadrant um den Speech-Bubble-Tail) ragt sonst knapp in die H1-Bbox rein — der kleine Lift hält die Bboxes auseinander und sorgt für sichtbare Luft zwischen Tail-Tip und H1-Linksrand bei kurzen Viewports.
   - **Calc-basiertes Logo-X/Y auf Desktop (>1200 cqw), pure CSS**:
     ```css
     @container dc (min-width: 1201px) {
       .hero__logo-bubble {
         transform: translate(
           calc(-0.5 * var(--tw-h1) * 5.568 - 2vw - 0.5 * var(--tw-logo-w)),
           calc(var(--tw-bubble-ty) - 8.5rem
                + 0.5 * (var(--tw-bubble-w) * 908 / 1039
                       - var(--tw-logo-w) * 399 / 442))
         );
       }
     }
     ```
     - **X-Achse**: Der `5.568`-Faktor ist die empirisch konstante Ratio `h1_text_width / h1_font_size` für „Django Chat" in Ubuntu Bold. Logo's rechter Rand sitzt **2vw** (viewport-relativ) links vom H1-Text — automatisch über alle Viewport-Breiten, mit kompaktem Gap an narrow Viewports und mehr Luft an wide. **Wenn der H1-Text mal geändert wird**: einmal mit `const r=document.createRange();r.selectNodeContents(h1);r.getBoundingClientRect().width / parseFloat(getComputedStyle(h1).fontSize)` neu messen und Konstante updaten.
     - **Y-Achse**: Logo's vertikale Position ist an `--tw-bubble-ty` gekoppelt + 8.5rem konstanter Center-zu-Center-Offset (Logo-Mitte 8.5rem über Bubble-Mitte). Der Size-Difference-Term aus Aspect-Ratios kompensiert die unterschiedlichen Element-Höhen, sodass Center-zu-Center exakt 8.5rem bleibt. Wenn die Bubble nach unten/oben rutscht, folgt das Logo automatisch.
     - **Einheits-Constraint**: `--tw-bubble-ty` und `--tw-bubble-w` müssen einheits-clean sein (keine `%`-Anchors), weil `%` im Logo-Transform fälschlich auf logo.height/width bezogen würde. `%` ist deshalb aus den Panel-Dropdown-Listen dieser zwei Properties entfernt. Bei manueller Tuning-Arbeit nicht wieder hinzufügen.
   - **Mobile (≤1200 cqw)** nutzt weiter die `--tw-logo-tx`/`--tw-logo-ty` Anchors für das stacked Layout.
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
