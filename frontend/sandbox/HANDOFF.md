# Django Chat — New Hero Header (Sandbox Handoff)

## Goal

Selbst-contained Sandbox für den neuen Django-Chat Hero-Header. Erst hier sauber zu Ende bauen, dann migrieren ins Hauptprojekt (`django_chat/templates/cast/django_chat/base.html` + `django_chat/static/django_chat/css/site.css`).

**Entwurf**: `/Users/katha/Desktop/Django-Header-Idee.jpg`
**Repo-Assets**: `frontend/sandbox/assets/` (Django-chat-logo, Headphones SVG, Hero-Hintergrundbild)

## Files

- `frontend/sandbox/new-header.html` — kompletter Sandbox-HTML mit eingebettetem CSS + JS + Tweak-Panel.
- `frontend/sandbox/assets/` — Logo, Headphones, Hero-BG.
- `frontend/sandbox/tweak-snapshot.json` — authoritative Anchor-Defaults, gepflegt parallel zum Code (aktuell: v7 Storage-Key-State, `singles: {}` = keine statischen Slider angefasst). Dient als Fall-Back-Referenz, falls localStorage verloren geht.
- `frontend/sandbox/tweak-snapshot.css` — historisches CSS-Snippet von Mai 2026, nicht aktuell. Vor Konsultation der JSON-Snapshot bevorzugen.

## Aktueller Stand (2026-05-26, post Schritt 4 + Cleanup)

### Komposition

- **Topbar** (`.topbar`): sticky. Auf Desktop (>1200 cqw) einreihig mit Brand-Slot links (Landeplatz des Scroll-Morphs, statisch `visibility: hidden + pointer-events: none` — der @supports-Block oder der JS-Polyfill promotet ihn auf visible+auto). Auf Tablet/Mobile (≤1200 cqw via @container) zweireihig: Nav oben, Brand-Slot zentriert darunter. Brand bleibt überall im Flow (kein `display: none`), Morph läuft auf jedem Viewport. **Visibility statt Opacity** ist bewusst: ein opacity:0 Brand-Link wäre für die Tastatur fokussierbar (Phantom-Focus), `visibility: hidden` entfernt ihn aus der Tab-Reihenfolge.
- **Hero** (`.hero`): position:relative, min-height anchored via `--tw-hero-min-h`, gecappt auf `calc(100svh - var(--tw-topbar-h, 5rem))`.
- **`.hero__center`**: Grid mit logo-bubble + bubble in derselben grid-cell (z-stacking via DOM order + z-index).
- **`.hero__bubble`**: Flex column. SVG sitzt absolut dahinter. Vertikale Padding-Inset nutzen einen `× 908/1039`-Aspect-Ratio-Compensator, damit Panel-`%`-Werte als "% der HÖHE" funktionieren. `transform: translateY(var(--tw-bubble-ty))`; X war ein Anker mit Default 0 und wurde im Cleanup entfernt (siehe v7-Bump).
- **`.hero__logo-bubble`**: position relative, aspect-ratio 442/399. transform via Anchors (Mobile) oder pure CSS-calc-Rule (Desktop >1200 cqw, siehe unten).
- **`.hero__headphones`**: position absolute bottom-right. width / bottom / right alle anchored. Zusätzlich `translate:` für Maus-Parallax (siehe Schritt 4).
- **LISTEN UP** (`.listen-up`): position absolute bottom: 0 of stage. Fill + Outline mit translate-Y (Anschnitt-Effekt unter Viewport-Kante). Zusätzlich `translate:` für Parallax.
- **Episodes Hook** (`.hero__episodes`): position absolute. Wandert von kleinem Corner-Label (Desktop) zu großem Above-LISTEN-UP-Marker (Mobile) — über Anchors, ohne @container-Override.
- **Subscribe**: `<a class="hero__subscribe" href="/django-chat/feed/">` — Sandbox-Stub, der pfad-identisch zu `cast:feed_detail` ist (`<slug:slug>/feed/`, die HTML-Subscribe-Seite). **Bei Migration** durch das echte Django-URL-Tag ersetzen: `{% url 'cast:feed_detail' slug=podcast.slug %}`. Der reine XML-RSS-Feed (`cast:podcast_feed_rss` mit `audio_format='mp3'`) ist ein anderer Endpunkt und sitzt *hinter* der Subscribe-Seite — nicht direkt im Hero-CTA verdrahten, sonst landen User im rohen RSS-XML statt auf der Subscribe-Page.

