# Django Chat — New Hero Header (Sandbox Handoff)

## Goal

Wir bauen den neuen Header für die Django-Chat-Seite als Sandbox-Komponente. Erst sauber außerhalb der Live-Seite entwickeln, dann später migrieren.

**Entwurf:** `/Users/katha/Desktop/Django-Header-Idee.jpg`
**Original-Assets:** auf `~/Desktop/` (DC-Bubble.svg, Django-chat-logo-neu.svg, Headphones.svg)

## Files

- `frontend/sandbox/new-header.html` — die komplette Sandbox (HTML + CSS + JS)
- `frontend/sandbox/assets/` — Kopien der drei SVGs + des Hero-Hintergrundbilds
- `frontend/sandbox/HANDOFF.md` — dieses Dokument

## Vorgehen

1. **Schritt 1 + 2 (erledigt):** statisches Layout, responsive Verhalten, Komposition
2. **Schritt 3 (offen):** Scroll-Morph — Logo + „Django Chat" wandern beim Scrollen aus dem Hero in die Topbar, via `animation-timeline: scroll()`
3. **Schritt 4 (offen):** Maus-Parallax auf Headphones + LISTEN-UP-Layer
4. **Schritt 5 (offen):** Migration in `django_chat/templates/cast/django_chat/base.html` und `site.css`

## Aktueller Stand der Komponente

### Komposition (von oben nach unten)