### Anchor-System (Panel)

Pro Property eine Anchor-Liste mit `(viewport-breakpoint, value, unit)`. Pro Anchor eigene Unit wählbar via Dropdown in der Row. Sum-of-ramps Composer:

```
val₀<unit₀> + Σᵢ (valᵢ<unitᵢ> − valᵢ₋₁<unitᵢ₋₁>) × clamp(0, (100cqw − vwᵢ₋₁px) / spanᵢpx, 1)
```

- Wenn alle Anchors gleiche Unit haben: kompakte Delta-Form.
- Wenn gemischte Units: explizite `(b - a) * ramp` — CSS calc löst mixed-unit deltas zur Laufzeit (z.B. `(50svh - 76vw) * ramp`).
- Pro Property optional min/max bounds. Wenn beide gesetzt: `clamp(MIN, inner, MAX)`. Wenn nur eine Bound gesetzt: `max(MIN, inner)` bzw. `min(inner, MAX)`. Wenn keine: `inner` pur. Relevant z.B. für `--tw-hero-min-h`, das nur ein `defaultMin` hat.

**Container-Query-basiert**: `.dc-shell` wrappt topbar + hero, hat `container-type: inline-size; container-name: dc`. Alle Anchor-Formeln nutzen `100cqw` statt `100vw` — Header adaptiert auf seine Container-Breite, nicht auf den Viewport.

### 17 anchored Properties

| Property | Defaults | Units |
|---|---|---|
| `--tw-logo-tx` | **Nur in Mobile-Range (≤1200 cqw)**. 4 anchors @ 1920/-159.5%, 1400/-145%, 820/-60%, 400/-30%. Auf Desktop (>1200 cqw) wird das Logo via reiner CSS-calc-Formel positioniert. Die wide-Anchors (1400, 1920) bleiben als no-@container CSS-Fallback. | %, rem, vw, svh, vh |
| `--tw-logo-ty` | 3 anchors @ 1024/2vh, 737/4vh, 380/2vh. Calc-rule übernimmt ab >1200 vollständig. | %, rem, vw, svh, vh |
| `--tw-logo-w` | 6 anchors @ 1920/17vw, 1360/22vw, 1070/22vw, 1024/24vw, 820/32vw, 400/20vh; min 9rem max 20rem. | vw, rem, %, svh, vh |
| `--tw-bubble-ty` | 6 anchors @ 1920/-12rem, 1400/-10vw, 1024/2.5vh, 820/11vh, 400/15.5vh, 380/12.25vh. **Unit-Liste: nur rem/vw/svh/vh** — `%` ist bewusst raus, weil die Y-calc-Rule die Variable im Logo-Transform wiederverwendet und `%` dort fälschlich auf logo.height bezogen würde. | rem, vw, svh, vh |
| `--tw-bubble-w` | 4 anchors @ 1920/50vw, 1400/59vw, 1024/84vw, 600/90vw; min 26rem max 56rem. **Unit-Liste: nur vw/rem/svh/vh** (selber Grund wie bubble-ty). | vw, rem, svh, vh |
| `--tw-h1` | 3 anchors @ 1920/7rem, 1024/6rem, 400/3.5rem; min 2.5rem max 9rem. | rem, em, vw, %, svh, vh |
| `--tw-subtitle` | 2 anchors @ 1920/1.55rem, 400/1.06rem; min 1.06rem max 1.55rem. | rem, em, vw, %, svh, vh |
| `--tw-bubble-inset-top` | 3 anchors @ 1920/22%, 1400/24%, 820/12%. | %, rem, svh, vh |
| `--tw-hp-w` | 3 anchors @ 1920/30vw, 1024/50vh, 400/26vh; min 5rem max 32rem. | vw, rem, %, svh, vh, cqw |
| `--tw-hp-bottom` | 3 anchors @ 1024/13vw, 400/11vw, 380/9vh. | vh, svh, rem, %, vw |
| `--tw-hp-right` | 2 anchors @ 1024/0%, 380/2rem. | %, rem, vw, cqw |
| `--tw-ep-size` | 2 anchors @ 1030/2.5rem, 1024/5.15cqw; min 1rem max 7rem (sharp 6 px ramp = step an der mobile↔desktop-Grenze). | rem, em, vw, %, svh, vh, cqw |
| `--tw-ep-tracking` | 2 anchors @ 1920/0.04em, 820/-0.045em. | em, rem, % |
| `--tw-ep-right` | 2 anchors @ 1920/1.5rem, 1024/5.3cqw. | rem, vw, %, cqw |
| `--tw-ep-bottom` | 2 anchors @ 1030/1.5rem, 1024/16cqw (sharp 6 px ramp). | rem, vh, svh, %, cqw |
| `--tw-hero-min-h` | 3 anchors @ 1400/50rem, 820/50rem, 400/0rem; min `calc(100svh - var(--tw-topbar-h, 5rem))`. Composed value wird in `.hero` mit `min(…, svh-topbar)` gewrappt und durch `max-height: svh-topbar` gecappt. Der 820/1400-Zero-Delta ist gewollt: erzeugt einen Knie bei 820 cqw (unter 820 ramped auf 0, darüber konstant 50rem). | rem, svh, vh, % |
| `--tw-topbar-h` | 3 anchors @ 1920/7rem, 1024/6rem, 820/7.5rem (mobile 2-row). | rem, vh, svh, % |

**Im Cleanup entfernte Anchors** (waren konstant, jetzt direkt im CSS verdrahtet):

- `--tw-bubble-tx` (war immer 0%) → `transform: translateY(…)` in `.hero__bubble`.
- `--tw-ep-arrow` (war immer 1.75rem) → `width/height: 1.75rem` in `.hero__episodes svg`.
- `--tw-ep-gap` (war immer 0.1em) → `gap: .1em` in `.hero__episodes`.

### Static Single-Sliders (im Panel, kein Anchor-System)

- `--tw-bubble-inset-bottom`: 15% (default)
- `--tw-bubble-inset-x`: 8.5%
- `--tw-sub-size` / `--tw-sub-py` / `--tw-sub-px`: Subscribe-Button (rem)
- `--tw-listen-size`, `--tw-listen-tracking`, `--tw-listen-fill-tx/ty`, `--tw-listen-outline-tx/ty`: LISTEN UP
- **Scroll-Morph**: Slider `--tw-brand-logo-h` (3rem, gedockte Logo-Höhe), `--tw-morph-start` (0vh), `--tw-morph-end` (30vh), `--tw-morph-text-start` (25vh), `--tw-morph-text-end` (32vh). `--tw-morph-scale/-tx/-ty` werden vom Auto-Fit-Script gemessen.

### Panel-Features

- Pro Anchor-Group: Label + `+`-Button. Pro Anchor-Zeile: `@<vw>px` + Value + Unit-Dropdown + `×`-Button + Slider darunter.
- Min/Max-Inputs als freie CSS-Length-Strings.
- **Copy-Button** gibt `:root { … }` paste-ready aus. Migration-safe seit Cleanup: Singles werden nur aufgelistet, wenn `state.singles[var]` tatsächlich gesetzt ist (= der User hat den Slider berührt). Anchor-Werte sind immer mit dabei (composed calc).
- Reset gibt alle Properties auf die Code-Defaults zurück.
- Resizable Panel, draggable Header. Position + Größe + Hidden-State werden persistiert (`dc-tweak-pos`, `dc-tweak-size`, `dc-tweak-hidden`).
- **Storage-Key: `dc-tweak-v7`**. v1–v6 werden beim Laden geräumt. v6→v7 wurde gebumpt, weil drei Anchor-Lists (--tw-bubble-tx, --tw-ep-arrow, --tw-ep-gap) entfernt wurden und alte v6-States gestaltete Defaults hätten überleben lassen.

### Tooling

- Server: `python3 -m http.server 8765` im `frontend/sandbox/` Ordner.
- Playwright-Verify-Skripte: `/tmp/dc-shots/*.js` (devices.js, parallax-test.js, …). Output in `/tmp/dc-shots/*.png`.
- **localStorage aus dem Helium-Browser auslesen** (User benutzt Helium, nicht Chrome): `strings -a ~/Library/Application\ Support/net.imput.helium/Default/Local\ Storage/leveldb/*.{log,ldb} 2>/dev/null | grep "dc-tweak-v7" -A0 | tail -1` liefert das letzte JSON. Storage-Key bei Anchor-Default-Breaks bumpen; immer den aktuellen Wert von `STORAGE_KEY` in `new-header.html` nutzen.
- **Vor Migration** ein LevelDB-Backup empfehlen, damit ein evtl. zwischenzeitlich getuneter State nicht verloren geht.