- **Topbar** (`.topbar`): sticky, 2 Reihen — Menü oben rechts, Brand-Lockup („django Django Chat") unten links. Auf Mobile sichtbar (immer), auf Desktop bis zum Scroll-Morph unsichtbar (Ziel-Slot für den Scroll-Morph).
- **Hero** (`.hero`): `min-height: max(calc(100svh - var(--topbar-h)), 42rem)` — Bubble, Logo, Headphones, LISTEN UP, Episodes-Hook
- **Below** (`.below`): Placeholder-Section unter dem Hero (Scroll-Test)

### Menü-Items (final)

`Episodes`, `Sponsor Us`, `Fosstodon`. Live-Daten kommen später aus `source_metadata.visible_menu_links` (siehe `templates/cast/django_chat/base.html:90-99`).

### Background

`assets/hero-bg.jpg` (Kopie von `django_chat/static/django_chat/img/show-hero-bg.jpg`), mit `linear-gradient(180deg, rgba(9,32,29,.45) 0%, rgba(9,32,29,.55) 100%)` als Overlay.

### Farben

```css
--bg-deep:    #09201D;
--accent:     #41FCB9;
--green:      #0ea342;
--green-soft: rgba(14, 163, 66, 0.35);
```

### Body-Text-Größe (aus dem bestehenden Projekt)

`--text-base: 1.06rem` (≈17px) — `site.css:143`. Subtitle-Min hängt daran.

## Design-Entscheidungen (Why)

### Bubble-Composition

- **70vw-Spec von Anfang an verworfen** — User hat sich später für eine kleinere, kontrolliertere Bubble entschieden, gesteuert durch `min/svh/horizontalen Constraint/max`.
- **Bubble „fillt die oberen 2/3"** — bezogen auf die *Dome ohne Tail*. Tail nimmt ~10% der Bubble-Höhe; Dome ≈ 90%. Daraus die svh-Faktoren.
- **Bubble darf nie kleiner werden als Content + Padding** — Floor 35rem.
- **Bubble darf nie zu groß werden** — Ceiling 60rem.
- **Bubble bleed auf Mobile** — unter ~470 px erlaubt, dann ist die Bubble breiter als der Viewport (Floor 28rem mobile). Content bleibt aber durch `max-width: calc(100vw - 2rem)` immer im Viewport mit Padding.

### Bewegungs-Interpolation zwischen 1920px ↔ 820px

- **820px** ist die Mobile-Schwelle (Media-Query-Breakpoint). Bei 820 sollte die Composition optisch dort sein, wo der Mobile-Stack einsteigt → saubere Überleitung, kein Sprung.
- **Bubble translateY**: `-14rem` (1920) → `+5rem` (820). Bei narrow Desktop sinkt die Bubble UNTER den Topbar, sodass die H1 unterhalb der Logo-Unterkante liegt.
- **Logo translateX**: `-135%` (1920) → `-120%` (820). Logo wandert leicht nach rechts, schließt das „Dreieck-Loch" zwischen Logo / Bubble / Topbar.
- **Logo translateY**: `-19%` (1920) → `-45%` (820). Logo darf **niemals** oben angeschnitten werden. Die Range ist begrenzt durch die Topbar-Höhe an jedem Viewport.
- **Bubble inset-top**: `22%` (1920) → `12%` (820). Kompensiert die Bubble-Bewegung — wenn die Bubble runter rutscht, sitzt der Content nicht „abgestürzt" zu tief.
- **Topbar-Höhe**: `5rem` (1920) → `8.5rem` (820). Topbar wächst beim schmaler werden, damit Menü oben + Brand unten Platz haben.

### Größen-Verhältnisse

- **H1 = 13% der Bubble-Breite**, capped by 6rem max. Plus viewport-Cap `(100vw - 2rem) / 5.6` bei sehr schmalen Devices (verhindert H1-Anschnitt auf <440px).
- **Subtitle = 22.5% der H1** ≈ 2.9% der Bubble. Min 1.06rem (Body-Text-Größe).
- **Logo = 0.4 × Bubble-Breite** (Default, war zwischenzeitlich 0.48).
- **LISTEN UP = 23vw**, max 29rem. Bottom-anchored mit Fill `+2%`/Outline `-1%` (eigene Höhe) — konstant über alle Viewports.
- **Headphones = 32vw mit 65vh-Cap**, min 17.5rem floor, max 31.25rem.

### Topbar 2-Reihen-Layout (umgedreht zu Live-Seite)

- **Live-Seite:** Logo oben, Menü unten.
- **Neues Design:** **Menü oben, Logo unten.** Grund: Scroll-Morph soll das große Hero-Logo in die untere Reihe der Topbar wandern lassen — sauberer animierbar.

### Hartzonen (NICHT verletzen)

1. **Logo darf NIE oben angeschnitten werden** (logo_top ≥ 0 in Viewport-Koordinaten).
2. **Logo darf NIE die H1 überlappen** — runde Form, Body-Curve am H1-y-Level muss links der H1 bleiben.
3. **Logo darf NIE aus dem Viewport rutschen** (auch nicht links bei sehr schmalen Viewports).
4. **Bubble darf NIE kleiner werden als der Content** (mit Padding innen).
5. **Content (H1/Subtitle/Subscribe) bleibt immer mit Padding zum Viewport-Rand** — auch wenn die Bubble seitlich aus dem Viewport ragt.
6. **Episodes-Hook ist immer im Viewport sichtbar**.

### Selektor-Falle (gelöst, dokumentiert)

`.hero__bubble svg` matched **alle** Descendant-SVGs inklusive dem Feed-Icon im Subscribe-Button → führte dazu, dass das Icon auf die volle Bubble gestreckt wurde und „im Layout herumflog". **Fix:** Direkter Kind-Selektor `.hero__bubble > svg`.

### Z-Index-Falle (gelöst, dokumentiert)

`.hero__center` hatte `z-index: 2` → erzeugte einen Stacking-Context, der den Logo (z-index: 60) im 2er-Kontext gefangen hielt → das Logo blieb hinter der Topbar (z-index: 50). **Fix:** Kein `z-index` auf `.hero__center`. DOM-Order regelt die internen Stacks.

## Tweak Panel

Sandbox-only Dev-Tool im selben HTML-File. Aktuell:

- **Position:** rechts oben, draggable per Drag am Header
- **Toggle:** ⚙-Button unten rechts (war früher `≡`, wurde mit Hamburger-Menü verwechselt)
- **Default-State:** sichtbar (`localStorage.getItem('dc-tweak-hidden') === '1'` versteckt)
- **Slider + Text-Input pro Variable:** Slider für Quick-Tweak in nativer Einheit, Text-Input nimmt beliebigen CSS-Wert (vw, svh, rem, clamp, calc, …)
- **Werte persistieren** in `localStorage` unter Key `dc-tweak-v3` (alte v1/v2 werden beim Load gelöscht)
- **Reset / Copy** im Header

### Bekanntes Limit (das ist der nächste Schritt!)

Sobald ein Slider gesetzt wird, fliegt die Clamp-Interpolation raus (CSS-Variable hat einen konstanten Wert). Die dynamischen Bewegungen über die Viewport-Range sind nicht über die Slider einstellbar.

## NÄCHSTER SCHRITT — A + B Implementation

Der User hat A + B beauftragt. Das ist der **erste Task der neuen Session**.

### A) Anchor-Slider-Paare für interpolierte Bewegungen

Für jede viewport-getriebene Animation **zwei Slider** statt einem:

| Variable | @ 1920 (wide) | @ 820 (narrow) |
|---|---|---|
| `--logo-tx-wide` / `--logo-tx-narrow` | `-135%` | `-120%` |
| `--logo-ty-wide` / `--logo-ty-narrow` | `-19%` | `-45%` |
| `--bubble-ty-wide` / `--bubble-ty-narrow` | `-14rem` | `5rem` |
| `--inset-top-wide` / `--inset-top-narrow` | `22%` | `12%` |
| `--topbar-h-wide` / `--topbar-h-narrow` | `5rem` | `8.5rem` |

**CSS-Komposition** in den Components, etwa:

```css
clamp(
  min(var(--bubble-ty-wide), var(--bubble-ty-narrow)),
  calc(
    var(--bubble-ty-narrow) +
    (100vw - var(--vp-narrow)) / (var(--vp-wide) - var(--vp-narrow))
    * (var(--bubble-ty-wide) - var(--bubble-ty-narrow))
  ),
  max(var(--bubble-ty-wide), var(--bubble-ty-narrow))
)
```

mit `--vp-wide: 120rem` und `--vp-narrow: 51.25rem`.

### B) Clamp-Komponenten-Slider für Größen

| Variable | Min | Fluid | Max |
|---|---|---|---|
| `--bubble-w` | `--bubble-min: 35rem` | `--bubble-vw: 75` + `--bubble-svh: 92` | `--bubble-max: 60rem` |
| `--listen-up-size` | `--listen-min: 3rem` | `--listen-vw: 23` | `--listen-max: 29rem` |
| `--hp-w` | `--hp-min: 17.5rem` | `--hp-vw: 32` + `--hp-vh: 65` | `--hp-max: 31.25rem` |

Plus Ratios:
- `--logo-ratio: 0.4`
- `--h1-ratio: 0.13` mit `--h1-min: 2.5rem` und `--h1-max: 6rem`
- `--subtitle-ratio: 0.029` mit `--subtitle-min: 1.06rem` und `--subtitle-max: 1.55rem`

**Fluid-Komposition** (Beispiel Bubble):
```css
--bubble-w: clamp(
  var(--bubble-min),
  min(
    calc(var(--bubble-vw) * 1vw),
    calc(var(--bubble-svh) * 1svh)
  ),
  var(--bubble-max)
);
```

### Panel-Umbau

- Bestehende Slider für die o.g. Variablen entfernen / ersetzen
- Pro Anchor-Paar: 2 Slider + 2 Text-Inputs (Sektion „… @ wide" / „… @ narrow")
- Pro Clamp-Größe: 3-4 Slider + Text-Inputs (Min/Fluid-VW/Fluid-VH/Max)
- Andere Tweaks (Padding-X, Tracking, Subscribe-Button etc.) bleiben als Single-Slider mit Text-Input.

### Reihenfolge

1. CSS :root umstrukturieren (neue Variablen einführen, Composing-Formeln schreiben)
2. Component-Rules aktualisieren (`hero__bubble`, `hero__logo-bubble`, `hero__bubble-content`, `topbar`, etc.)
3. Panel HTML neu strukturieren (Anchor- und Komponenten-Sektionen)
4. JS leicht anpassen (keine grundsätzliche Änderung — die bestehende Slider+TextInput-Logik passt)
5. Per Playwright-Screenshots bei 1920/1440/1200/1024/820/768/480/375 verifizieren

### Storage-Key bumpen

Beim Umbau zu `dc-tweak-v4` bumpen, damit alte v3-Overrides nicht reinpfuschen.

## Playwright-Setup für Verification

```js
const { chromium } = require('playwright');
// installiert: /Users/katha/Library/Caches/ms-playwright/chromium-headless-shell-...
// Script-Vorlagen: /tmp/dc-shots/all-widths.js (Multi-Viewport-Sweep)
//                  /tmp/dc-shots/with-panel.js (mit sichtbarem Panel)
// Output:           /tmp/dc-shots/*.png
```

Vor dem Screenshot immer `localStorage.clear()` aufrufen, damit alte Tweaks nicht reinhängen.

## Diverses

- **Build-Hook / Hot-Reload:** keiner. User refresht den Browser manuell.
- **Commit-Politik:** **nie eigenmächtig commit/push** ([[feedback_no_auto_commit]]). Nur auf explizite Aufforderung.
- **Letzter visueller Stand (1920 px):** Logo top-left, fully visible (top y ≈ 14), Bubble tief im Anschnitt (-14rem translateY), H1 bei y ≈ 41-129, kein Logo-H1-Overlap, Headphones rechts hinter Bubble, LISTEN UP bottom-anchored mit leichtem Anschnitt links/rechts, Episodes bottom-right.