## Schritte / Offene Punkte

1. **Schritt 1 + 2 (erledigt)**: statisches Layout, responsive Verhalten, Komposition. Alle anchored Properties getunt, Headphones + Episodes promoted.

2. **Schritt 3 — Scroll-Morph (erledigt)**: „Echter Flug" — *ein* travelling Element. Pure CSS via `animation-timeline: scroll(root block)` mit JS-Polyfill für ältere Browser. Start-Geometrie per Auto-Fit-Mess-Script.
   - **Flugobjekt**: `.topbar__brand img`.
   - **Hero-Logo** (`.hero__logo-bubble`): bekommt im `@supports`-Block bzw. via Polyfill `visibility: hidden`. Bei nicht-unterstützten Browsern *und* JS aus bleibt das Hero-Logo sichtbar (statischer Fallback ohne Morph).
   - **Auto-Fit-Script**: misst Hero-Logo + Brand-Slot per `getBoundingClientRect()` und schreibt `--tw-morph-scale/-tx/-ty` exakt nach `:root`. Re-runs on resize / fonts.ready / `--tw-brand-logo-h`-Slider-Change. **Bei Migration MITNEHMEN**.
   - **Native Pfad**: `@media (prefers-reduced-motion: no-preference) { @supports (animation-timeline: scroll(root)) { … } }` — Chrome/Edge 115+, Safari 26+.
   - **Polyfill**: defensiver `CSS.supports`-Guard (`typeof CSS !== 'undefined' && typeof CSS.supports === 'function'`). Setzt inline `brand.visibility = 'visible'`, `brand.pointerEvents = 'auto'`, `heroLogo.visibility = 'hidden'`, `brandImg.transformOrigin = 'left center'`, `brandImg.animationName = brandSpan.animationName = 'none'`. Im rAF-Update-Loop wird dann nur die Fade-In-Opacity der Wordmark (`brandSpan.style.opacity = q`) plus `brandImg.style.transform` getrieben — kein statisches `brand.opacity = 1` mehr (Baseline ist `visibility: hidden`, nicht `opacity: 0`). `prefers-reduced-motion: reduce` deaktiviert beide Pfade.
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
     - **X-Achse**: `5.568` = empirische Konstante für `h1_text_width / h1_font_size` bei „Django Chat" in Ubuntu Bold. Bei Änderung des H1-Texts: `const r=document.createRange();r.selectNodeContents(h1);r.getBoundingClientRect().width / parseFloat(getComputedStyle(h1).fontSize)` neu messen.
     - **Y-Achse**: Logo-Position an `--tw-bubble-ty` gekoppelt + 8.5rem konstanter Center-zu-Center-Offset + Size-Diff-Kompensator.
     - **Einheits-Constraint**: `--tw-bubble-ty` und `--tw-bubble-w` müssen einheits-clean sein (keine `%`-Anchors). Im Panel-Dropdown ist `%` für diese Properties entfernt.

3. **Schritt 4 — Parallax (erledigt)**: Drei Layer (Headphones, LISTEN-UP-Fill, LISTEN-UP-Outline) driften so, dass sie nie deckungsgleich sind. Magnituden-Konfiguration steht im `M`-Objekt im Parallax-Script — User-gewählter Stand: HP/Outline laufen synchron in eine Richtung, Fill driftet entgegengesetzt (HP=Outline=`{x:-0.8, y:-0.5}`, Fill=`{x:0.8, y:0.5}` cqw).
   - **CSS**: Je Layer eine separate `translate: var(--dc-px-{layer}-x, 0) var(--dc-px-{layer}-y, 0)` Property. Die separate `translate` CSS-Property wird zusammen mit dem bestehenden `transform` komponiert, ohne ihn zu überschreiben.
   - **JS**: Ein eigener `<script>`-Block direkt nach dem Scroll-Morph-Polyfill. Early-Return bei `prefers-reduced-motion: reduce`. rAF-Lerp (Faktor 0.08) zwischen Target und Current für smoothe Bewegung.
     - **`(hover: hover) and (pointer: fine)` Pfad**: `pointermove` auf `.dc-shell` → Position-zu-Center-Vektor, geclampt auf `-1..+1` pro Achse. `pointerleave` ramped zurück auf 0.
     - **Coarse Pointer / Touch (iOS/Android)**: `scroll`-Listener mappt die erste ~0.8 viewport-height Scroll-Strecke linear auf `ty = 0..+1`. `tx` bleibt 0. Selbe Per-Layer-Vorzeichen → drei Layer driften auseinander beim Scrollen in den Hero.
   - **Migration MITNEHMEN**: Den Parallax-`<script>`-Block + die drei `translate:`-CSS-Properties.
   - **Verifiziert via** `/tmp/dc-shots/parallax-test.js`.

4. **Schritt 5 (offen) — Migration ins Hauptprojekt**:

   **Production Migration Rule (für den ausführenden Agenten):**
   > Topbar bleibt in `base.html` (siteweit), der große Show-Hero wandert in den Episodenindex (`blog_list_of_posts.html`). Alte `.show-hero`-Implementierung **vor** der Migration entfernen. Tweak-Panel/Storage/Snapshot werden **nicht** migriert. Sandbox-`--tw-*`-Variablen zu component-lokalen `--show-hero-*` umbenennen. Morph- und Parallax-JS in eine statische Datei (`django_chat/static/django_chat/js/show-hero.js`) auslagern und über `data-*`-Hooks ansteuern statt über reine Klassen-Queries.

   ### Template-Aufteilung
   - **`django_chat/templates/cast/django_chat/base.html`**: Nur die Topbar (sticky brand-slot links, nav rechts, mobile 2-row ≤1200 cqw, scroll-morph-Brand). Der Hero-Bereich gehört dort **nicht** hinein, sonst bekommen Subpages versehentlich den großen Show-Hero und der Skip-Link überspringt deren eigentlichen H1.
   - **`django_chat/templates/cast/django_chat/blog_list_of_posts.html`** (Episodenindex): Show-Hero einsetzen (logo-bubble, speech-bubble mit H1 "Django Chat" + Subtitle + Subscribe-CTA, Headphones, LISTEN UP, Episodes-Anker). Vorhandene Home-Hero-Struktur dort ersetzen.

   ### Konflikt: `header-autohide.js`
   `base.html` lädt `header-autohide.js`, das aktuell `.site-header` steuert. Wenn die neue Topbar als `.site-header` migriert wird, kollidiert das mit Sticky + Scroll-Morph (Brand-Slot wird per Class versteckt während der Morph läuft = inkonsistent). Drei Optionen:
   1. `header-autohide.js` ersatzlos entfernen (Topbar bleibt immer sichtbar; sauberer für das Morph-Konzept).
   2. Autohide neu scopen auf einen anderen Selector, sodass die neue Topbar nicht reagiert.
   3. Topbar nicht an `.site-header--hidden` hängen (eigene CSS-Klasse).
   Entscheidung gehört zur Migration, nicht in die Sandbox.

   ### Naming-Mapping (Sandbox → Production)
   **CSS-Klassen:** Die Topbar-Klassen sind **nicht** 1:1 zu ersetzen — sie landen in `base.html` und müssen mit den dort bereits existierenden Klassen-Strukturen integriert werden, nicht überschrieben:

   | Sandbox | Production | Hinweis |
   |---|---|---|
   | `.dc-shell` | Container-Query-Wrapper im Episode-Index-Template, idealerweise `.show-hero-shell` oder ein bereits vorhandener Wrapper auf der Episode-Index-Seite | Container-Type bewahren |
   | `.topbar` (Wrapper) | In die bestehende `.site-header`-Struktur in `base.html` integrieren; nicht durch neue Klasse ersetzen | Sticky + height-anchor übernehmen |
   | `.topbar__brand` (Brand-Link + Logo) | In die bestehende Brand-Struktur (`.brand`/`.brand-mark`/`.brand-name`) integrieren — Markup vorhanden, Morph-Verhalten erweitert das | Element-Selektion über `data-show-hero-brand-logo` data-Attribut, nicht über Klassennamen |
   | `.topbar__nav`, `.topbar__nav a` | Existierende Nav-Klassen (`.site-nav`/`.nav-links`/`.cluster`) wiederverwenden | Hover-State an site-Tokens anpassen |
   | `.hero` | `.show-hero` (neue Komponente; Element bleibt `<section aria-labelledby="hero-title">`) | Bereits sectioning, nicht `<header>` |
   | `.hero__center`, `.hero__bubble`, `.hero__bubble-content`, `.hero__logo-bubble`, `.hero__headphones`, `.hero__subscribe`, `.hero__episodes` | `.show-hero-center`, `.show-hero-bubble`, `.show-hero-bubble-content`, `.show-hero-logo-bubble`, `.show-hero-headphones`, `.show-hero-subscribe`, `.show-hero-episodes` | Component-Prefix, BEM-`__`-Doppel-Underscore raus |
   | `.listen-up-stage`, `.listen-up`, `.listen-up--fill`, `.listen-up--outline` | `.show-hero-listen-up-stage`, `.show-hero-listen-up`, `--fill`/`--outline` | Modifier-`--` bleibt |

   **CSS-Variablen:** sandbox-`--tw-*` (tweak-driven) und parallax-`--dc-px-*` werden zu component-lokalen `--show-hero-*`:
   | Sandbox | Production |
   |---|---|
   | `--tw-logo-tx/-ty/-w` | `--show-hero-logo-tx/-ty/-w` |
   | `--tw-bubble-ty/-w/-inset-top/-inset-bottom/-inset-x` | `--show-hero-bubble-ty/-w/-inset-…` |
   | `--tw-h1`, `--tw-subtitle` | `--show-hero-h1`, `--show-hero-subtitle` |
   | `--tw-hp-w/-bottom/-right` | `--show-hero-hp-w/-bottom/-right` |
   | `--tw-ep-size/-tracking/-right/-bottom` | `--show-hero-ep-…` |
   | `--tw-hero-min-h`, `--tw-topbar-h` | `--show-hero-min-h`, `--show-hero-topbar-h` |
   | `--tw-listen-size/-tracking/-fill-tx/-ty/-outline-tx/-ty` | `--show-hero-listen-…` |
   | `--tw-sub-size/-py/-px` | `--show-hero-sub-…` |
   | `--tw-brand-logo-h`, `--tw-morph-start/-end/-text-start/-text-end/-scale/-tx/-ty` | `--show-hero-brand-logo-h`, `--show-hero-morph-…` |
   | `--dc-px-{hp,outline,fill}-{x,y}` | `--show-hero-px-{hp,outline,fill}-{x,y}` |

   **Token-Mapping (globale Sandbox-Tokens → site.css `--dc-*`):**
   | Sandbox | site.css |
   |---|---|
   | `--green` (#0ea342) | `--dc-django` (#48a04e) — semantisch gleich, Farbwerte minimal anders; Migration übernimmt site.css-Wert |
   | `--green-dark` (#14513a) | `--dc-accent-dark` (#14513a) — exakt gleich, kein Token-Neuwert nötig |
   | `--green-soft` (rgba 14,163,66,.35) | Component-lokal lassen oder via `color-mix(in srgb, var(--dc-django) 35%, transparent)` |
   | `--accent` (#41FCB9) | Sandbox-spezifischer mintgrüner Akzent für Topbar-Nav-Hover und LISTEN-UP-Outline. Wenn diese grellere Farbe in Production gewünscht: als component-lokales `--show-hero-accent`, NICHT generisch ins `:root`. |
   | `--ink` (#0b1a17) | `--dc-ink` (#0d0d0d) — fast identisch |
   | `--bg-deep` (#09201D) | Sandbox-spezifischer Hero-Wash-Hintergrund. Component-lokal als `--show-hero-bg-deep`. |
   | `--listen-up-size` | Component-lokal `--show-hero-listen-up-size` |
   | `--h1-text-ratio` (5.568) | Component-lokal `--show-hero-h1-text-ratio`. **Nicht** zu site.css `:root` heben — der Wert ist spezifisch für die H1-Text "Django Chat" in Ubuntu Bold, kein siteweites Token. |
   | `--ease-out` | Falls site.css bereits ein Standard-Easing-Token hat, das nutzen; sonst component-lokal |

   ### CSS-Architektur-Regeln aus site.css übernehmen
   - **`color-mix()`-Fallback**: site.css-Convention (siehe `--dc-django-soft`/`-tint`) ist eine literale `rgb()`/`rgba()`-Deklaration **direkt vor** jeder `color-mix()`-Zeile als Safari 16.0/16.1-Fallback. Wenn diese Browser-Versionen weiterhin Teil der unterstützten Baseline sind, gilt das auch für die Show-Hero-Komponente. Konkret betroffen: der Hero-Wash-Gradient (zwei `color-mix(in srgb, var(--show-hero-bg-deep) 45/55%, transparent)`-Stops) und ggf. der LISTEN-UP-Fill (`--green-soft` als color-mix). Die literale Form muss bei Brand-Token-Änderungen synchron gepflegt werden — site.css-Kommentar dokumentiert das Pattern.
   - **`@layer`-Einbettung**: site.css strukturiert mit `@layer base`. Show-Hero-Component-Styles sollten in einen passenden Layer (z.B. `@layer components` oder neu `@layer show-hero`) eingebunden werden, damit die Cascade vorhersagbar bleibt.

   **Hardcoded Werte, die in Production Tokens werden sollten:**
   - `border-radius: 999px` (`.hero__subscribe`) → `var(--dc-radius-pill)`
   - `min-height: var(--dc-tap)` am Subscribe-Button explizit setzen (44px Apple-Tap-Floor, aktuell durchs Padding nur implizit erfüllt)
   - Z-Index-Werte 0/4/5/50/60 → component-lokale Tokens `--show-hero-z-listen-up: 0`, `--show-hero-z-episodes: 4`, `--show-hero-z-bubble: 5`, `--show-hero-z-topbar: 50`, `--show-hero-z-logo: 60` — macht die Stacking-Logik lesbarer
   - Bubble-shadow `drop-shadow(0 30px 40px rgba(0,0,0,.25))` → component-lokales `--show-hero-bubble-shadow` (shape-spezifisch, nicht ins globale Theme)
   - Breakpoint `1200px`/`1201px` in den `@container`-Rules → mit Comment dokumentieren, dass Container-Query-Thresholds keine `var()` akzeptieren (deshalb literal); ggf. `75em`/`75.0625em` für rem-skalierende Konsistenz

   ### JS-Migration: Static Files + `data-*` Hooks
   Die drei Inline-`<script>`-Blöcke (Auto-Fit, Polyfill, Parallax) werden zu `django_chat/static/django_chat/js/show-hero.js` (oder gesplittet). Selektoren sollten auf `data-*`-Attributen sitzen statt auf Klassen:
   - `data-show-hero-shell` (Container-Query-Wrapper, Parallax-Mount-Punkt)
   - `data-show-hero-brand-logo` (Topbar-Brand-img, Auto-Fit + Morph)
   - `data-show-hero-hero-logo` (Hero-Logo-Container, Auto-Fit + Morph + Parallax-Off-Target)
   - `data-show-hero-listen-up-fill` / `-outline` (Parallax-Targets)
   - `data-show-hero-headphones` (Parallax-Target)
   - `data-show-hero-brand-logo-h-slider` (entfällt — Tweak-Panel-only)

   Damit ist die JS-Logik unabhängig von Klassenwahl der Migration. Der Auto-Fit-ResizeObserver in der Sandbox observiert bereits `.dc-shell`, `heroLogo`, `brandLogo` — das mappt 1:1 auf die data-Attribute.

   ### Subscribe-CTA
   - URL: `{% url 'cast:feed_detail' slug=podcast.slug %}` (HTML-Subscribe-Seite mit Plattform-Links + RSS). **Nicht** `cast:podcast_feed_rss` (das ist das rohe XML, sitzt hinter der Subscribe-Seite).
   - Sandbox-Stub `/django-chat/feed/` ist nur pfad-gleich, nicht das richtige URL-Tag.

   ### Subtitle: `<br>` ist i18n-fragil
   Der harte `<br>` zwischen "Web Framework" und "by Will Vincent" funktioniert für das EN-Original visuell sauber. Bei späterer i18n oder dynamischem Subtitle-Content: durch CSS-driven Umbruch ersetzen oder mit semantischen Inline-Spans arbeiten, sonst bricht das Layout an unerwarteten Stellen.

   ### A11y-Carry-Over
   - **Hero-Logo `alt=""`** — Logo ist dekorativ, der H1 dahinter trägt den Markenamen für Screenreader. Migration übernehmen.
   - **`<section class="hero" aria-labelledby="hero-title">`** — kein `<header>` mehr (würde ein zweites banner-Landmark neben dem Site-Header in `base.html` erzeugen). Der `<h1 id="hero-title">` ist der labelling-Anchor.
   - **`:focus-visible`-Outline auf Subscribe** mit `--accent` — in Production an das site-weite Focus-Outline-Token anpassen, z.B. `outline: var(--dc-focus-outline, 2px solid var(--dc-django)); outline-offset: 3px`.
   - **reduce-motion** ist bereits durchgängig respektiert: Scroll-Morph (CSS + JS-Polyfill), Parallax (JS), Subscribe-Transitions + translateY. Bei zusätzlichen Hover-/Transition-Effekten in der Production-Komponente das Pattern fortführen.
   - **Color-Contrast (gefixt)**: Subscribe nutzt jetzt **dunklen Text auf hell-grünem Idle** und **weißen Text auf dunkel-grünem Hover/Focus** — bewusst weil die Subscribe-`font-size` per `clamp(1rem, 1.4cqw, 1.4rem)` auf <1200 cqw effektiv 16 px ist (clamp-Untergrenze), und 16 px Bold ist **kein** WCAG-Large-Text (Schwelle: 14pt ≈ 18.66 px). `#fff` auf `--green` (#0ea342) lag bei 3.31:1 → fail bei normal text. Aktuell (gemessen): `--ink` (#0b1a17) auf `--green` (#0ea342) = **5.40:1** (idle, passes AA Normal 4.5:1) und `#fff` auf `--green-dark` (#14513a) = **9.26:1** (hover, passes AAA 7:1). Bei Migration auf `--dc-django` (#48a04e, 3.27:1 mit weißem Text — auch zu wenig): das Muster „dunkler Text auf hellem Brand-Grün" beibehalten, also `color: var(--dc-ink)` für Idle, `color: var(--dc-paper)` für Hover/Focus.
   - **Optionale Erweiterung** (nicht in Sandbox umgesetzt): Subscribe-Link mit visually-hidden Kontext-Suffix versehen, z.B. `Subscribe<span class="visually-hidden"> to the Django Chat podcast</span>`. Setzt eine `.visually-hidden`-Utility-Klasse in site.css voraus.
   - **`aria-current="page"`** für aktive Topbar-Nav-Items — Django-Template-Logik, gehört in `base.html` bei der Topbar-Integration.

   ### Was migriert wird vs. was nicht
   - **Migrieren**: HTML-Markup (gestripped vom Panel), CSS-Layout + Morph + Parallax, Auto-Fit-Script, Polyfill, Parallax-Script (alle drei in static file).
   - **NICHT migrieren**: Tweak-Panel HTML/CSS/JS, `tweak-snapshot.json`, `tweak-snapshot.css`, der Storage-Key-Cleanup-Block, das Sandbox-only Comment am Panel.

   ### Pre-Migration-Checks
   - `git log -p django_chat/static/django_chat/css/site.css django_chat/templates/cast/django_chat/blog_list_of_posts.html` — User erinnerte sich, dass es früher schon mal ein vergleichbares Mobile-Verhalten gab (Brand unsichtbar, Nav zentriert); Endzustand soll dazu passen.
   - LevelDB-Backup der Helium-Tuning-State falls noch nicht gemacht.
   - Manuellen Test des `header-autohide.js`-Verhaltens vor und nach Migration.

## Wichtige Conventions

- **Niemals eigenmächtig committen/pushen** (siehe `~/.claude/projects/-Users-katha-gitprojects-django-chat/memory/feedback_no_auto_commit.md`).
- User benutzt **Helium-Browser** (Chromium-basiert). localStorage liegt in `~/Library/Application Support/net.imput.helium/Default/Local Storage/leveldb/` (nicht Chrome).
- **CSS first, JS als Fallback/Progressive Enhancement** — siehe `~/.claude/CLAUDE.md` Frontend Principles.
- Für UI-Arbeit: `frontend-design` und `every-layout` Skills proaktiv nutzen.
- **Commit-Messages**: nie Selbstreferenzen / "Claude" / „Generated with …".
- **Copy-Button-Output ist migration-safe**: Anchors immer enthalten, Singles nur wenn tatsächlich getunt (`state.singles[var]` gesetzt).
