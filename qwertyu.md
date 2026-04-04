# 🛵 KiranaRush — Hyperlocal Delivery Platform
### Full-Stack Django + React Native Product Specification & Prompt

---

## 🧭 Product Vision

**KiranaRush** is a hyperlocal, multi-vendor, multi-role delivery platform connecting neighbourhood Kirana stores with customers through a network of independent delivery riders. Think of it as the intersection of **Dunzo's neighbourhood focus**, **Zomato's UX polish**, and **Sarvam.ai's clean modern design language** — built for Bharat.

---

## 🎨 UI/UX Design System — Production Level

---

### 1. Design Philosophy & Aesthetic Direction

KiranaRush lives at the intersection of three worlds:
- **Sarvam.ai's structural DNA** — generous whitespace, clear typographic hierarchy, flat surfaces with confident depth
- **Zomato's action density** — every scroll reveals value; persistent CTAs; information without overwhelm
- **Indian vernacular warmth** — earthy warmth in the palette, accessibility for all literacy levels, bharat-first iconography

The aesthetic is **"Warm Precision"**: clean enough for tech-forward early adopters, warm enough for the neighbourhood aunty ordering dal. Never cold. Never clinical. Always immediate.

---

### 2. Design Tokens & Style Guide

#### 2.1 Color System

```
── Brand Colors ────────────────────────────────────────────────
  --color-navy-950:    #0D0F1F   ← Deepest navy (headers, overlays)
  --color-navy-900:    #1A1A2E   ← Primary brand (navigation, primary text)
  --color-navy-800:    #16213E   ← Deep sections, footer
  --color-navy-700:    #1F2D55   ← Active states, selected items

  --color-orange-600:  #FF5733   ← Primary CTA (buttons, alerts, badges)
  --color-orange-500:  #FF6B4A   ← Hover state of CTA
  --color-orange-100:  #FFF0EC   ← Light tint for selected cards, highlights
  --color-orange-050:  #FFF8F6   ← Subtle background tints

── Neutral Scale ───────────────────────────────────────────────
  --color-gray-900:    #111827   ← Primary text
  --color-gray-700:    #374151   ← Secondary text
  --color-gray-500:    #6B7280   ← Placeholder, caption text
  --color-gray-300:    #D1D5DB   ← Borders, dividers
  --color-gray-200:    #E5E7EB   ← Card borders (default)
  --color-gray-100:    #F3F4F6   ← Subtle backgrounds
  --color-gray-050:    #F9FAFB   ← Page background (not pure white)

── Semantic Colors ─────────────────────────────────────────────
  --color-success:     #16A34A   ← Order confirmed, payment success
  --color-success-bg:  #F0FDF4   ← Success badge background
  --color-warning:     #D97706   ← Low stock, pending
  --color-warning-bg:  #FFFBEB   ← Warning badge background
  --color-error:       #DC2626   ← Errors, rejections
  --color-error-bg:    #FEF2F2   ← Error badge background
  --color-info:        #0284C7   ← Live tracking, rider online
  --color-info-bg:     #F0F9FF   ← Info badge background

── Special Purpose ─────────────────────────────────────────────
  --color-live:        #00C896   ← Pulsing dot for live/online status
  --color-electric:    #00B4D8   ← Electric vehicle badge
  --color-gold:        #F59E0B   ← Star ratings
  --color-overlay:     rgba(13, 15, 31, 0.6)   ← Modal backdrops
  --color-skeleton:    linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)
```

#### 2.2 Typography System

```
── Typeface Stack ──────────────────────────────────────────────
  Display / Headings:   'Plus Jakarta Sans', sans-serif
  Body / UI:            'DM Sans', sans-serif
  Monospace (OTP/IDs):  'JetBrains Mono', monospace
  Fallback:             -apple-system, BlinkMacSystemFont, 'Segoe UI'

── Type Scale (rem based, base 16px) ──────────────────────────
  --text-xs:    0.75rem  / 12px   line-height: 1rem      ← Labels, captions
  --text-sm:    0.875rem / 14px   line-height: 1.25rem   ← Helper text, tags
  --text-base:  1rem     / 16px   line-height: 1.5rem    ← Body copy
  --text-lg:    1.125rem / 18px   line-height: 1.75rem   ← Subtitles
  --text-xl:    1.25rem  / 20px   line-height: 1.75rem   ← Section headers
  --text-2xl:   1.5rem   / 24px   line-height: 2rem      ← Card titles
  --text-3xl:   1.875rem / 30px   line-height: 2.25rem   ← Screen titles
  --text-4xl:   2.25rem  / 36px   line-height: 2.5rem    ← Hero headlines
  --text-display: 3rem  / 48px    line-height: 1.1       ← Splash / splash

── Font Weights ────────────────────────────────────────────────
  Regular:      400   ← Body, descriptions
  Medium:       500   ← Labels, secondary CTAs
  SemiBold:     600   ← Prices, stats, navigation
  Bold:         700   ← Section headers, card titles
  ExtraBold:    800   ← Display, hero text, brand name

── Letter Spacing ──────────────────────────────────────────────
  Tracking tight:  -0.025em   ← Large display text
  Tracking normal:  0em       ← Body
  Tracking wide:    0.05em    ← Small caps, labels, tags
  Tracking wider:   0.1em     ← ALL CAPS badges, categories
```

#### 2.3 Spacing & Layout Grid

```
── Spacing Scale (4px base unit) ───────────────────────────────
  --space-1:   4px    ← Icon gaps, tight inline spacing
  --space-2:   8px    ← Inline padding, icon-to-text gap
  --space-3:   12px   ← Small component padding
  --space-4:   16px   ← Standard padding (most card internals)
  --space-5:   20px   ← Comfortable sections
  --space-6:   24px   ← Card padding, form field spacing
  --space-8:   32px   ← Section gaps
  --space-10:  40px   ← Large section breaks
  --space-12:  48px   ← Hero sections
  --space-16:  64px   ← Full-section padding

── Border Radius ───────────────────────────────────────────────
  --radius-sm:   6px    ← Tags, small badges
  --radius-md:   10px   ← Input fields, small buttons
  --radius-lg:   16px   ← Standard cards
  --radius-xl:   20px   ← Bottom sheets, modal cards
  --radius-2xl:  24px   ← Feature cards, hero cards
  --radius-full: 9999px ← Pills, circular avatars, toggles

── Shadows ────────────────────────────────────────────────────
  --shadow-xs:   0 1px 2px rgba(0,0,0,0.05)
  --shadow-sm:   0 2px 4px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)
  --shadow-md:   0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)
  --shadow-lg:   0 8px 24px rgba(0,0,0,0.10), 0 4px 8px rgba(0,0,0,0.06)
  --shadow-xl:   0 16px 48px rgba(0,0,0,0.12), 0 8px 16px rgba(0,0,0,0.08)
  --shadow-float: 0 24px 64px rgba(0,0,0,0.14)   ← FABs, floating cart
  --shadow-orange: 0 8px 24px rgba(255,87,51,0.28) ← CTA buttons (brand glow)

── Layout Grid (React Native) ──────────────────────────────────
  Columns:      4 (phone) / 8 (tablet)
  Gutter:       16px
  Margin:       16px (phone) / 24px (tablet)
  Safe areas:   Always respect iOS/Android safe area insets
  Max width:    428px (iPhone Pro Max reference)
```

#### 2.4 Component Tokens

```
── Input Fields ─────────────────────────────────────────────────
  Height:          52px (comfortable tap target, ≥48px WCAG)
  Background:      #F9FAFB (resting) → #FFFFFF (focused)
  Border:          1.5px solid #E5E7EB (resting)
  Border-focused:  1.5px solid #1A1A2E (focus ring, navy)
  Border-error:    1.5px solid #DC2626 + light red background
  Border-radius:   12px
  Padding:         14px 16px
  Label:           12px semibold, #374151, 4px above field
  Placeholder:     #9CA3AF (DM Sans Regular)
  Helper text:     12px, #6B7280, 4px below field
  Error text:      12px, #DC2626, icon + message

── Buttons ──────────────────────────────────────────────────────
  Primary:
    Height: 52px | Radius: 14px | Padding: 0 24px
    Background: #FF5733 | Text: #FFFFFF, 16px semibold
    Shadow: --shadow-orange
    Pressed: scale(0.97) + darken(#E64A2E)
    Loading: spinner replaces text, disabled interaction

  Secondary:
    Height: 52px | Radius: 14px | Padding: 0 24px
    Background: transparent | Border: 1.5px solid #1A1A2E
    Text: #1A1A2E, 16px semibold
    Pressed: Background #F3F4F6

  Ghost / Text:
    No border, no background
    Text: #FF5733 or #1A1A2E, 14px medium
    Underline on press

  Destructive:
    Background: #FEF2F2 | Text: #DC2626 | Border: 1px solid #FECACA

  Icon Button (circular):
    Size: 44px × 44px | Radius: full
    Background: #F3F4F6 | Icon: 20px stroke

── Badges / Tags ────────────────────────────────────────────────
  Structure: [Icon?] [Label]
  Padding: 4px 10px | Radius: full | Font: 11px semibold tracking-wider

  Open:      Background #F0FDF4, Text #16A34A, Dot #16A34A (pulsing)
  Closed:    Background #F9FAFB, Text #6B7280
  Pending:   Background #FFFBEB, Text #D97706
  Live:      Background #EFF6FF, Text #2563EB, animated border
  Electric:  Background #F0F9FF, Text #0284C7, ⚡ icon
  Discount:  Background #FFF0EC, Text #FF5733

── Cards ────────────────────────────────────────────────────────
  Standard card:
    Background: #FFFFFF
    Border: 1px solid #E5E7EB
    Border-radius: 16px
    Shadow: --shadow-md
    Padding: 16px

  Elevated card (featured):
    Border-radius: 20px
    Shadow: --shadow-lg
    May have colored top border (3px, accent color)

  Tappable state:
    Press → scale(0.98) + shadow reduces
    Haptic feedback (light impact)

  Skeleton loader:
    Same dimensions, animated shimmer gradient
    Duration: 1.2s infinite ease-in-out
```

---

### 3. Motion & Animation System

#### 3.1 Animation Principles
- **Purposeful**: Every animation communicates something — state change, hierarchy, causality
- **Fast by default**: Most micro-interactions ≤ 200ms. Nothing feels sluggish
- **Spring physics**: Use spring curves (not ease-in-out) for organic feel
- **Interruptible**: User can always interrupt mid-animation

#### 3.2 Duration Scale
```
  --duration-instant:  50ms    ← Haptic responses, icon swap
  --duration-fast:     150ms   ← Button press, toggle
  --duration-normal:   250ms   ← Card appear, tab switch
  --duration-slow:     400ms   ← Page transition, modal open
  --duration-slower:   600ms   ← Success screen, onboarding
  --duration-crawl:    1200ms  ← Skeleton shimmer, background animations
```

#### 3.3 Easing Curves
```
  --ease-spring:    cubic-bezier(0.34, 1.56, 0.64, 1)  ← Bouncy CTAs, FAB
  --ease-smooth:    cubic-bezier(0.25, 0.46, 0.45, 0.94) ← Page transitions
  --ease-sharp:     cubic-bezier(0.4, 0, 0.6, 1)        ← Dismissals
  --ease-linear:    linear                               ← Progress bars, shimmer
```

#### 3.4 Screen Transitions
```
  Push navigation:       New screen slides in from right (350ms --ease-smooth)
  Pop navigation:        Current screen slides out to right + prev reveals
  Modal / bottom sheet:  Slides up from bottom (400ms --ease-spring)
  Modal dismiss:         Slides down (250ms --ease-sharp)
  Tab switch:            Crossfade (150ms) — no slide, instant feel
  Alert / toast:         Slides in from top, auto-dismiss (3s), slide out
```

#### 3.5 Micro-interaction Catalogue

```
Add to Cart (+):
  1. Button morphs: [ + Add ] → [ − 1 + ] (spring, 250ms)
  2. Product thumbnail does a mini "jump" (translateY -8px → 0, 200ms)
  3. Floating cart counter increments with a bounce (scale 1.3 → 1, 150ms)
  4. Haptic: light impact

Cart Counter Bubble:
  Number change: old number flies up and out, new drops in (150ms)
  Color pulses orange for 300ms on each increment

Order Placed Success:
  Full-screen lottie: checkmark draws, confetti bursts (600ms)
  Text staggers in: title (0ms delay), subtitle (100ms), CTA (200ms)
  Background: white → very light orange tint → white

Rider Pin on Map:
  Custom animated SVG pin — bike icon that subtly rocks side to side (2s loop)
  Direction: pin rotates to match heading (smoothly interpolated)
  Trail: faint dotted path left behind (fades over 5s)

Live Status Dot:
  CSS keyframe: opacity 1 → 0.3 → 1, scale 1 → 1.4 → 1 (1.5s loop)
  Colour: --color-live (#00C896)

Toggle (Online/Offline for Rider):
  Thumb slides with spring physics (--ease-spring, 200ms)
  Background color transitions simultaneously
  Haptic: medium impact on state change

Skeleton → Content:
  Content fades in (opacity 0 → 1, 300ms) while skeleton fades out
  No layout shift — skeleton matches exact content dimensions

Bottom Sheet Drag:
  Follow finger exactly (no delay)
  Snap to: open / half / closed positions
  Velocity-based: fast swipe = snap direction
  Rubber-band past limits (0.3 resistance factor)

OTP Input Boxes:
  Each digit: subtle scale animation on entry (1.0 → 1.05 → 1.0, 100ms)
  All 6 filled: boxes briefly turn green, then trigger auto-submit
  Error shake: translateX oscillation (-8 → 8 → -4 → 4 → 0, 400ms)

Star Rating:
  Tap a star: stars to the left fill sequentially with 30ms stagger
  Filled star: warm gold, slight scale up, haptic per star
  Shake encouragement if left empty on submit attempt

Pull to Refresh:
  Custom refresh indicator: KiranaRush logo rotates 360° (not default spinner)
  Resistance: scroll beyond top with 0.5 pull factor
  Trigger threshold: 70px pull → haptic → logo spins → data loads
```

---

### 4. Screen-by-Screen UI Specification

#### 4.1 Splash Screen
```
Duration: 2.2s total
Background: Linear gradient: #0D0F1F → #1F2D55 (diagonal, 135deg)

Animation sequence:
  0ms:    Background renders instantly
  100ms:  Logo mark drops from y:-40 to y:0 with spring (opacity 0→1)
  350ms:  Brand name "KiranaRush" types character by character (30ms/char)
  800ms:  Tagline fades in: "आपका मोहल्ला, आपकी दुकान" (bilingual)
  1400ms: Subtle floating particles animate in background (grocery silhouettes)
  2200ms: Entire screen fades out → Role Selection

Design details:
  Logo: Bold "K" monogram with a subtle rider arc, orange on navy
  Tagline: 14px DM Sans, #9CA3AF (subdued, elegant)
  Particles: 8-12 tiny SVG silhouettes (bag, bottle, grain, leaf) floating slowly upward
```

#### 4.2 Role Selection Screen
```
Background: White (#FFFFFF) with subtle radial gradient from top center
Header: Back arrow (top left) + Step indicator dots (top right)

Title block:
  "I am a..." — 28px Plus Jakarta Sans ExtraBold, #111827
  "Choose your role to get started" — 14px DM Sans, #6B7280

Role Cards (stacked vertically, full-width):
  Each card: 100% width, height auto (~110px), border-radius 20px
  Internal layout:
    Left: Role emoji/icon in a 52×52 coloured rounded square
    Center: Role name (18px bold) + description (13px, 2 lines max)
    Right: Chevron icon (24px, #D1D5DB)
    
  Customer card:
    Icon bg: #FFF0EC | Icon: 🛒 shopping bag | Emoji colour: #FF5733
    Title: "Customer"
    Description: "Discover and order from local kirana stores near you"
    
  Rider card:
    Icon bg: #F0FDF4 | Icon: 🛵 scooter | Emoji colour: #16A34A
    Title: "Delivery Rider"
    Description: "Earn money delivering orders in your neighbourhood"
    
  Shop Owner card:
    Icon bg: #EFF6FF | Icon: 🏪 store | Emoji colour: #2563EB
    Title: "Shop Owner"
    Description: "List your kirana store and start receiving orders"

Selected state:
  Card border changes: 1px #E5E7EB → 2px #FF5733
  Card background: White → very subtle #FFF8F6
  Icon square gets a soft drop shadow
  Right chevron replaced with filled orange checkmark
  scale(1.01) spring animation on selection

Cards animate in on mount:
  Stagger: 0ms, 80ms, 160ms delays per card
  Each: translateY(20px) → 0 + opacity 0 → 1 (300ms --ease-smooth)

Bottom:
  Primary button "Continue →" appears after selection (fade in)
  Already have account? → Login (text link, centered, below button)
```

#### 4.3 Authentication Screens (Login + Registration)

**Login Screen Layout:**
```
Top 35%: Illustration area
  - Role-specific illustration (customer: shopping bag floating, rider: scooter, owner: store front)
  - Subtle gradient background matching role colour
  - Role name badge: "Customer Login" / "Rider Login" / "Shop Owner Login"
  - Rounded bottom corners on illustration container (border-radius: 0 0 32px 32px)

Bottom 65%: Form area (white, rounded top corners 32px)
  Title: "Welcome back 👋" — 26px ExtraBold
  Subtitle: "Sign in to continue" — 14px #6B7280

  Tab switcher:
    [ Phone ] [ Email ]
    Animated underline slides between tabs (--ease-spring, 200ms)
  
  Phone tab:
    +91 flag prefix dropdown (auto-detected) + 10-digit input
    "Send OTP" primary button → transitions to OTP screen
  
  Email tab:
    Email input with envelope icon (left-adornment)
    Password input with eye toggle (right-adornment, show/hide)
    "Forgot password?" → right-aligned text link, 12px
    "Sign In" primary button

  ─── OR ───  (styled divider with social login below)
  
  Google login button:
    White card, Google logo SVG, "Continue with Google" — 15px Medium
    Border: 1px #E5E7EB | Shadow: --shadow-sm

  Bottom: "New user? Create Account" — centered, text link

  Keyboard behaviour:
    Screen scrolls to keep active field visible
    "Next" key moves to next field
    "Done" key on last field triggers primary action
```

**OTP Screen:**
```
Header: Back arrow, "Verify Phone" title, progress (Step 2 of 2)

Illustration: Animated phone icon with signal waves
Main text: "OTP sent to +91 98765 43210"
Sub text: "Enter the 6-digit code" (tap number to edit)

OTP boxes:
  6 individual boxes, each 48×56px, border-radius 12px
  Border: 1.5px #E5E7EB | Active border: 1.5px #1A1A2E
  Font: 24px JetBrains Mono Bold, centered
  Spacing: 8px gap between boxes
  Auto-advance to next box on digit entry
  Backspace on empty box focuses previous

Resend OTP:
  "Didn't receive it? Resend in 00:45"
  Countdown timer in orange, ticks down
  After 0: "Resend OTP" becomes tappable link
  Max 3 resends before cooldown

Auto-submit: When all 6 digits filled, verify triggers automatically
  Loading state: Boxes show subtle shimmer, no interaction
  Error state: Boxes shake + turn red, counter decrements, refocuses first box
  Success state: Boxes turn green for 300ms → next screen
```

**Multi-Step Registration — Progress UI:**
```
Top bar for all registration screens:
  Back arrow (left) | Step pill: "2 of 4" (center) | Skip? (right, only on optional steps)
  
  Progress bar below top bar:
    Thin 3px bar, full width
    Filled portion: #FF5733
    Unfilled: #E5E7EB
    Animated fill: width transition on step advance (400ms ease)

Step transitions:
  Advance: current slides left + fades (200ms), next slides in from right (250ms)
  Back: reverse direction
```

#### 4.4 Shop Owner — Store Location Step (Most Critical Step)
```
Full-screen Google Map view:
  Status bar: translucent, dark content
  Map fills entire screen (no padding)

Top floating card (over map):
  Frosted glass: background rgba(255,255,255,0.92), blur(20px)
  Border-radius: 0 0 20px 20px (attached to top)
  Content: Step indicator + "Pin your store location"
  Sub: "Drag the map to reposition the pin"

Center pin:
  Custom SVG pin: store/shop icon at tip
  When dragging: pin lifts up (translateY -8px), shadow grows (shadow-lg)
  When released: pin drops with spring bounce, shadow shrinks
  Pin colour: #FF5733 (brand orange)

Bottom card (slides up from bottom, 50% screen height):
  Handle indicator (pill shape, gray, centered at top)
  Draggable — pull up for full-screen address details
  
  Address preview (auto-reverse-geocoded):
    Icon: location pin (16px)
    Text: "Plot 45, 5th Cross, Koramangala..."
    Sub: "Bengaluru, Karnataka — 560034"
  
  Input: "Fine-tune address" (optional manual edit)
  
  Location accuracy indicator:
    Circle on map shows GPS accuracy radius
    Text: "Accuracy: ±8 meters" (green if <15m, yellow if >15m)
  
  "Use This Location" primary button:
    Disabled until accuracy < 50m OR user manually confirmed
    Loading: "Locating..." with spinner
    
  "Search for address instead" text link below

Map controls (floating, right side):
  My location button (44px circle, white, shadow-md)
  Zoom in / Zoom out (stacked, same style)
```

#### 4.5 Shop Owner Dashboard

```
Header bar:
  Left: Avatar (36px circle) + "Hello, Rajesh 👋" — 16px Medium
  Center: Store name in compact logo treatment
  Right: Bell icon (notification badge count) + Open/Closed live toggle

  Open/Closed Toggle (prominent, top right):
    Pill toggle: 72×32px
    On (Open): Background #16A34A, thumb right, label "OPEN"
    Off (Closed): Background #9CA3AF, thumb left, label "CLOSED"
    Transition: 200ms spring
    Haptic: medium on toggle
    Confirmation modal if turning off during active orders

Stats Strip (horizontal scroll, below header):
  4 stat cards, each ~140px wide, height 88px
  Slightly elevated with shadow-sm
  ┌──────────────────┐
  │  📦  Today       │
  │  14 Orders       │
  │  +3 vs yesterday │
  └──────────────────┘
  Stats: Today's Orders | Today's Revenue | Pending | Avg Rating
  Revenue: "₹3,240" in 22px ExtraBold
  Delta: Small arrow + %, colored green/red

Tab Navigation (icon + label, bottom of screen):
  Orders | Products | Analytics | Account
  Active tab: orange underline + icon fill + label bold
  Inactive: gray icon + gray label
  Badge on Orders tab if pending orders > 0

── Orders Tab ─────────────────────────────────────────────────

  Filter chips row (horizontal scroll):
    [ All (14) ] [ Pending (3) ] [ Preparing (2) ] [ Ready (1) ] [ Completed ]
    Active chip: orange fill, white text
    Inactive chip: #F3F4F6 background, #374151 text

  Order cards (vertical list):
    ┌──────────────────────────────────────────────┐
    │ #KR-1047          14 min ago    [● Pending]  │
    │ Priya Sharma  •  3 items  •  ₹485 COD        │
    │ ─────────────────────────────────────────── │
    │ Amul Butter 500g × 2  |  Bread × 1           │
    │ ─────────────────────────────────────────── │
    │ [✗ Decline]              [✓ Confirm Order]   │
    └──────────────────────────────────────────────┘
    
    Status badge colours per state:
      Pending:   Orange pill
      Confirmed: Blue pill
      Preparing: Amber pill
      Ready:     Green pill
      Completed: Gray pill

    Swipe actions on card:
      Swipe left → reveals red "Decline" action
      Swipe right → reveals green "Confirm" action (if pending)

    New order animation:
      Card slides in from top with orange left-border flash (3 pulses)
      Haptic: notification pattern
      Sound: optional ding (respects device silent mode)

── Products Tab ───────────────────────────────────────────────

  Top controls:
    Search bar (full width, 46px height)
    Below: Category filter chips (horizontal scroll)
    View toggle: Grid (2-col) / List — top right

  Grid view product card (2 columns, 16px gap):
    ┌───────────────┐
    │ [Image 1:1]   │   ← aspect ratio enforced, object-fit cover
    │ ───────────── │
    │ Amul Butter   │   ← 14px SemiBold, max 2 lines
    │ 500g          │   ← 12px gray
    │ ₹265  ~~280~~ │   ← Price bold, MRP strikethrough, 5% off chip
    │ Stock: 24     │   ← 11px, green if >10, amber if 3-10, red if <3
    │ ──────●────── │   ← Available toggle
    └───────────────┘
    Long press → context menu: Edit / Duplicate / Delete / Toggle availability

  List view product card (single column):
    [56×56 image] | [Name + unit] | [Price] | [Stock] | [Toggle] | [⋮ menu]

  FAB (Floating Action Button):
    Position: bottom-right, 88px from bottom (above tab bar)
    Size: 56×56px, border-radius full
    Background: #FF5733, Shadow: --shadow-float
    Icon: + (24px, white)
    Label: "Add Product" — expands on first tap (Zomato-style extended FAB)
    Press: scale(0.92) + haptic

  Add/Edit Product Bottom Sheet (full-height modal):
    Handle + "Add Product" / "Edit Product" title + "Save" text button (top right)
    
    Image section (top):
      Large dashed border area (aspect-ratio 1:1, border-radius 16px)
      Center: Camera icon + "Tap to add photo"
      After image added: Full preview with "Change" overlay on tap
      Support: Camera / Gallery / Auto-cropper (1:1 crop enforced)
    
    Form fields (scrollable):
      Product Name* — full-width text input
      Category* — dropdown (sheet picker, grid of categories with icons)
      Description — multiline input, 3 lines visible, expandable
      
      Price row (2 columns):
        ₹ Price*  |  ₹ MRP (optional)
        Auto-calculated discount % shown below: "24% off" in green badge
      
      Unit* — custom picker: g / kg / L / mL / piece / pack / dozen
      Stock Quantity* — number input with +/- controls
      
      Availability toggle:
        Large switch with label "Currently Available"
        Sub: "Turn off to temporarily hide from customers"
      
    Save button: Sticky at bottom, full-width primary button
    
── Analytics Tab ──────────────────────────────────────────────

  Period selector: [ Today ] [ This Week ] [ This Month ] [ Custom ]
  
  Revenue chart:
    Bar chart (Today: hourly | Week: daily | Month: weekly)
    Orange bars, hover/tap shows tooltip with exact ₹ amount
    Y-axis: auto-scaled with ₹ prefix
    X-axis: time labels
    
  Key metrics row (2×2 grid of stat cards):
    Orders Completed | Revenue | Avg Order Value | Ratings (avg)
    
  Top Products list:
    Rank | Image | Name | Units Sold | Revenue
    Top 3 get medal emojis 🥇🥈🥉
    
  Peak Hours heatmap:
    7-column (days) × time blocks grid
    Color intensity: light → orange (low → high orders)
    
── Account Tab ────────────────────────────────────────────────

  Store profile card:
    Store image (banner aspect ratio 3:1) with camera icon overlay to change
    Below: Store name | Category badge | Rating stars + count
    
  Edit sections (accordion-style, tap to expand):
    📍 Store Details (Name, Description, Category)
    📞 Contact Info (Phone, Email)
    ⏰ Store Timings (Time pickers, days of week toggle)
    📸 Store Images (Add more images, reorder, delete)
    📌 Location (Opens map picker — changes go to admin review)
    🏦 Bank Details (For future payouts)
    
  Critical change warning:
    Banner: "⚠️ Changing name or location requires admin re-approval (24-48 hrs)"
    
  Support & Legal:
    Help Center | Report an issue | Privacy Policy | Terms
    
  Logout (red destructive button, bottom, with confirmation dialog)
```

#### 4.6 Rider App — Home (Online/Offline State Machine)

```
OFFLINE STATE:
  Background: Dark navy (#1A1A2E) — signals "not working"
  Map: Desaturated / grayscale filter
  
  Center of screen:
    Rider avatar (large, 80px circle) with gray border
    Name: "Ravi Kumar"
    Status: "● Offline"
    
  Toggle card:
    Large card (white, bottom 30% of screen, rounded top 32px)
    Big ON/OFF toggle (iOS-style but 2× larger, 72×40px)
    Label: "Go Online to start earning"
    Sub: "You'll receive delivery requests in your area"
    Current earnings today: "₹0 earned today"
    
ONLINE STATE:
  Background: Rich map, fully saturated
  Rider pin: Animated orange bike pin in center
  
  Status bar (top, floating frosted-glass card):
    ● Online  |  10km radius  |  ⏱ 00:45:22 (time online)
    Subtle green pulsing dot on "Online"
    
  Side stats pill (right side, floating):
    ₹ 340   ← today's earnings (updates live)
    5 trips ← completed today
    
  Nearby stores panel (expandable bottom sheet):
    Collapsed (default): 120px visible — shows "3 stores in your area" + store logos
    Expanded: Full list of nearby approved stores
    
    Each store item:
      [Image 40×40] | Store name | Distance | Pending orders badge
      e.g. "Sharma Kirana  •  1.2km  •  2 pending orders"
      
  Offline toggle: Now a small pill in top-right of status bar (not prominent — discourages going offline)

ORDER REQUEST BOTTOM SHEET (slides up, 85% screen height):
  Backdrop: 60% opacity over map (blurs map, focuses attention)
  
  ── Sheet top ──
  Handle pill
  "New Delivery Request 🛒" — 18px ExtraBold
  
  ── Countdown timer (most prominent element) ──
    Circular countdown: large circle, 72px diameter
    Orange fill depletes clockwise (30s → 0s)
    Center: "24" (seconds remaining), 22px Mono Bold
    Haptic feedback at: 10s, 5s, 3s, 2s, 1s
    If expired: auto-declines, brief "Missed" animation, sheet slides down
    
  ── Trip details card ──
    Two-row route:
      [🏪 icon] Pickup: Sharma Kirana — 5th Cross Koramangala    1.2 km
      [📍 icon] Drop:   Koramangala 6th Block, near Jyothi Nivas  3.4 km
    Total distance: 4.6 km (shown below, smaller)
    
    Divider
    
    Items summary:
      4 items from 1 store
      Item thumbnails row: [img][img][img] +1 more
      
    Divider
    
    Estimated earnings:
      ₹45 base  +  ₹12 distance bonus  =  ₹57 total
      (Broken down clearly, riders understand how they earn)
      
  ── Actions ──
    Two buttons, side by side:
      [ ✗  Decline ]   (secondary, border style, white bg)
      [ ✓  Accept  ]   (primary, orange fill, larger)
    
    Decline confirmation: "Are you sure? Declining too often may reduce requests"
    
ACTIVE DELIVERY SCREEN:
  Map (full screen) with route overlay:
    Phase 1 (heading to store):
      Route: Rider → Store (blue line with turn arrows)
      Store marker: Animated store icon (bouncing softly)
      Rider marker: Moving bike icon (rotates per heading)
      
    Phase 2 (heading to customer):
      Route: Rider → Customer (orange line)
      Customer marker: Home/person icon
      
  Bottom action panel (slides up, ~40% height):
    ── Phase 1 content ──
    Store info: [image] Sharma Kirana  •  1.2km  •  ETA 8 min
    Divider
    Order summary (collapsible):
      [Expand] "4 items — tap to view"
      Expanded: item list with product names + quantities
    
    Map action row:
      [📞 Call Store]  [🗺 Open in Maps]
      
    "MARK AS PICKED UP" — full-width orange button
      Only activates when rider is within 200m of store (geo-fence)
      If outside range: "Get closer to the store to mark pickup"
      Disabled style: grayed out, with distance remaining: "180m away"
      
    ── On Pickup Confirmed: Phase 2 content ──
    Route updates to customer
    Customer info: [avatar] Priya Sharma  •  3.4km  •  ETA 18 min
    "[📞 Call Customer]" icon button
    
    OTP Section (bottom):
      "Ask customer for their OTP"
      6 boxes (same as auth OTP input)
      "COMPLETE DELIVERY" button → active only when valid OTP entered
      
    If OTP wrong: error shake + "Incorrect OTP. Ask customer to check their app"
    
RIDER EARNINGS SCREEN (Account/Profile tab):
  Header: Avatar | Name | Rating (stars) | Total deliveries
  
  Earnings summary card:
    Today: ₹340  |  This Week: ₹1,840  |  This Month: ₹7,200
    Bar chart below (7-day daily earnings)
    
  Trip history list:
    Each trip card:
      [Store icon → Customer icon] route visual
      Sharma Kirana → Koramangala 6th Block
      Date/time  |  Distance  |  Duration  |  ₹ earned
      Rating received: ⭐4  (if rated)
      
  Performance stats:
    Acceptance Rate: 87%  (animated ring chart)
    Completion Rate: 98%
    Avg Rating: 4.7/5
    
  Vehicle badge: "⚡ Electric Rider" or "⛽ Petrol Rider"
```

#### 4.7 Customer App — Home Feed (Most Complex Screen)

```
LOCATION BAR (sticky top):
  Left: Location pin icon (orange)
  Center: "Koramangala, Bengaluru ▾" — 15px SemiBold (tap to change)
  Right: 🔔 notification bell (badge if unread) + 🔍 search icon
  Background: white, shadow-sm when scrolled (none at top)
  
  Location change flow:
    Tapping opens fullscreen modal:
      Search bar (autofocused)
      "Use current location" option (GPS icon, orange)
      Recent locations list
      Map with draggable pin option
      Saved addresses: Home 🏠 | Work 💼 | + Add New

SEARCH EXPERIENCE:
  Tap search → screen slides over with search UI
  
  Default (no query):
    "Recent searches" (with ✕ to clear each)
    "Popular near you" — trending product names
    
  While typing:
    Real-time suggestions:
      - Product matches: [product image] "Amul Butter 500g" — Sharma Kirana
      - Store matches: [store image] "Green Basket Organics" — 2.1km
    Highlighted matching text in results
    
  Results screen:
    Filter row: Sort (Relevance/Distance/Rating) | Distance | Category | Open Now
    Mixed results: stores + products, clearly labelled
    Product result shows which store stocks it + add-to-cart button inline

HOME FEED (scrollable):
  
  ── Section 1: Hero Promo Banner ──
    Auto-scrolling carousel (swipe-enabled)
    Card: full-width, height 160px, border-radius 16px
    Background: rich gradient or store photo with overlay
    Text: Promo headline + CTA chip
    Indicator dots: tiny pills (active = wider orange pill, inactive = gray dot)
    Autoplay: 4s per slide, pauses on touch
    
  ── Section 2: Category Shortcuts ──
    Horizontal scroll of category pills with icons:
    [🥛 Dairy] [🍞 Bakery] [🥤 Beverages] [🌿 Organic] [🧴 Personal Care] [🍎 Fruits]
    Each: 64px circle icon + label below, background color-coded
    Tap → Pre-filtered store list
    
  ── Section 3: Stores Near You ──
    Section header: "Stores near you" (18px Bold) + "See all →" (link)
    Horizontal scroll of store cards:
    
    Store card (240px × 200px, vertical layout):
      [Store image — 240×110px, border-radius 12px top]
      [Content area — 16px padding]
        Row 1: Store name (15px SemiBold, truncated 1 line) + ⭐ 4.2 rating (right)
        Row 2: Category badge + distance — "1.2 km away"
        Row 3: "30-45 min" ETA + delivery fee OR "Free delivery"
        Row 4: [Open Now 🟢] OR [Opens at 9:00 AM 🔴] badge
    
    Sorting logic: Open stores first, then by distance
    Sponsored stores: subtle "Ad" pill, can be filtered out
    
  ── Section 4: Quick Picks (popular products) ──
    Section header: "Order again" — shows repeat items
    OR "Popular near you" for new users
    
    Horizontal scroll of product cards (140×180px):
      [Product image — square, object-fit contain on white bg]
      [Brand/store name — 11px gray, truncated]
      [Product name — 13px SemiBold, 2 lines max]
      [Price — 15px Bold orange]
      [+ Add button — full width, 32px, small orange button]
      
    Add button: Morphs to [ − 1 + ] inline on tap (no navigation)
    
  ── Section 5: "Order Again" (returning users) ──
    Past order cards: [Store image] + "Order again from Sharma Kirana" + item count
    CTA: "Reorder" chip — populates cart with same items, user confirms
    
  ── Section 6: Explore by Store (all nearby stores, paginated) ──
    Vertical list (for user to scroll and discover)
    Each store: horizontal card (full width, 100px height)
      [80×80 image] | [Name + Category + Distance + Rating] | [Open badge]

STORE DETAIL SCREEN:
  
  ── Hero Section ──
    Store banner image: full-width, height 220px
    Parallax: image scrolls at 0.5× speed as user scrolls down
    Gradient overlay: bottom 50% → black (for text readability)
    Over image (bottom-left):
      Store name — 22px ExtraBold, white
      ⭐ 4.2  (847 reviews)  •  1.2km  •  Grocery

  ── Store Info Bar ──
    White bar, sticky after hero scrolls past
    Row 1: Open status badge | Timing: "9:00 AM – 10:00 PM"
    Row 2: 📞 Call | ℹ️ Info | ❤️ Save store — icon action row
    
  ── Search Within Store ──
    Full-width search bar: "Search in Sharma Kirana"
    
  ── Category Chips ──
    Horizontal scroll, sticky below search when scrolling:
    [ All ] [ Dairy ] [ Snacks ] [ Beverages ] [ Staples ] [ Personal Care ]
    Active chip: orange fill | Inactive: gray border
    
  ── Product Grid ──
    2-column grid (16px gap, 16px horizontal padding)
    
    Product card (detailed):
      Image: square, 100%, aspect-ratio 1:1, border-radius 12px
        Low-stock ribbon: diagonal "Only 3 left!" in red (if stock ≤ 3)
        Out of stock overlay: gray overlay + "Out of Stock" center text
      
      Content (12px padding below image):
        Brand name: 10px, #9CA3AF, uppercase tracking-wider
        Product name: 13px SemiBold, max 2 lines, ellipsis
        Weight/unit: 11px, #6B7280
        
        Price row:
          ₹265 (15px Bold, #111827)
          ~~₹280~~ (12px, line-through, #9CA3AF)
          5% OFF (green badge, 10px)
          
        Add button:
          Default: "+ Add" (32px tall, full-width, orange border, orange text)
          Added: "− 2 +" (same dimensions, orange fill, white text, quantity number)
          Transition: 200ms spring morph
          
    Out-of-stock cards: full grayscale filter, no add button, "Notify me" link
    
  ── Sticky Footer ──
    Appears when cart has items from this store:
    White card, shadow-xl, safe-area-bottom padding
    "🛒  2 items   |   View Cart   ₹530"
    Tapping navigates to cart

CART SCREEN:
  
  Header: "Your Cart" (20px Bold) + item count badge
  
  ── Multi-store grouping ──
    Each store group:
      Store header: [Store image 36px] Store name (16px SemiBold) | [✕ Remove all]
      
      Item rows:
        [Product image 64×64] | [Name + unit] | [Qty controls: − Q +] | [Price]
        Price: 14px Bold (right aligned)
        Qty: − and + buttons (28px circles, border, orange on active)
        
      Store subtotal: right-aligned, 14px SemiBold
      Divider (dashed, 1px #E5E7EB)
      
  ── Savings summary ──
    "You're saving ₹45 on this order 🎉" — green banner, centered
    
  ── Delivery info ──
    Address row: 📍 "Flat 5A, Prestige Shantiniketan..." | Change
    Estimated time: "40-55 min estimated delivery"
    
  ── Bill Summary (expandable) ──
    Item total:        ₹795
    Discount:         −₹45
    Delivery fee:      ₹40
    Platform fee:       ₹5
    ─────────────────────────
    Total:            ₹795
    
    Savings: "Total savings: ₹45" (green, below total)
    
  ── Checkout button (sticky bottom) ──
    "Proceed to Pay  ₹795" — full-width primary orange button
    Height: 56px, margin: 16px horizontal, safe-area bottom padding

CHECKOUT SCREENS:
  
  Step 1 — Address:
    Map (40% screen height): delivery pin visible
    Address details below: full address + apartment/floor input
    Saved addresses toggle: Home | Work | + New
    Pin is draggable on map for fine-tuning
    
  Step 2 — Payment:
    Payment method cards:
      ┌──────────────────────────────────────┐
      │ 💳  Pay Online                       │
      │     UPI / Cards / Netbanking         │
      │     Razorpay — secure                │
      │                          ○ (radio)   │
      └──────────────────────────────────────┘
      ┌──────────────────────────────────────┐
      │ 💵  Cash on Delivery                 │
      │     Pay when you receive             │
      │     Max order ₹2,000 for COD         │
      │                          ○ (radio)   │
      └──────────────────────────────────────┘
    
    Coupon code field: [ Enter coupon code ] [Apply]
    Applied coupon: green checkmark + savings shown
    
    "Place Order  ₹795" — orange primary button
    
  Order Success Screen:
    Full-screen celebration:
    Background: white with confetti Lottie animation
    Center: Green checkmark Lottie (draws in over 600ms)
    
    "Order Placed! 🎉" — 28px ExtraBold
    "Order #KR-1047" — 14px Mono, gray
    "Estimated delivery: 40-55 min"
    
    Store confirmation chips: each store with ✓ confirmed / ⏳ pending
    
    "Track Order →" primary button
    "Continue Shopping" text link below

LIVE TRACKING SCREEN:
  
  Map (full screen):
    Custom map style: light, desaturated (Sarvam-inspired — elements pop over it)
    
    Markers:
      Home/delivery: Pulsing blue circle + house icon inside
      Store(s): Animated shop pin (orange, slight bounce)
      Rider: Custom orange bike SVG, rotates to match heading direction
        Trailing dots: faded path behind the rider (last 5 positions, fades out)
        
    Route:
      Solid line: completed path (gray)
      Dashed line: upcoming path (orange dashes)
      
    ETA chip: floating over map near destination: "~18 min"
    
  Bottom status sheet (drag up for more detail):
    
    Collapsed (120px visible):
      Order status in large text: "Rider is on the way 🛵"
      Progress bar: ●━━━━━━━━○ (rider position shown)
      
    Expanded (50% screen):
      Order status timeline:
        ✅ Order Placed — 2:34 PM
        ✅ Store Confirmed — Sharma Kirana
        ✅ Rider Assigned — Ravi Kumar
        🔄 Rider heading to store
        ⬜ Order Picked Up
        ⬜ Out for Delivery
        ⬜ Delivered
      
      Rider card:
        ┌────────────────────────────────────────┐
        │ [Rider photo 48px] Ravi Kumar          │
        │ ⭐ 4.8  •  Hero Electric Optima        │
        │ KA01 XY 1234      (vehicle number)     │
        │             [📞 Call]  [💬 Message]    │
        └────────────────────────────────────────┘
      
      Order summary (tap to expand):
        "4 items from Sharma Kirana"
        
    OTP reveal (when rider arrives — push notification + screen):
      Full-screen interrupt:
        "Your rider is here! 🛵"
        "Share this code with them:"
        "847291" — huge 48px JetBrains Mono, centered
        "Do not share with anyone else"
        [Copy Code] button

RATING SCREEN (post-delivery):
  
  Appears automatically after delivery confirmation (5-second delay)
  Cannot skip (but can dismiss after 3s with reduced rating nudge)
  
  Header: "How was your delivery? 🌟"
  
  Rider rating:
    Rider photo (72px) + Name
    5 large star buttons (48px each, 8px gap)
    Stars fill gold left-to-right as tapped
    Below stars: contextual text based on rating:
      1★: "What went wrong? We'll fix it."
      3★: "Tell us more — we'll improve"
      5★: "Awesome! Ravi will be happy 😊"
      
  Per-store rating (each store as a card):
    [Store image 40px] Sharma Kirana — 5 stars
    [Store image 40px] Green Basket — 5 stars
    
  Comment box: "Anything else? (optional)" — 3-line multiline
  
  [Submit Ratings] — primary orange button
  [Skip for now] — tiny text link, only visible after 5s
  
  Post-submit: Brief success animation + redirect to home
```

---

### 5. Empty States, Error States & Edge Cases

#### 5.1 Empty States (Never a blank screen)
```
No stores nearby:
  Illustration: Cute kirana store building with a question mark
  Title: "No stores in your area yet"
  Sub: "We're growing fast! Check back soon or explore nearby."
  CTA: "Expand search radius" button

No products in store:
  Illustration: Empty shelf with dust particles
  Title: "This store hasn't added products yet"
  Sub: "Check back soon — they're setting up!"

Empty cart:
  Illustration: Empty bag with a small tumbleweed
  Title: "Your cart is empty"
  Sub: "Discover fresh items from local kirana stores"
  CTA: "Explore Stores" button

No order history:
  Illustration: Order receipt with a clock
  Title: "No orders yet"
  Sub: "Your first order from a local store is just a tap away"

Rider — no deliveries yet:
  Illustration: Rider waiting under a street light
  Title: "Waiting for your first order..."
  Sub: "Stay online and we'll notify you as soon as there's a delivery nearby"
  Animation: Gentle pulsing glow on the rider illustration

No internet:
  Illustration: Broken signal icon
  Title: "You're offline"
  Sub: "Check your connection and try again"
  CTA: "Retry" button (with spinning animation while retrying)
```

#### 5.2 Loading States
```
Every data-loaded component has a skeleton that exactly mirrors the content dimensions.

Home feed skeleton:
  Location bar: gray bar (140px × 16px)
  Hero banner: gray rect (full width × 160px), shimmer
  Category chips: 6 gray circles in a row
  Store cards: 2 gray cards (240×200px each), shimmer
  
Product grid skeleton:
  8 gray squares in 2-column grid, shimmer

Store detail skeleton:
  Hero image: full-width gray rect
  Title: gray bar (200px)
  Stats: 3 inline gray bars

All skeletons:
  Background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)
  Animation: background-position 0% → 100% (1.2s ease-in-out infinite)
  Border-radius matches content element
```

#### 5.3 Error Handling UI
```
Inline field errors:
  Red border on input
  Icon: ⚠ (16px, red) + error message below
  Error text: 12px DM Sans, #DC2626

Toast notifications (top of screen):
  Slide in from top, 3s auto-dismiss
  Types: Success (green), Error (red), Info (blue), Warning (amber)
  Each: Icon + message text + optional undo/retry action
  
Network error on API call:
  Overlay on the section that failed (not full screen)
  Icon: broken wifi
  "Couldn't load. Tap to retry" with retry button
  
Payment failure:
  Specific error message from Razorpay
  "Your payment failed. No money was deducted."
  [Try Again] or [Use COD instead] options
  
Delivery OTP wrong:
  OTP boxes shake (400ms)
  "Incorrect OTP — ask customer to check their app"
  Attempt counter: "2 attempts remaining"
  After 3 wrong → must call customer, "Call Customer" button appears
```

---

### 6. Accessibility & Inclusive Design

```
Touch Targets:
  Minimum: 44×44px for all interactive elements (WCAG 2.5.5)
  Recommended: 48×48px for primary actions
  
Text Contrast:
  Body text on white: ≥ 4.5:1 contrast ratio (WCAG AA)
  Large text (18px+): ≥ 3:1
  Orange (#FF5733) on white: test — if fails, darken to #E5431F for text use
  
Font Sizes:
  Minimum body text: 14px (DM Sans Regular)
  System font size: respect user's system font size settings (use sp not px in native)
  
Haptic Feedback:
  Light: button taps, selection
  Medium: toggle state changes, confirmations
  Heavy: errors, warnings, important alerts
  None: decorative animations (optional haptics in settings)
  
Screen Reader Support:
  All images: meaningful alt text
  Icons: accessibilityLabel on all icon buttons
  Dynamic content: announce live status changes
  OTP boxes: labeled "OTP digit 1 of 6", auto-announce digit entered
  
Language:
  Primary: English
  Recommended addition: Hindi (hi-IN) localization for tier 2/3 cities
  Numbers: Always use Indian number format (₹1,00,000 not ₹100,000)
  Dates: DD MMM YYYY format (15 Jan 2025)
  Distance: km (below 1km: show in metres — "850m")
  Time: 12-hour format with AM/PM for Indian users
  
Offline Behaviour:
  Cache: last-loaded home feed data for offline viewing
  Cart: persists locally (AsyncStorage/SQLite), syncs when back online
  Show: "Viewing cached content — connect to order" banner
```

---

### 7. Navigation Architecture

```
── Customer App ────────────────────────────────────────────────

Bottom Tab Bar (4 tabs):
  🏠 Home        — Feed, stores, search
  🧾 My Orders   — Active + history (badge count for active)
  🛒 Cart        — Cart view (badge = item count, pulsing if items > 0)
  👤 Profile     — Account, addresses, settings

Stack within Home tab:
  Home Feed → Store Detail → Product Detail (modal)
  Home Feed → Search Results → Store Detail

Stack within Orders tab:
  Order List → Order Detail → Live Tracking → Rating

── Rider App ───────────────────────────────────────────────────

Bottom Tab Bar (3 tabs):
  🗺 Deliveries  — Map + active delivery / waiting screen
  📊 Earnings    — Stats, trip history
  👤 Profile     — Personal info, vehicle, settings

── Shop Owner App ──────────────────────────────────────────────

Bottom Tab Bar (4 tabs):
  📦 Orders      — Incoming + history (badge = pending count)
  🛒 Products    — Product CRUD
  📊 Analytics   — Revenue charts
  👤 Account     — Store details, settings

── Global Elements ─────────────────────────────────────────────

Notification center: Slide in from right (full-height drawer)
  Grouped by: Today | Yesterday | This Week
  Each notification: Icon + title + body + time
  Tap → navigates to relevant screen

Settings (from Profile):
  Account | Notifications | Privacy | Help | About | Logout
```

---

### 8. Dark Mode Specification

```
All screens support dark mode (system-preference aware):

Dark mode palette:
  Background:      #0D0F1F   ← Deep navy (brand-consistent, not pure black)
  Surface:         #1A1A2E   ← Card backgrounds
  Surface-raised:  #1F2D55   ← Elevated cards, bottom sheets
  Border:          #2D3748   ← Dividers, card borders
  Text-primary:    #F9FAFB   ← Main text
  Text-secondary:  #9CA3AF   ← Helper text, captions
  Text-disabled:   #4B5563   ← Disabled states

  Accent (unchanged):  #FF5733   ← Same orange in dark mode
  Success (adjusted):  #22C55E   ← Same (reads well on dark)
  
Cards in dark mode:
  Subtle glow instead of shadow: box-shadow: 0 0 0 1px #2D3748

Map in dark mode:
  Use Google Maps' "night" style (dark map tiles)
  Custom style JSON to match navy palette

Transitions:
  Colour changes when toggling mode: 200ms transition on all colour properties
  Respects system "auto dark mode" — no in-app toggle needed (optional addition)
```

---

### 9. Onboarding Experience (First Launch Only)

```
3-screen onboarding carousel (skip-able from screen 1):

Screen 1: "Order from your local Kirana"
  Illustration: Warm neighbourhood street scene, illuminated store
  Body: "Shop fresh groceries, daily essentials, and more from trusted local stores"
  
Screen 2: "Fast delivery by local riders"
  Illustration: Friendly rider on electric scooter
  Body: "Dedicated riders deliver your order in under an hour — track them live"
  
Screen 3: "Support your neighbourhood"
  Illustration: Money flowing from phone → rider → store → community
  Body: "Every order supports a local shopkeeper and an independent rider"
  
Each screen:
  Illustration: Lottie animation (looping, 3-5s)
  Swipe left/right to advance
  Dots indicator at bottom
  "Get Started" → Registration / Login screen on screen 3
  
After onboarding: Not shown again (flag stored locally)
```

---

---

## 🔐 Authentication System — Full Redesign

### Design Notes
- **Single unified auth screen** with role switcher — not separate apps
- Glassmorphism card on a rich gradient background (deep navy → warm orange mesh)
- Animated role pill selector at top: `[ Customer ] [ Rider ] [ Shop Owner ]`
- Social login options (Google OAuth via `django-allauth`) + phone/OTP option
- Smooth cross-fade between Login ↔ Register forms

### Auth Screens

#### 1. Welcome / Splash
```
- App logo animation (logo drops in, text types out)
- Tagline: "Your neighbourhood, delivered."
- CTA: "Get Started" → Role Selection
- Background: animated gradient with floating kirana item silhouettes
```

#### 2. Role Selection Screen
```
Three large cards, tap to select:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  🛒 Customer    │  │  🛵 Rider       │  │  🏪 Shop Owner  │
│  Order from     │  │  Deliver &      │  │  List your      │
│  local stores   │  │  earn money     │  │  Kirana store   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
Selected card: border glows with accent colour, slight scale-up (1.03)
```

#### 3. Login Screen (all roles share this)
```
- Phone number input (Indian format, +91 prefix auto-filled)
- OR Email + Password
- "Send OTP" button for phone login
- OTP screen: 6-box animated input (auto-focus next, auto-submit on last)
- "Forgot Password" → email reset flow
- "New here? Create Account" link
```

#### 4. Registration Flow — Customer
```
Step 1: Name + Email + Phone + Password
Step 2: Location Permission prompt (illustrated, explains why)
Step 3: Profile photo (optional)
→ Redirects to Home Feed
```

#### 5. Registration Flow — Shop Owner (Multi-step wizard)
```
Step 1 — Account Details
  • Full Name
  • Email + Phone
  • Password + Confirm

Step 2 — Store Location
  • "Use My Current Location" button (Google Maps SDK)
  • Map preview showing pinned location
  • Manual address fine-tuning (drag pin)
  • Auto-populated: City, State, Pincode

Step 3 — Store Details
  • Shop Name (text)
  • Category (Grocery / General / Dairy / Organic / etc.)
  • Full Address (pre-filled from map, editable)
  • GSTIN (optional)
  • Phone Number (store contact)
  • Store Timings (open/close time picker)
  • Store Image (camera/gallery, cropped to 4:3)

Step 4 — Review & Submit
  • Preview card of how store will look to users
  • "Submit for Approval" CTA
  → Status: Pending Admin Approval
  → Redirect to: Pending Approval screen (with illustration + "We'll notify you" message)
```

#### 6. Registration Flow — Rider (Multi-step wizard)
```
Step 1 — Personal Details
  • Full Name
  • Age (must be 18+, validated)
  • Phone + Email
  • Password

Step 2 — Vehicle Details
  • Vehicle Type: [ ⚡ Electric ] [ ⛽ Petrol ] (toggle cards)
  • Vehicle Number (text)
  • Vehicle Model (text)

Step 3 — Documents & Photo
  • Profile Photo (mandatory — camera/gallery)
  • Aadhar / DL number (for verification)
  • Upload DL Photo

Step 4 — Review & Submit
  → Status: Under Review
  → Redirect to: Pending Approval screen
```

---

## 🛠️ Django Backend Architecture

### Tech Stack
```
Backend:       Django 4.2+ with Django REST Framework (DRF)
Auth:          djangorestframework-simplejwt + django-allauth (Google OAuth)
Database:      PostgreSQL (with PostGIS extension for geospatial queries)
Maps:          Google Maps Platform (Geocoding, Places, Directions, Maps JS/SDK)
Real-time:     Django Channels + Redis (WebSockets for live tracking & notifications)
Payments:      Razorpay Python SDK
File Storage:  AWS S3 or Cloudinary (store/product/rider images)
Push Notifs:   Firebase Cloud Messaging (FCM)
Task Queue:    Celery + Redis (async tasks: notifications, OTP, emails)
OTP:           Twilio or MSG91 (SMS OTP)
Cache:         Redis
Search:        Django's ORM + PostGIS `ST_DWithin` for radius queries
```

### Django App Structure
```
kiranaRush/
├── config/                  # settings, urls, wsgi, asgi
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   └── urls.py
├── apps/
│   ├── accounts/            # User model, Auth, Roles
│   ├── stores/              # Store model, CRUD, approval
│   ├── products/            # Product model, categories, inventory
│   ├── orders/              # Order, OrderItem, multi-store cart
│   ├── riders/              # Rider model, availability, radius
│   ├── delivery/            # Delivery assignment, live tracking
│   ├── payments/            # Razorpay integration, COD
│   ├── notifications/       # FCM, in-app notifications
│   ├── admin_panel/         # Custom admin for approvals
│   └── reviews/             # Ratings for riders and stores
├── core/                    # Shared utilities, mixins, permissions
└── requirements/
    ├── base.txt
    ├── development.txt
    └── production.txt
```

### Database Models (Key)

#### CustomUser
```python
class CustomUser(AbstractUser):
    ROLE_CHOICES = [('customer', 'Customer'), ('rider', 'Rider'), ('shop_owner', 'Shop Owner'), ('admin', 'Admin')]
    role = CharField(choices=ROLE_CHOICES)
    phone = CharField(unique=True)
    profile_photo = ImageField()
    is_phone_verified = BooleanField(default=False)
    fcm_token = CharField()  # For push notifications
    created_at = DateTimeField(auto_now_add=True)
```

#### Store
```python
class Store(Model):
    owner = ForeignKey(CustomUser)
    name = CharField()
    category = CharField()
    description = TextField()
    phone = CharField()
    address = TextField()
    location = PointField()           # PostGIS Point (lat, lng)
    city = CharField()
    state = CharField()
    pincode = CharField()
    image = ImageField()
    gstin = CharField(blank=True)
    opening_time = TimeField()
    closing_time = TimeField()
    is_open = BooleanField(default=True)
    approval_status = CharField(choices=['pending', 'approved', 'rejected'])
    rejection_reason = TextField(blank=True)
    rating = DecimalField()           # Avg rating
    total_orders = IntegerField(default=0)
    created_at = DateTimeField(auto_now_add=True)
```

#### Product
```python
class Product(Model):
    store = ForeignKey(Store)
    name = CharField()
    description = TextField()
    category = CharField()            # e.g. 'Dairy', 'Snacks', 'Beverages'
    price = DecimalField()
    mrp = DecimalField()              # Show discount %
    unit = CharField()                # '500g', '1L', '1 piece'
    image = ImageField()
    stock = IntegerField()
    is_available = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

#### Rider
```python
class Rider(Model):
    user = OneToOneField(CustomUser)
    age = IntegerField()
    vehicle_type = CharField(choices=['electric', 'petrol'])
    vehicle_number = CharField()
    vehicle_model = CharField()
    license_number = CharField()
    license_photo = ImageField()
    aadhar_number = CharField()
    current_location = PointField(null=True)   # Updated live via WebSocket
    is_available = BooleanField(default=False)
    approval_status = CharField(choices=['pending', 'approved', 'rejected'])
    base_radius_km = IntegerField(default=10)
    extended_radius_km = IntegerField(default=15)  # Auto-expanded when riders scarce
    rating = DecimalField()
    total_deliveries = IntegerField(default=0)
    created_at = DateTimeField(auto_now_add=True)
```

#### Order
```python
class Order(Model):
    STATUS = ['placed', 'confirmed', 'preparing', 'ready', 'rider_assigned',
              'picked_up', 'in_transit', 'delivered', 'cancelled']
    PAYMENT_METHOD = ['razorpay', 'cod']

    customer = ForeignKey(CustomUser)
    rider = ForeignKey(Rider, null=True)
    status = CharField(choices=STATUS, default='placed')
    payment_method = CharField(choices=PAYMENT_METHOD)
    payment_status = CharField(choices=['pending', 'paid', 'refunded'])
    razorpay_order_id = CharField(blank=True)
    delivery_address = TextField()
    delivery_location = PointField()
    delivery_otp = CharField(max_length=6)        # 6-digit OTP for delivery
    subtotal = DecimalField()
    delivery_fee = DecimalField()
    total = DecimalField()
    estimated_delivery = DateTimeField(null=True)
    picked_up_at = DateTimeField(null=True)
    delivered_at = DateTimeField(null=True)
    created_at = DateTimeField(auto_now_add=True)

class OrderStore(Model):
    """Links an order to a specific store (multi-store support)"""
    order = ForeignKey(Order)
    store = ForeignKey(Store)
    store_status = CharField()  # per-store fulfillment status
    store_subtotal = DecimalField()

class OrderItem(Model):
    order_store = ForeignKey(OrderStore)
    product = ForeignKey(Product)
    quantity = IntegerField()
    price_at_order = DecimalField()  # Snapshot price at time of order
```

#### Delivery / Tracking
```python
class RiderLocation(Model):
    """Stores real-time rider location — updated via WebSocket"""
    rider = OneToOneField(Rider)
    location = PointField()
    updated_at = DateTimeField(auto_now=True)
    heading = FloatField(null=True)   # Direction in degrees

class Review(Model):
    order = ForeignKey(Order)
    reviewer = ForeignKey(CustomUser)   # customer reviewing rider/store
    rider = ForeignKey(Rider, null=True)
    store = ForeignKey(Store, null=True)
    rating = IntegerField()             # 1–5
    comment = TextField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

---

## 🏪 Shop Owner Flow (Post-Approval)

### Dashboard (Landing after login)
```
Top Bar: Store name | Live toggle (Open/Closed) | Notification bell
Stats Row: Today's Orders | Revenue | Pending | Avg Rating

Tabs:
├── 📦 Orders     — Incoming orders, status management
├── 🛒 Products   — Full product CRUD
├── 📊 Analytics  — Sales charts, top products, peak hours
└── 👤 Account    — Edit store details, bank info, logout
```

### Product CRUD UI
```
Product List:
- Search bar + Category filter chips
- Each product card: Image | Name | Price | Stock | Available toggle | [Edit] [Delete]
- FAB (Floating Action Button): "+ Add Product"

Add/Edit Product Form:
- Image picker (with cropping — 1:1 square)
- Name, Description, Category dropdown
- Price (₹), MRP (₹) — shows discount % auto-calculated
- Unit (dropdown: g, kg, L, mL, piece, dozen, pack)
- Stock quantity
- Available toggle
- Save → optimistic update in list
```

### Store Details Edit (Account Tab)
```
Editable: Store name, description, phone, timings, category, image
Location: "Update Location" → opens map picker
Changes to critical fields (name, location) go back for admin review
```

### Admin Approval for New Store / Changes
```
Admin Panel shows:
- Pending store registrations (card with all details + map preview)
- Approve / Reject (with rejection reason text)
- Pending store detail changes
On approval → FCM notification to shop owner: "Your store is now live! 🎉"
On rejection → FCM + rejection reason shown in app
```

---

## 🛵 Rider Flow (Post-Approval)

### Rider Home Screen
```
Top: "You're Online/Offline" toggle (large, prominent)
Map: Full-screen map showing their current location

Nearby Stores Panel (bottom sheet):
- List of approved stores within their radius
- Each store: Name, distance, pending orders count
- Radius indicator: "You're covering 10km radius"

Status: Waiting for orders...
→ Animated pulse on their pin on the map
```

### Order Notification
```
Push notification arrives + in-app bottom sheet pops up:
┌──────────────────────────────────────┐
│  🛒 New Delivery Request             │
│  Pickup: Sharma Kirana, 1.2km away   │
│  Drop: Koramangala 5th Block, 3.4km  │
│  Items: 4 items from 1 store         │
│  Estimated Earnings: ₹45             │
│  ⏱ Accept in: 30s [countdown timer] │
│  [ ✗ Decline ]    [ ✓ Accept ]      │
└──────────────────────────────────────┘
Timer: If not accepted in 30s → auto-decline, sent to next available rider
```

### Active Delivery Screen
```
Map showing: Rider pin → Store pin (Phase 1) → Customer pin (Phase 2)
Step 1: Navigate to store
  → "Mark as Picked Up" button (only visible at store, geo-fenced)
  → Confirmation: Show order items list before confirming pickup
Step 2: Navigate to customer
  → Live location shared with customer + store owner
  → "Request OTP from Customer" button
  → OTP input (6-digit) → validates against backend
  → "Complete Delivery" → Trip ends
Post-delivery: Rating prompt for the customer
```

### Radius Logic (Backend)
```python
# Celery task runs every 5 minutes
def adjust_rider_radius():
    for city in active_cities:
        active_riders = Rider.objects.filter(is_available=True, city=city).count()
        pending_orders = Order.objects.filter(status='placed', city=city).count()
        ratio = pending_orders / max(active_riders, 1)
        if ratio > 2:  # More orders than riders can handle
            Rider.objects.filter(city=city).update(base_radius_km=15)
        elif ratio > 3:
            Rider.objects.filter(city=city).update(base_radius_km=17)
        else:
            Rider.objects.filter(city=city).update(base_radius_km=10)
```

---

## 🛒 Customer Flow

### Home Screen
```
Header: Location bar (tap to change) | Search icon | Cart bubble (item count)
Banner: Promotional carousel (horizontal scroll, auto-play)

Section: "Stores Near You" (radius: 20km, PostGIS query)
  → Horizontal scroll of Store Cards:
     ┌───────────────────────────┐
     │ [Store Image]             │
     │ Sharma Kirana         ⭐4.2│
     │ Grocery • 1.2km away      │
     │ 30-45 min • Free delivery │
     │ [Open Now 🟢]             │
     └───────────────────────────┘

Section: "Quick Picks" — Popular products across nearby stores
Section: "Order Again" — Previous orders for repeat customers
```

### Store Detail Screen
```
Top: Store image (hero, parallax scroll)
Info: Name | Rating | Distance | Timings | Category
Search: Search within this store

Product Grid (or list toggle):
  Category chips: All | Dairy | Snacks | Beverages | ...
  Product Card:
  ┌─────────────────────────┐
  │ [Product Image]         │
  │ Amul Butter 500g        │
  │ ₹265  ~~₹280~~  5% off  │
  │          [ + Add ]      │
  └─────────────────────────┘
  Tapping + shows [ − 1 + ] quantity controls inline
```

### Multi-Store Cart
```
Cart groups items by store:
┌──────────────────────────────────────┐
│ 🏪 Sharma Kirana                     │
│   Amul Butter 500g × 2 = ₹530       │
│   Britannia Bread × 1 = ₹45         │
│                      Subtotal: ₹575  │
├──────────────────────────────────────┤
│ 🏪 Green Basket Organics             │
│   Alphonso Mangoes 1kg × 1 = ₹220   │
│                      Subtotal: ₹220  │
├──────────────────────────────────────┤
│ Delivery Fee: ₹40                    │
│ Total: ₹835                          │
│ [ Proceed to Checkout → ]            │
└──────────────────────────────────────┘
Note: One rider handles entire order across stores (sequential pickup)
```

### Checkout Flow
```
Step 1: Confirm Delivery Address
  → Map showing delivery pin (draggable)
  → Address label input (Home/Work/Other)
Step 2: Payment Method
  → [ 💳 Pay Online (Razorpay) ] [ 💵 Cash on Delivery ]
  → Razorpay: Opens SDK sheet (UPI / Cards / Netbanking / Wallets)
Step 3: Order Confirmation
  → Animated success screen (Lottie animation)
  → Show estimated delivery time
  → Order tracking CTA
```

### Live Order Tracking Screen
```
Full-screen map:
  📍 Your location (home icon)
  🏪 Store location(s) (shop icons, multiple if multi-store)
  🛵 Rider location (animated bike icon, updates every 5s via WebSocket)

Status Timeline (bottom sheet):
  ✅ Order Placed (2:34 PM)
  ✅ Store Confirmed (2:36 PM)
  ✅ Rider Assigned — Ravi Kumar on 🛵 Ather 450
  🔄 Rider heading to store...
  ⬜ Order Picked Up
  ⬜ Out for Delivery
  ⬜ Delivered

Rider Card (bottom):
  [Photo] Ravi Kumar ⭐4.8  |  📞 Call  |  💬 Message
  Hero Electric Optima • KA01 XY 1234
```

### OTP Delivery Verification
```
When rider arrives:
  Customer gets push notification: "Your rider is here! Share OTP: 847291"
  OTP displayed prominently on customer screen with big font
  Rider enters OTP on their screen to complete delivery
```

### Post-Delivery
```
Rating Screen (mandatory before seeing next order):
  Rate Rider: ⭐⭐⭐⭐⭐ (tap stars)
  Rate Each Store: (per store, quick tap)
  Optional comment field
  Submit → Home Feed
```

### Order History
```
List of past orders:
  Each card: Order date | Stores | Items count | Total | Status badge
  Tap → Order detail:
    - Items breakdown per store
    - Rider details + rating given
    - Delivery time taken
    - Re-order button
    - Download invoice
```

---

## 👮 Admin Panel (Django Admin + Custom Views)

### Custom Admin Dashboard
```
Stats Overview:
  Total Users | Active Stores | Active Riders | Today's Orders | Revenue

Approval Queues:
  ┌─ Pending Store Approvals (N) ─────────────────────┐
  │  [Store Card with full details + Map preview]      │
  │  [ ✗ Reject (reason) ]  [ ✓ Approve ]            │
  └────────────────────────────────────────────────────┘
  
  ┌─ Pending Rider Approvals (N) ─────────────────────┐
  │  [Rider Card: Photo, Age, Vehicle, DL]             │
  │  [ ✗ Reject ]  [ ✓ Approve ]                     │
  └────────────────────────────────────────────────────┘

Management:
  → All Users | All Stores | All Riders | All Orders
  → Manual radius override per city
  → Notification broadcast tool
  → Dispute resolution (flag orders, manage refunds)
```

---

## 🔴 Real-time WebSocket Events (Django Channels)

```python
# Consumer Groups
order_{order_id}         # Customer + Store + Rider all subscribe
rider_location_{order_id} # Rider location updates
store_dashboard_{store_id} # Store gets new order notifications
rider_pool_{city}         # New order broadcasts to available riders

# Events
ORDER_PLACED             → Notify store + broadcast to rider pool
RIDER_ACCEPTED           → Notify customer + store
RIDER_LOCATION_UPDATE    → Broadcast to customer (every 5s)
ORDER_PICKED_UP          → Notify customer + store
ORDER_DELIVERED          → Notify all parties, close WebSocket groups
```

---

## 💳 Razorpay Integration Flow

```
1. Customer clicks "Pay Online"
2. Backend: razorpay.order.create() → returns order_id
3. Frontend: Open Razorpay SDK with order_id
4. Customer pays → Razorpay sends webhook to /api/payments/webhook/
5. Backend verifies signature → marks order payment_status='paid'
6. Proceeds to order fulfillment flow
7. Refunds: Initiated from admin panel via razorpay.refund.create()
```

---

## 📱 API Endpoints (DRF)

```
/api/auth/
  POST  /register/         — Register (role-based, returns JWT)
  POST  /login/            — Login (phone+OTP or email+password)
  POST  /otp/send/         — Send OTP to phone
  POST  /otp/verify/       — Verify OTP
  POST  /token/refresh/    — Refresh JWT

/api/stores/
  GET   /                  — List stores (PostGIS radius filter: ?lat=&lng=&radius=20)
  POST  /                  — Create store (shop_owner only)
  GET   /{id}/             — Store detail
  PATCH /{id}/             — Update store (owner only)
  GET   /{id}/products/    — Products in store

/api/products/
  GET   /                  — List (filter: store, category, search)
  POST  /                  — Create (store owner only)
  GET   /{id}/             — Product detail
  PUT   /{id}/             — Update
  DELETE/{id}/             — Delete

/api/orders/
  POST  /                  — Place order (customer only)
  GET   /                  — List (filtered by role: customer sees own, store sees theirs)
  GET   /{id}/             — Order detail
  PATCH /{id}/status/      — Update status (role-gated)
  POST  /{id}/verify-otp/  — Rider verifies delivery OTP

/api/riders/
  GET   /available/        — Available riders near location
  PATCH /location/         — Update rider's live location
  PATCH /availability/     — Toggle online/offline

/api/payments/
  POST  /create-order/     — Create Razorpay order
  POST  /webhook/          — Razorpay payment webhook

/api/reviews/
  POST  /                  — Submit review
  GET   /rider/{id}/       — Rider's reviews
  GET   /store/{id}/       — Store's reviews

/api/admin/
  GET   /pending-stores/   — Pending approvals
  POST  /approve-store/    — Approve/reject store
  GET   /pending-riders/   — Pending rider approvals
  POST  /approve-rider/    — Approve/reject rider
```

---

## 📊 Order History — All Roles

### Customer History
```
- Order ID, date, time
- Store(s) ordered from
- Items with images, quantities, prices
- Rider name + rating given
- Delivery duration (placed → delivered)
- Payment method + amount
- Re-order button
```

### Store History
```
- All orders received (filterable by date, status)
- Revenue per day/week/month (chart)
- Top-selling products
- Rider who delivered each order
- Customer rating received
```

### Rider History
```
- All deliveries completed
- Per delivery: Store → Customer, distance, earnings, time taken
- Rating received per trip
- Total earnings (daily/weekly/monthly)
- Acceptance rate stat
```

---

## 🔔 Notification System (FCM)

| Event | Recipient | Message |
|---|---|---|
| New order placed | Store owner | "New order #1234 received! ₹575" |
| Order confirmed | Customer | "Your order is confirmed by Sharma Kirana" |
| Rider assigned | Customer + Store | "Ravi Kumar is on the way 🛵" |
| Order picked up | Customer | "Your order is picked up! ETA 15 min" |
| Rider nearby | Customer | "Your rider is 500m away!" |
| Delivered | Customer | "Order delivered! Rate your experience ⭐" |
| Approval | Shop Owner | "Your store KiranaRush listing is approved! 🎉" |
| Approval | Rider | "Welcome aboard! You can now accept deliveries 🛵" |
| Rejection | Shop/Rider | "Application update — see reason in app" |

---

## 🗺 Google Maps Integration Points

| Feature | Maps API Used |
|---|---|
| Store registration — pin location | Maps JS API + Geocoding |
| User sets delivery address | Maps JS API (draggable pin) |
| Nearby store search | PostGIS `ST_DWithin` (backend) |
| Live rider tracking | Maps JS API (marker updates) |
| Route display (rider path) | Directions API |
| Distance/ETA calculation | Distance Matrix API |
| Rider navigation | Deep link to Google Maps / Maps SDK |

---

## 🔒 Security Checklist

- [ ] JWT tokens with 15-min access + 7-day refresh rotation
- [ ] Role-based permissions on every API endpoint (DRF Permissions)
- [ ] Phone OTP for all registrations (prevents fake accounts)
- [ ] Razorpay webhook signature verification
- [ ] Delivery OTP (server-generated, 6-digit, 10-min expiry)
- [ ] Geo-fencing for pickup confirmation (rider must be within 200m of store)
- [ ] Rate limiting on OTP endpoints (max 3 attempts per 10 min)
- [ ] Admin approval gate for stores and riders
- [ ] HTTPS enforced, CORS configured for known domains only
- [ ] Sensitive data (Aadhar, DL) encrypted at rest

---

## 🚀 Suggested Development Phases

### Phase 1 — Foundation (Weeks 1–3)
- Django project setup, custom user model, JWT auth
- Store and product models + CRUD APIs
- Admin approval flow
- Basic React Native auth screens (redesigned)

### Phase 2 — Core Order Flow (Weeks 4–6)
- Order placement, multi-store cart
- Razorpay + COD integration
- Rider assignment algorithm
- Push notifications via FCM

### Phase 3 — Real-time (Weeks 7–9)
- Django Channels + Redis WebSocket setup
- Live rider location tracking
- Order status WebSocket events
- OTP delivery verification

### Phase 4 — Maps & Radius Logic (Weeks 10–11)
- Google Maps full integration (all touchpoints)
- Dynamic radius adjustment (Celery task)
- Distance-based store sorting

### Phase 5 — Polish & Launch (Weeks 12–14)
- Rating & review system
- Order history (all roles)
- Admin analytics dashboard
- Performance optimization, load testing
- Play Store / App Store submission

---

*Built for Bharat. Designed for the neighbourhood. Powered by Django.*

---

---

# 📋 PART 2 — Complete Page & Field Specification

---

## 🗺️ URL / Screen Route Map

### React Native Screen Routes

```
── AUTH STACK ─────────────────────────────────────────────────────────────────
  /splash                               Splash / launch screen
  /onboarding                           3-slide onboarding (first launch only)
  /role-select                          Choose: Customer / Rider / Shop Owner
  /login                                Login screen (role-aware)
  /login/otp                            OTP verification
  /login/forgot-password                Enter email for reset link
  /login/reset-password                 New password (from email deep link)

  /register/customer/step-1             Personal details
  /register/customer/step-2            OTP verification
  /register/customer/step-3            Location permission
  /register/customer/step-4            Profile photo (optional)

  /register/rider/step-1               Personal details
  /register/rider/step-2               OTP verification
  /register/rider/step-3               Vehicle details
  /register/rider/step-4               Documents & photo upload
  /register/rider/step-5               Review & submit

  /register/shop-owner/step-1          Account details
  /register/shop-owner/step-2          OTP verification
  /register/shop-owner/step-3          Store location (map)
  /register/shop-owner/step-4          Store details & images
  /register/shop-owner/step-5          Review & submit

  /pending-approval                     Pending approval holding screen
  /rejected                             Rejection screen with reason + reapply

── CUSTOMER STACK ─────────────────────────────────────────────────────────────
  HOME TAB:
  /home                                 Home feed
  /home/search                          Full-screen search
  /home/search/results                  Search results
  /home/location-picker                 Change delivery location
  /home/store/:storeId                  Store detail + products
  /home/store/:storeId/product/:id      Product detail modal
  /home/category/:slug                  Stores by category

  CART TAB:
  /cart                                 Cart (multi-store grouped)
  /cart/checkout                        Step 1 — Address
  /cart/checkout/payment                Step 2 — Payment method
  /cart/checkout/payment/razorpay       Razorpay SDK screen
  /cart/checkout/cod-confirm            COD confirmation modal
  /cart/checkout/success                Order success screen
  /cart/checkout/payment-failed         Payment failure screen

  ORDERS TAB:
  /orders                               All orders (active + history)
  /orders/:orderId                      Order detail
  /orders/:orderId/tracking             Live tracking map
  /orders/:orderId/otp                  OTP display (when rider arrives)
  /orders/:orderId/rate                 Post-delivery rating

  PROFILE TAB:
  /profile                              Profile home
  /profile/edit                         Edit personal info
  /profile/addresses                    Saved addresses list
  /profile/addresses/add                Add address (map picker)
  /profile/addresses/:id/edit           Edit address
  /profile/payment-methods              Saved UPI/cards
  /profile/notifications                Notification preferences
  /profile/help                         Help & support
  /profile/help/raise-ticket            Raise support ticket
  /profile/privacy                      Privacy settings
  /profile/about                        About KiranaRush

── RIDER STACK ────────────────────────────────────────────────────────────────
  /rider/home                           Map + online/offline toggle
  /rider/home/order-request             Incoming order sheet
  /rider/home/active-delivery           Active delivery navigation
  /rider/home/active-delivery/pickup    Pickup confirmation
  /rider/home/active-delivery/otp       Enter customer OTP
  /rider/earnings                       Earnings dashboard
  /rider/earnings/history               Full trip history
  /rider/earnings/trip/:tripId          Individual trip detail
  /rider/profile                        Profile home
  /rider/profile/edit                   Edit personal info
  /rider/profile/vehicle                Vehicle details
  /rider/profile/documents              View/update documents
  /rider/profile/bank                   Payout bank account
  /rider/profile/notifications          Notification preferences
  /rider/profile/help                   Help & support

── SHOP OWNER STACK ───────────────────────────────────────────────────────────
  /shop/orders                          Live + history orders
  /shop/orders/:orderId                 Order detail
  /shop/orders/history                  Order history with filters
  /shop/products                        Product list
  /shop/products/add                    Add product
  /shop/products/:id/edit               Edit product
  /shop/analytics                       Revenue dashboard
  /shop/analytics/products              Top products
  /shop/account                         Store profile
  /shop/account/edit                    Edit store details
  /shop/account/edit/location           Update location (triggers re-approval)
  /shop/account/timings                 Store timings
  /shop/account/images                  Manage images
  /shop/account/bank                    Bank details
  /shop/account/notifications           Notifications
  /shop/account/help                    Help
```

### Django API URL Patterns

```python
urlpatterns = [
  # AUTH
  path('api/auth/register/customer/',         RegisterCustomerView.as_view()),
  path('api/auth/register/rider/',            RegisterRiderView.as_view()),
  path('api/auth/register/shop-owner/',       RegisterShopOwnerView.as_view()),
  path('api/auth/login/',                     LoginView.as_view()),
  path('api/auth/login/google/',              GoogleOAuthView.as_view()),
  path('api/auth/otp/send/',                  SendOTPView.as_view()),
  path('api/auth/otp/verify/',                VerifyOTPView.as_view()),
  path('api/auth/token/refresh/',             TokenRefreshView.as_view()),
  path('api/auth/password/forgot/',           ForgotPasswordView.as_view()),
  path('api/auth/password/reset/',            ResetPasswordView.as_view()),
  path('api/auth/logout/',                    LogoutView.as_view()),

  # STORES
  path('api/stores/',                         StoreListCreateView.as_view()),
  path('api/stores/nearby/',                  NearbyStoresView.as_view()),
  path('api/stores/<uuid:id>/',               StoreDetailView.as_view()),
  path('api/stores/<uuid:id>/products/',      StoreProductsView.as_view()),
  path('api/stores/<uuid:id>/toggle-open/',   ToggleStoreOpenView.as_view()),
  path('api/stores/<uuid:id>/reviews/',       StoreReviewsView.as_view()),

  # PRODUCTS
  path('api/products/',                       ProductListCreateView.as_view()),
  path('api/products/<uuid:id>/',             ProductDetailView.as_view()),
  path('api/products/<uuid:id>/toggle/',      ToggleProductAvailabilityView.as_view()),
  path('api/products/search/',                ProductSearchView.as_view()),

  # ORDERS
  path('api/orders/',                         OrderListCreateView.as_view()),
  path('api/orders/<uuid:id>/',               OrderDetailView.as_view()),
  path('api/orders/<uuid:id>/status/',        UpdateOrderStatusView.as_view()),
  path('api/orders/<uuid:id>/cancel/',        CancelOrderView.as_view()),
  path('api/orders/<uuid:id>/verify-otp/',    VerifyDeliveryOTPView.as_view()),
  path('api/orders/<uuid:id>/rate/',          SubmitOrderRatingView.as_view()),
  path('api/orders/<uuid:id>/invoice/',       DownloadInvoiceView.as_view()),

  # CART
  path('api/cart/',                           CartView.as_view()),
  path('api/cart/items/',                     CartItemView.as_view()),
  path('api/cart/items/<uuid:id>/',           CartItemDetailView.as_view()),
  path('api/cart/clear/',                     ClearCartView.as_view()),
  path('api/cart/apply-coupon/',              ApplyCouponView.as_view()),

  # CHECKOUT & PAYMENTS
  path('api/checkout/validate/',              ValidateCheckoutView.as_view()),
  path('api/payments/create-order/',          CreateRazorpayOrderView.as_view()),
  path('api/payments/verify/',                VerifyRazorpayPaymentView.as_view()),
  path('api/payments/webhook/',               RazorpayWebhookView.as_view()),
  path('api/payments/cod/confirm/',           ConfirmCODOrderView.as_view()),
  path('api/payments/refund/',                InitiateRefundView.as_view()),

  # RIDERS
  path('api/riders/profile/',                 RiderProfileView.as_view()),
  path('api/riders/availability/',            UpdateRiderAvailabilityView.as_view()),
  path('api/riders/location/',                UpdateRiderLocationView.as_view()),
  path('api/riders/earnings/',                RiderEarningsView.as_view()),
  path('api/riders/trips/',                   RiderTripHistoryView.as_view()),
  path('api/riders/trips/<uuid:id>/',         RiderTripDetailView.as_view()),

  # ADDRESSES
  path('api/addresses/',                      AddressListCreateView.as_view()),
  path('api/addresses/<uuid:id>/',            AddressDetailView.as_view()),
  path('api/addresses/<uuid:id>/set-default/', SetDefaultAddressView.as_view()),

  # NOTIFICATIONS
  path('api/notifications/',                  NotificationListView.as_view()),
  path('api/notifications/<uuid:id>/read/',   MarkNotificationReadView.as_view()),
  path('api/notifications/read-all/',         MarkAllReadView.as_view()),
  path('api/notifications/fcm-token/',        UpdateFCMTokenView.as_view()),

  # ADMIN
  path('api/admin/stores/pending/',           PendingStoresView.as_view()),
  path('api/admin/stores/<uuid:id>/approve/', ApproveStoreView.as_view()),
  path('api/admin/riders/pending/',           PendingRidersView.as_view()),
  path('api/admin/riders/<uuid:id>/approve/', ApproveRiderView.as_view()),
  path('api/admin/orders/',                   AdminOrderListView.as_view()),
  path('api/admin/stats/',                    PlatformStatsView.as_view()),
  path('api/admin/broadcast/',               BroadcastNotificationView.as_view()),

  # SEARCH
  path('api/search/',                         GlobalSearchView.as_view()),
  path('api/search/suggestions/',             SearchSuggestionsView.as_view()),

  # REVIEWS
  path('api/reviews/',                        ReviewCreateView.as_view()),
  path('api/reviews/rider/<uuid:riderId>/',   RiderReviewsView.as_view()),
  path('api/reviews/store/<uuid:storeId>/',   StoreReviewsView.as_view()),

  # SUPPORT
  path('api/support/ticket/',                 CreateSupportTicketView.as_view()),
  path('api/support/tickets/',               UserSupportTicketsView.as_view()),

  # GEOCODING PROXY (hides Google API key from client)
  path('api/geocode/reverse/',                ReverseGeocodeView.as_view()),
  path('api/geocode/search/',                 GeocodeSearchView.as_view()),
]
```

---

## 📝 REGISTRATION — Complete Field-by-Field Specification

---

### 🛒 CUSTOMER REGISTRATION — All 4 Steps

**Total steps:** 4 (Personal → OTP → Location → Photo)
**Time to complete:** ~90 seconds
**Auto-login after:** Yes, JWT issued immediately on completion

---

#### Step 1 — Personal Details `/register/customer/step-1`

```
Screen title: "Create your account"
Progress bar: 25% filled

FULL NAME *
  Input: text, placeholder "Priya Sharma"
  Validation: 2–60 chars, letters + spaces only
  Error: "Please enter your full name"
  Keyboard: default, capitalization: words

PHONE NUMBER *
  Layout: [🇮🇳 +91] [10-digit input]
  Keyboard: numeric
  Validation: exactly 10 digits, starts with 6/7/8/9
  On blur: check if already registered
    If yes: "This number is registered. Login instead?" with Login link
  Error: "Enter a valid 10-digit Indian mobile number"

EMAIL ADDRESS *
  Input: email keyboard type
  Auto-suggests: @gmail.com, @yahoo.com, @outlook.com
  On blur: duplicate check
  Validation: standard email regex
  Error: "Enter a valid email address"

PASSWORD *
  Input: secure text, toggle 👁 show/hide
  Strength meter: 4 bars below input, fills orange as complexity increases
  Live rules shown as checkmarks below meter:
    ○ At least 8 characters          → ✓ (turns green when met)
    ○ One uppercase letter           → ✓
    ○ One number or symbol           → ✓
  Error: "Password doesn't meet requirements"

CONFIRM PASSWORD *
  Input: secure text, toggle 👁
  Live match: shows "✓ Passwords match" green OR "✗ Don't match" red
  Error: "Passwords do not match"

TERMS CHECKBOX *
  ☐ I agree to the Terms of Service and Privacy Policy
  Links: open in-app browser (WebView), not external browser
  Must be checked to enable Continue

[  Continue →  ] — disabled until all fields valid + checkbox
[  Already have an account? Login  ] — text link below

── OR divider ──

[ G  Continue with Google ]
  Skips to Step 3 (location) with name + email pre-filled from Google
  Phone number step still required after Google auth
```

---

#### Step 2 — OTP Verification `/register/customer/step-2`

```
Screen title: "Verify your phone"
Subtitle: "We sent a 6-digit code to +91 98765 43210"
Tappable subtitle: tap number to go back and correct it

OTP INPUT:
  6 individual boxes (48×56px, 8px gap)
  Font: JetBrains Mono, 24px Bold, centered
  Active box: navy border (1.5px #1A1A2E)
  Filled box: standard border
  Auto-advance: entry moves focus to next box
  Auto-submit: all 6 filled → trigger verify API instantly
  Paste support: paste 6-digit SMS code → fills all boxes, submits
  Backspace on empty → focuses previous box

SUCCESS: all 6 boxes flash green for 300ms → advance to Step 3
FAILURE:
  Boxes shake (translateX oscillation, 400ms)
  Boxes turn red for 1s then clear
  "Incorrect OTP — X attempts remaining" (3 max)
  After 3 fails: "Too many attempts. Request a new OTP."

RESEND:
  "Didn't receive it? Resend in 0:45" countdown (orange number)
  After countdown → "Resend OTP" tappable (orange)
  Resend triggers new SMS, resets countdown
  Max 3 resends → "Too many attempts. Try again in 10 minutes."

SECURITY NOTE:
  "Never share this OTP with anyone, including KiranaRush support."
  Small, gray, 12px — important anti-fraud message
```

---

#### Step 3 — Location `/register/customer/step-3`

```
Screen title: "Where do you want deliveries?"
Subtitle: "We'll show you stores near your location"

Large illustration: animated map pin dropping into a neighbourhood

PERMISSION CARD:
  Large card with soft shadow:
  📍 "Allow location access"
  
  Bullet points (with checkmark icons):
  ✓ See nearby kirana stores
  ✓ Get accurate delivery time estimates
  ✓ Help riders find you easily
  
  Privacy note: "Your location is only shared with riders during active deliveries."

[ 📍 Allow Location Access ] — primary orange button
  → Triggers native OS permission prompt
  
  IF GRANTED:
    Animate map in: small map preview slides in (200px height)
    Shows detected city/area: "Koramangala, Bengaluru"
    Confirm: [ ✓ Yes, that's right ] | [ Set differently ]
    
  IF DENIED (or "Set differently"):
    Search field: "Search your area or landmark"
    Recent locations (if any stored)
    Manual pin on map option
    [ Continue with manual address ]
    Note: "You can always update your location later"
```

---

#### Step 4 — Profile Photo `/register/customer/step-4`

```
Screen title: "Add a profile photo"
Subtitle: "Optional — helps riders identify you at the door"

Large circle placeholder (120px diameter):
  Default: gray circle with person silhouette icon
  Tap anywhere on circle → action sheet:
    [ 📷 Take a photo ]
    [ 🖼 Choose from gallery ]
    [ Cancel ]

After photo selected/taken:
  Circular crop tool:
    Full-screen crop with circular mask overlay
    Pinch to zoom in/out
    Drag to reposition
  [ Use This Photo ] | [ Retake / Choose Again ]

Final state: shows selected photo in circle preview

[ Finish Setup ] — primary button (active always — photo is optional)
[ Skip for now ] — text link below

On tap "Finish Setup":
  Loading: "Setting up your account..."
  Success: navigate to /home with welcome toast
  "Welcome to KiranaRush, Priya! 👋"
```

---

### 🛵 RIDER REGISTRATION — All 5 Steps

**Total steps:** 5 (Personal → OTP → Vehicle → Documents → Review)
**Time:** ~6–10 minutes
**Post-submit:** Pending approval screen, no active features until approved

---

#### Step 1 — Personal Details `/register/rider/step-1`

```
Screen title: "Join as a Rider"
Progress: 20%

FULL NAME *
  Placeholder: "Your full name (as on Aadhaar)"
  Validation: 2–80 chars, letters + spaces
  Note below: "Must match your Aadhaar card exactly"

DATE OF BIRTH *
  Picker: 3-column roller — Day / Month / Year
  Validation: Age ≥ 18 years (real-time calculated)
  Live display: "Age: 24 years ✓" (green) OR "You must be 18+ to ride" (red)

GENDER *
  Segmented: [ Male ] [ Female ] [ Prefer not to say ]

PHONE NUMBER *
  Same format as customer — +91 + 10 digits
  Unique check on blur

EMAIL ADDRESS *
  Standard email input, unique check

EMERGENCY CONTACT NAME *
  Placeholder: "Parent / Spouse / Sibling"
  Sub-label: "Someone we can contact in emergencies"

EMERGENCY CONTACT PHONE *
  Same +91 format
  Validation: must differ from rider's own number
  Note: "Stored securely, used only in emergencies"

PASSWORD * + CONFIRM PASSWORD *
  Same as customer (strength meter + rules)

CHECKBOXES (both required):
  ☐ I agree to the Rider Agreement, Terms of Service and Privacy Policy
  ☐ I confirm all information provided is accurate and truthful

[ Continue → ]
[ Already have an account? Login ] — text link
```

---

#### Step 2 — OTP `/register/rider/step-2`

```
Same OTP UI as customer.
Messaging: "Verify your number to continue your rider application"
```

---

#### Step 3 — Vehicle Details `/register/rider/step-3`

```
Screen title: "Your Vehicle"
Progress: 60%

VEHICLE TYPE * — Two large full-width tap cards:

  ┌──────────────────────────────────────────────────────┐
  │  ⚡  Electric Vehicle                                │
  │     Ather, Ola Electric, TVS iQube, Bounce, etc.    │
  │     Eco-friendly • Earn 10% extra per delivery       │
  │                                             ○        │
  └──────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │  ⛽  Petrol / CNG Vehicle                            │
  │     Honda Activa, Bajaj, Hero, Yamaha, etc.          │
  │     Standard earning rate                            │
  │                                             ○        │
  └──────────────────────────────────────────────────────┘

  Selected card: orange border 2px + orange filled radio + tinted bg

VEHICLE BRAND *
  Searchable dropdown:
  Electric: Ather / Ola Electric / TVS iQube / Hero Electric /
            Revolt / Bounce / Pure EV / Ampere / Yulu / Other
  Petrol:   Honda / TVS / Bajaj / Hero / Yamaha / Suzuki /
            Royal Enfield / Vespa / Other
  "Other" → free text field appears

VEHICLE MODEL *
  Free text: placeholder "e.g. Ather 450X, Activa 6G"

MANUFACTURING YEAR *
  Dropdown: 2010 → current year
  Validation: vehicle must not be older than 15 years
  Error: "Vehicle must be manufactured after [current year - 15]"

VEHICLE REGISTRATION NUMBER *
  Format hint shown: "KA 01 AB 1234"
  Auto-uppercase as user types
  Regex: Indian number plate format validation
  Duplicate check: if same plate already registered
  Error: "Enter a valid Indian vehicle registration number"

VEHICLE COLOUR *
  Grid of colour circles (12 options):
  White / Black / Silver / Red / Blue / Green / Yellow /
  Orange / Grey / Brown / Gold / Other
  "Other" → colour name text input
  Selected: checkmark on colour circle

VEHICLE INSURED? *
  Large toggle row:
  "Is your vehicle insured?" [ ● Yes / No ● ]
  If YES: "Insurance expiry date" date picker slides in
          Validation: must not be expired
          Warning if < 3 months remaining
  If NO: "⚠️ Insurance is required. Vehicles without valid insurance cannot be approved."
         Link: "Learn more about requirements"

VEHICLE PHOTOS *
  Two mandatory upload slots:
  ┌──────────────────┐  ┌──────────────────┐
  │  [dashed box]    │  │  [dashed box]    │
  │  Front view      │  │  Side view       │
  │  (show plate)    │  │  (full vehicle)  │
  │  Tap to upload   │  │  Tap to upload   │
  └──────────────────┘  └──────────────────┘
  After upload: thumbnail preview + ✕ to remove
  Both required to proceed
```

---

#### Step 4 — Documents `/register/rider/step-4`

```
Screen title: "Verify your identity"
Progress: 80%
Banner: "🔒 All documents are encrypted and stored securely. Used only for verification."

── PROFILE PHOTO * ──────────────────────────────────────────────

  Large circular placeholder (100px)
  Guide text: "Clear face photo, no sunglasses"
  Camera viewfinder shows oval face guide overlay
  [ 📷 Camera ] [ 🖼 Gallery ]
  After: circular crop tool → circular preview

── AADHAAR CARD * ───────────────────────────────────────────────

  AADHAAR NUMBER *
    12-digit numeric input
    Auto-formatted: XXXX XXXX XXXX (spaces auto-added)
    Validation: Verhoeff check digit algorithm
    Privacy note: "We only store the last 4 digits for display"
    Error: "Enter a valid 12-digit Aadhaar number"

  AADHAAR — FRONT PHOTO *
    Dashed upload box with card silhouette guide
    "Place card fully within frame, all text visible"
    Min readable quality enforced (blurry detection via image analysis)

  AADHAAR — BACK PHOTO *
    Same upload UI

── DRIVING LICENCE * ────────────────────────────────────────────

  LICENCE NUMBER *
    Format: [State 2-letter][RTO 2-digit][Year 4-digit][Number 7-digit]
    Placeholder: "KA0120230001234"
    Auto-uppercase
    Indian DL regex validation
    Error: "Enter a valid Indian driving licence number"

  LICENCE ISSUE DATE *
    Date picker — cannot be in the future

  LICENCE EXPIRY DATE *
    Date picker
    Validation: must be > 30 days from today
    Warning (< 6 months): "⚠️ Your licence expires soon. Renew before it expires to continue riding."
    Error (expired): "Your licence has expired. Renew and reapply."

  LICENCE CLASS * (multi-select chips)
    [ LMV ] [ MCWG ] [ MCWOG ] [ Transport ]
    Note: "MCWG or MCWOG required for two-wheelers"

  DL FRONT PHOTO *
    Dashed upload box, card guide frame

  DL BACK PHOTO *
    Same upload UI

── PAN CARD (Optional — required if annual earnings > ₹50,000) ──

  PAN NUMBER
    Format: ABCDE1234F (10 chars)
    Regex: [A-Z]{5}[0-9]{4}[A-Z]{1}
    Note: "Required for tax deduction above ₹50,000/year"

  PAN PHOTO (if PAN number entered — required)
    Upload box

── BANK ACCOUNT (for earnings payout) ──────────────────────────

  ACCOUNT HOLDER NAME *
    Must match Aadhaar name (verified at admin review stage)

  BANK NAME *
    Searchable dropdown — all Indian banks (public + private + cooperative)

  ACCOUNT NUMBER *
    Numeric, 9–18 digits
    No paste allowed for security
    
  CONFIRM ACCOUNT NUMBER *
    Re-entry, no paste
    Live match indicator: ✓ / ✗

  IFSC CODE *
    Format: 4 letters + 0 + 6 alphanumerics
    Placeholder: "SBIN0001234"
    Auto-lookup on entry: fetches bank + branch + city from RBI IFSC API
    Success: "✓ State Bank of India — MG Road Branch, Bengaluru"
    Error: "Invalid IFSC code"

  UPI ID (Optional)
    Placeholder: "yourname@upi"
    [ Verify ] button — calls UPI validation, shows account holder name
    Success: "✓ Priya Sharma" (name confirmed from bank)
```

---

#### Step 5 — Review & Submit `/register/rider/step-5`

```
Screen title: "Review your application"
Progress: 100%

PERSONAL CARD:
  [Profile photo 72px circle] Ravi Kumar  •  Age 26  •  Male
  📞 +91 98765 43210   ✉️ ravi@email.com
  Emergency: Sunita Kumar — +91 91234 56789
  [Edit ✎] — navigates back to step-1

VEHICLE CARD:
  [Vehicle front photo 80×60px]
  ⚡ Ather 450X  •  White  •  2023
  KA01 AB 1234  •  Insured until Dec 2025
  [Edit ✎] — navigates back to step-3

DOCUMENTS CARD:
  ✅ Aadhaar  XXXX XXXX 3456   (uploaded)
  ✅ Driving Licence  KA01 20230012345  Exp: Mar 2027
  ✅ PAN  ABCDE1234F
  ✅ Bank  HDFC Bank — XXXX 6789  (IFSC: HDFC0001234)
  [Edit ✎] — navigates back to step-4

DECLARATION CHECKBOX (required):
  ☐ I declare that all information and documents are genuine and accurate.
    I understand that false information leads to permanent disqualification.

[ Submit Application ] — primary orange button

POST-SUBMIT ANIMATION:
  Lottie: paper plane taking off (600ms)
  
  "Application Submitted! 🎉"
  "We'll review your documents within 24–48 hours"
  "You'll receive SMS + email + push notification when approved"
  
  Status tracker strip:
  [✓ Submitted] → [⏳ Under Review] → [✓ Approved]
  
  [ Back to Home ] → /pending-approval
```

---

#### Pending Approval Screen — Rider

```
URL: /pending-approval

Illustration: animated clock + documents (lottie, looping gently)

"Application under review"
"Verifying your documents — usually 24–48 hours"

STATUS TIMELINE:
  ✅ Application submitted — April 4, 2025
  🔄 Documents under review  (pulsing dot animation)
  ⬜ Background verification
  ⬜ Approval decision

WHAT HAPPENS NEXT:
  📱 SMS to +91 98765 43210
  ✉️  Email to ravi@gmail.com
  🔔 Push notification on this device

INFO CARDS (horizontal scroll, readable while waiting):
  "💰 How earnings work"
  "📦 What to expect on your first delivery"
  "🛵 Top tips from experienced riders"

[ Check Status ] button — pulls API, updates timeline
[ Contact Support ] — text link

── IF REJECTED ──────────────────────────────────────────────────

"❌ Application Update"
Reason shown prominently in a red card:
  e.g. "Your driving licence appears to have expired.
        Please renew it and resubmit your application."

[ Reapply with Corrected Documents ] — goes to step-4 (documents only)
[ Contact Support ] — in-app chat
```

---

### 🏪 SHOP OWNER REGISTRATION — All 5 Steps

**Total steps:** 5 (Account → OTP → Location → Store Details → Review)
**Time:** ~8–12 minutes
**Post-submit:** Pending approval, limited dashboard preview access

---

#### Step 1 — Account Details `/register/shop-owner/step-1`

```
Screen title: "List your Kirana Store"
Progress: 20%

OWNER FULL NAME *
  Placeholder: "Your name (store owner / representative)"
  Validation: 2–80 chars

PHONE NUMBER *
  +91 + 10-digit, unique check

EMAIL ADDRESS *
  Business email preferred (note shown, not enforced)
  Unique check

PASSWORD * + CONFIRM PASSWORD *
  Same strength meter + rules

OWNER TYPE *
  Radio group (vertical):
  ○ Individual Owner (self-operated / sole proprietor)
  ○ Partnership / Family Business
  ○ Registered Company (GST mandatory)
  
  If "Registered Company":
    COMPANY NAME * — text input slides in
    GST NUMBER * — mandatory, 15-char format (22AAAAA0000A1Z5)
    CIN — optional, Company Identification Number

CHECKBOXES (both required):
  ☐ I agree to the Merchant Terms of Service and Privacy Policy
  ☐ I am the authorized owner or representative of this store

[ Continue → ]
```

---

#### Step 2 — OTP `/register/shop-owner/step-2`

```
Messaging: "Verify your number to continue listing your store"
Same OTP UI as others.
```

---

#### Step 3 — Store Location `/register/shop-owner/step-3`

```
Screen title: "Where is your store?"
Progress: 60%

FULL-SCREEN MAP (entire screen, no padding):

TOP FLOATING BAR (frosted glass, attached to top):
  [ 🔍 Search for your store address... ]
  Tapping: full-screen Places Autocomplete (India only, commercial bias)
  Recent searches shown below search field
  Results show: Place name + address + distance

CENTER PIN (always centred on map):
  Custom store/shop SVG pin, orange
  Drag map → pin "floats" (lift up 8px, grow shadow)
  Release → pin "drops" (spring bounce + ripple on ground)
  Ripple: 2 expanding circles, orange fading to transparent (400ms)

MY LOCATION BUTTON (bottom-right, floating, 48px circle):
  Tapping: animates map to GPS position, drops pin
  Requires location permission (requests if not granted)

BOTTOM INFO SHEET (draggable handle):
  Peek height: 150px

  Collapsed content:
    "📍 5th Cross, Koramangala 6th Block"
    "Bengaluru, Karnataka — 560095"
    GPS Accuracy: ±5m ✓ (green) / ±45m ⚠️ (yellow) / ±100m+ ✗ (red)
    [ Confirm This Location → ] — disabled if accuracy > 100m

  Drag up → full sheet (60% screen):
    FINE-TUNE ADDRESS FIELDS (pre-filled from reverse geocode, editable):
      Shop No / Floor *:   text (e.g. "Ground Floor, Shop 12")
      Building / Street *: text (pre-filled from Google)
      Area / Locality *:   text (pre-filled)
      City *:              text (pre-filled)
      State *:             dropdown (Indian states)
      Pincode *:           6-digit numeric, validates with India Post API
      
    LANDMARK (optional):
      Placeholder: "Near Apollo Hospital, Opp. Metro Station"
      Helps riders locate the store quickly
      
    TIP CARD:
      "📌 Pin should be at your store's entrance, not inside the building"
      
    [ Use This Location ] — primary button
```

---

#### Step 4 — Store Details `/register/shop-owner/step-4`

```
Screen title: "Tell us about your store"
Progress: 80%
Scrollable form — single screen

── STORE IMAGES ─────────────────────────────────────────────────

COVER IMAGE * (the main image customers see):
  Large dashed rectangle (full width, 16:9 ratio, border-radius 16px)
  Center icon + text: "Add your store's main photo"
  Sub: "Best: clear storefront photo in daylight"
  [ 📷 Camera ] [ 🖼 Gallery ] side-by-side buttons
  After upload: 16:9 preview with "Change" overlay on tap
  Enforced crop: 16:9 ratio
  Min resolution: 800×450px enforced
  File size limit: 5MB, compressed automatically if larger

ADDITIONAL PHOTOS (up to 4):
  Row of 4 dashed square boxes (90px each, 8px gap)
  Tap any → add (1:1 crop, interior/products/signage)
  Label: "Add more photos (interior, products, signage)"
  Long press → drag to reorder
  Tap added photo → preview + "Remove" or "Replace" option

── STORE INFO ───────────────────────────────────────────────────

STORE NAME *
  Placeholder: "e.g. Sharma Kirana Store"
  Max 80 chars, character counter "23/80"
  Validation: min 3 chars
  Near-duplicate warning (not blocked): "A store with a similar name exists nearby"

STORE CATEGORY * (multi-select grid, max 3):
  2-column grid, each cell: large emoji + category name
  🛒 General Grocery    🥛 Dairy & Eggs
  🥦 Fruits & Veg       🌿 Organic Store
  💊 Medical & Health   🧴 Personal Care
  🍵 Tea, Coffee, Snacks 🏠 Household Items
  🐾 Pet Supplies       🧒 Baby Products
  🌾 Staples & Atta     [ + Other (specify) ]
  
  Selected: orange border + orange checkmark top-right corner
  "Other" → text input appears: "Describe your store type"

STORE DESCRIPTION (optional but encouraged):
  Multiline textarea, 4 lines visible, expandable
  Placeholder: "Tell customers what makes your store special —
               brands you stock, years in business, specialties..."
  Max 300 chars, counter shown: "127/300"
  Pro tip card: "Stores with descriptions get 40% more clicks 💡"

── CONTACT ──────────────────────────────────────────────────────

STORE PHONE NUMBER *
  The number customers + riders call (not necessarily owner's personal)
  +91 + 10-digit format
  Toggle: "☑ Same as my registered number" — auto-fills if checked

WHATSAPP NUMBER (Optional)
  Toggle: "☑ Same as store phone number"
  If different: separate 10-digit field
  Note: "Customers can WhatsApp for quick queries"

STORE EMAIL (Optional)
  For order confirmation copies to store

── STORE TIMINGS * ──────────────────────────────────────────────

DAYS OPEN:
  7 pill buttons: [Mon] [Tue] [Wed] [Thu] [Fri] [Sat] [Sun]
  Active (open): filled orange pill
  Inactive (closed): gray outline pill
  "Open all 7 days" quick-select chip at top-right

OPENING TIME *
  Time picker (12-hour with AM/PM)
  Quick presets: [7 AM] [8 AM] [9 AM] [10 AM]

CLOSING TIME *
  Time picker
  Validation: must be after opening time
  Quick presets: [9 PM] [10 PM] [11 PM] [Midnight]

BREAK TIME (Optional):
  Toggle: "[ ] Store has a break/lunch hour"
  If ON: "Break from [___] to [___]" — two time pickers slide in

UPCOMING HOLIDAYS:
  [ + Mark a date as closed ] → calendar date picker (future dates only)
  Listed closures: "Closed on Apr 14 (Ambedkar Jayanti)"
  Each can be removed with ✕

── BUSINESS DETAILS ─────────────────────────────────────────────

GST NUMBER
  Conditional: mandatory if owner_type = "Registered Company"
  Optional otherwise
  15-char field with format mask: 22AAAAA0000A1Z5
  [ Verify GST ] button → calls GST verification API
  Success: "✓ Sharma Trading Co. — Active registration (Delhi)"
  Error: "Invalid or inactive GST number"

FSSAI LICENCE (Food licence — Optional but badge shown to customers):
  14-digit numeric field
  Info tooltip: "Having FSSAI licence shows customers your store meets food safety standards"

YEARS IN BUSINESS:
  Dropdown: Less than 1 yr / 1–3 yrs / 3–5 yrs / 5–10 yrs / 10+ yrs

── DELIVERY PREFERENCES ─────────────────────────────────────────

MINIMUM ORDER VALUE *
  Currency input with ₹ prefix
  Quick presets: [₹0] [₹50] [₹100] [₹200]
  Default: ₹0 (no minimum)
  Note: "Customers cannot place orders below this amount from your store"

ACCEPT CASH ON DELIVERY?
  Large toggle, default ON
  Note: "COD orders require your confirmation before rider pickup"
  If OFF: orange info banner: "Online-only stores get 15% lower cancellation rates"
```

---

#### Step 5 — Review & Submit `/register/shop-owner/step-5`

```
Screen title: "Review your store listing"
Progress: 100%

CUSTOMER PREVIEW CARD (this is how your store looks to customers):
  [Cover image — full-width 16:9 preview, border-radius 12px]
  "Sharma Kirana Store"  (22px Bold)
  🛒 Grocery  •  ⭐ New Store  •  [Open Now 🟢]
  "Serving fresh groceries since 2012 — Koramangala's trusted store"
  "This is how customers will see your store"

OWNER DETAILS CARD:
  👤 Rajesh Sharma
  📞 +91 98765 43210   ✉️ rajesh@store.com
  Owner Type: Individual
  [Edit ✎]

LOCATION CARD:
  [Mini map snippet with pin, non-interactive]
  5th Cross, Koramangala 6th Block, Bengaluru — 560095
  Near Apollo Hospital
  [Edit ✎]

STORE DETAILS CARD:
  ⏰ Mon–Sun  9:00 AM – 10:00 PM
  📞 Store: +91 80 4567 8901
  Minimum order: ₹100
  COD: Accepted ✓
  GST: 22AAAAA0000A1Z5 ✓
  [Edit ✎]

COMMISSION NOTICE (transparent, builds trust):
  ┌─────────────────────────────────────────────────────────┐
  │  💰 Commission: KiranaRush charges 8% per completed     │
  │  order. Payouts are transferred within 3 business days. │
  └─────────────────────────────────────────────────────────┘

APPROVAL TIMELINE:
  ┌─────────────────────────────────────────────────────────┐
  │  ⏱ Approval takes 48–72 hours                          │
  │  Our team verifies every store before it goes live.     │
  │  You'll be notified via SMS, email + push notification. │
  └─────────────────────────────────────────────────────────┘

DECLARATIONS (both required):
  ☐ I confirm this is a legitimate physical store open to the public
    and all information provided is accurate
  ☐ I agree to the Merchant Terms of Service, Commission Policy,
    and Payout Terms

[ Submit for Approval ] — primary orange button (only if both checked)

POST-SUBMIT:
  Lottie: shop building with star burst animation (800ms)
  "Store submitted for review 🏪"
  "Meanwhile, you can start adding products to get ready!"
  [ Preview Dashboard → ] — limited mode, cannot receive orders yet
  [ Back to Home ] — /pending-approval

── PENDING APPROVAL — SHOP OWNER ────────────────────────────────

URL: /pending-approval

Illustration: animated store with a magnifying glass (verification)

"Your store is under review 🏪"
"Our team reviews every store to protect our customers"

STATUS TIMELINE:
  ✅ Application submitted — April 4, 2025
  🔄 Store details being verified
  ⬜ Location confirmation (team may call you)
  ⬜ Store goes live

ACTIONS AVAILABLE IN PREVIEW MODE:
  "While you wait, get your store ready:"
  [ 📦 Add Products ] → /shop/products (products saved, activated on approval)
  [ 📸 Add More Photos ] → /shop/account/images

CONTACT: "Questions? Our team typically calls within 24 hours to confirm your store details."

── IF REJECTED ──────────────────────────────────────────────────

"❌ Store Application Update"

Rejection reason in red card:
  Common rejection reasons + specific fixes shown:
  "Store image is unclear" → "Upload a clear, well-lit storefront photo"
  "Address could not be verified" → "Re-pin your location more precisely"
  "GST number is invalid" → "Re-enter your GSTIN or leave blank if not registered"

[ Resubmit with Corrections ]
  Takes user back to the SPECIFIC step that had the issue (not start)
  
[ Contact Support ] — live chat
```

---

## 👤 PROFILE PAGES — Complete Field Specification

---

### Customer Profile `/profile`

```
HEADER CARD:
  [Profile photo — 80px circle, orange border ring, tap to change]
  Priya Sharma
  📞 +91 98765 43210  •  ✉️ priya@gmail.com
  "Member since April 2025  •  12 orders placed"
  [ Edit Profile → ] — right-aligned text link, orange

RECENT ACTIVITY STRIP (horizontal scroll, 3 most recent orders):
  Each mini-card: order date + store name + amount + status badge

SECTION HEADERS use: 11px semibold #6B7280 uppercase, tracking-wider

SECTION — Account:
  👤  Edit Personal Information     →
  📍  My Delivery Addresses         →   "(3 saved)"
  💳  Payment Methods               →   "(2 saved)"
  🔔  Notification Preferences      →

SECTION — Orders & Activity:
  📦  My Orders                     →
  ❤️   Saved Stores                  →   "(5 stores)"
  🔄  Order Again                   →   (quick-reorder shortcuts)
  🏷️   My Coupons & Offers           →
  👥  Refer a Friend                →   (referral code + share)

SECTION — Support & Legal:
  ❓  Help & Support                →
  📝  Raise a Complaint             →
  🔒  Privacy Settings              →
  📄  Terms of Service              →
  ℹ️   About KiranaRush              →
  🌐  Language                      →   "English"

[ 🚪 Logout ] — full-width red-tinted row, with confirmation:
  Modal: "Are you sure you want to logout?"
  [ Cancel ] [ Logout ]

App version: "v1.0.0 (42)" — tiny gray, centered, bottom

── Edit Personal Info /profile/edit ─────────────────────────────

PHOTO: 80px circle + edit overlay (camera icon) — tap to change
  Uses same crop tool as registration

FIELDS:
  Full Name *         [Priya Sharma              ]
  Phone Number        [📞 +91 98765 43210        ] 
    Change phone: requires OTP on new number
    "Tap to change" → verify old phone → enter new → OTP new phone
  Email               [✉️ priya@gmail.com        ]
    Change email: sends verification to new email before updating
  Date of Birth       [15 Aug 1995               ] (date picker)
  Gender              [ Female                ▾  ] (dropdown)

  [ Save Changes ] — primary, enabled only when something changed
  
  Unsaved changes guard:
    Back button press → "Discard unsaved changes?" 
    [ Keep Editing ] [ Discard ]

── My Addresses /profile/addresses ──────────────────────────────

Default address: orange-bordered card with "DEFAULT 🏠" badge top-right

Each address card:
  ┌──────────────────────────────────────────────────────────┐
  │  🏠  Home                                  [Set Default] │
  │  Flat 5A, Prestige Shantiniketan           [Edit ✎] [✕] │
  │  Koramangala, Bengaluru — 560034                         │
  │  Near Apollo Hospital                                    │
  └──────────────────────────────────────────────────────────┘

  Long press → reorder addresses (drag handles appear)
  Swipe left → reveals [Delete] action in red

FAB: [ + Add New Address ] (bottom-right)

ADD / EDIT ADDRESS:
  Address Label *:
    [ 🏠 Home ] [ 💼 Work ] [ 👫 Other ]
    If Other: "Label name" text input: "Parents' House"
    
  Flat / House No *:  text
  Building / Apartment: text
  Street / Area *:    text + Google Places suggestions
  City *:             auto-filled, editable
  State *:            dropdown
  Pincode *:          6-digit + India Post validation
  Landmark (optional): "Near/Opp./Behind ___"
  
  MAP (200px compact):
    Shows pin at current address location
    "Adjust pin" link → full-screen map picker
    "Use my current location" button
    
  [ Save Address ] | [ Cancel ]

── Payment Methods /profile/payment-methods ──────────────────────

SAVED UPI IDs:
  [UPI logo] priya@okaxis     [ Remove ]
  [UPI logo] priya@paytm      [ Remove ]
  [ + Add UPI ID ]
    Input: "yourname@upi"  [ Verify → shows name ] [ Save ]

SAVED CARDS:
  [Visa] •••• 4242  VISA  Exp 09/27   [ Remove ]
  [MC]   •••• 8888  MC    Exp 03/26   [ Remove ]
  [ + Add New Card ]
    → Opens Razorpay card-add SDK (tokenised storage, PCI compliant)

SECURITY NOTE:
  "🔒 Card details are stored securely by Razorpay, not KiranaRush."

── Notification Preferences /profile/notifications ──────────────

ORDER UPDATES (cannot fully disable — critical):
  ☑ Order confirmed by store
  ☑ Rider assigned to your order
  ☑ Order picked up by rider
  ☑ Rider is nearby (500m alert)
  ☑ Order delivered

PROMOTIONAL (fully optional):
  ☐ Deals and discounts from nearby stores
  ☐ New stores in your area
  ☐ Weekly KiranaRush newsletter
  ☑ Flash sale alerts

DELIVERY METHOD:
  ☑ Push notifications (in-app)
  ☑ SMS alerts
  ☐ Email notifications
  
NOTE: "Order status SMS cannot be disabled as they are essential for delivery."
```

---

### Rider Profile `/rider/profile`

```
HEADER CARD:
  [Profile photo — 80px, orange ring]
  Ravi Kumar
  ⭐ 4.8 rating  •  128 deliveries completed
  Rider since March 2025
  ⚡ Electric Rider — Hero Electric Optima  •  KA01 AB 1234
  [ Edit Profile ] — orange text link

QUICK STATS (horizontal scroll, 4 cards):
  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │ This Month │  │ Acceptance │  │ Completion │  │ Avg Delivery│
  │  ₹7,840    │  │  88% rate  │  │  99% rate  │  │   28 min   │
  └────────────┘  └────────────┘  └────────────┘  └────────────┘

SECTION — My Information:
  👤  Edit Personal Information    →
  🛵  Vehicle Details              →
  📄  My Documents                 →   (with expiry alerts if any)
  🏦  Bank & UPI Details           →

SECTION — Performance:
  📊  My Earnings                  →
  ⭐  My Ratings & Reviews         →
  📅  Attendance & Hours           →

SECTION — Support:
  ❓  Help & FAQs                  →
  📝  Report an Issue              →
  🔒  Privacy Settings             →
  📄  Rider Agreement              →

[ 🚪 Logout ]

── Edit Personal Info /rider/profile/edit ────────────────────────

PHOTO: circular with edit overlay (required, cannot remove)

FIELDS:
  Full Name *              (change triggers document re-verification)
  Phone Number             (OTP required to change)
  Email                    (verify required to change)
  Date of Birth            (read-only after approval — contact support to change)
  Gender
  Emergency Contact Name * (editable anytime)
  Emergency Contact Phone *(editable anytime)
  Current Residential Address (private — for records only):
    Flat/House No | Street | Area | City | State | Pincode

[ Save Changes ]

── Vehicle Details /rider/profile/vehicle ────────────────────────

CURRENT VEHICLE SUMMARY:
  [Vehicle front photo 120px wide]
  ⚡ Hero Electric Optima  |  White  |  2023
  KA01 AB 1234
  Insurance: Valid until December 2025

EDITABLE FIELDS:
  Vehicle Brand / Model (change triggers admin review)
  Manufacturing Year
  Vehicle Colour
  Registration Number (change triggers admin review + re-verification)
  Insurance Expiry Date (update when renewed — no approval needed)
  Vehicle Photos — Front + Side (re-upload anytime)

INSURANCE EXPIRY ALERTS:
  > 3 months: nothing shown
  1–3 months: amber banner "⚠️ Insurance expires in 47 days. Renew soon."
  < 30 days: red banner "🚨 Insurance expires in 18 days. Renew to continue riding."
  Expired: cannot go online, red screen "🚫 Your vehicle insurance has expired. Update to resume deliveries."

── Documents /rider/profile/documents ────────────────────────────

Each document as a card:
  ┌────────────────────────────────────────────────────────────┐
  │  📄 Aadhaar Card                    ✅ Verified             │
  │  XXXX XXXX 3456                                            │
  │  [ View Photo ] [ Update ]                                 │
  └────────────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────────┐
  │  🚗 Driving Licence                 ✅ Verified             │
  │  KA0120200012345  •  Expires Mar 2027                      │
  │  [ View Photo ] [ Update ]                                 │
  └────────────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────────┐
  │  💳 PAN Card                        ✅ Verified             │
  │  ABCDE1234F                                                │
  │  [ View ]                                                  │
  └────────────────────────────────────────────────────────────┘

Status badges: ✅ Verified | ⏳ Pending Review | ❌ Rejected | ⚠️ Expiring Soon

Update flow: re-upload photo → goes for admin re-verification
             Shows "⏳ Under Review" badge during verification
```

---

### Shop Owner Account `/shop/account`

```
STORE HERO:
  [Cover image — full width, 16:9, tap to change]
  [Store avatar — 72px circle, overlapping left side of cover bottom edge]
  "Sharma Kirana Store"       (24px ExtraBold)
  ⭐ 4.3  (127 reviews)  •  🛒 Grocery
  Since February 2025
  Status toggle: [ 🟢 Open ] ← large pill, tap to toggle open/closed

QUICK ACTIONS ROW:
  [ 📦 View Orders ] [ ➕ Add Product ] [ 📊 Today's Stats ]
  3 chips, horizontally spaced

SECTION — Store Management:
  📝  Edit Store Details           →   (Name, description, categories)
  📍  Update Store Location        →   (Map — triggers re-approval)
  ⏰  Store Timings                →   (Hours, days, holidays)
  📸  Manage Store Images          →   (Cover + gallery)
  💰  Order & Delivery Settings    →   (Min order, COD toggle)

SECTION — Financial:
  🏦  Bank Account Details         →   (Payout account)
  💵  Payout History               →   (All transfers received)
  🧾  GST & Tax Documents          →   (GSTIN, FSSAI)
  📊  Commission Summary           →   (8% breakdown + this month's)

SECTION — Reviews:
  ⭐  Customer Reviews             →   (All reviews, reply feature)
  📈  Store Performance            →   (Badges, metrics)

SECTION — Support:
  ❓  Help Centre                  →
  📝  Raise a Dispute              →
  📄  Merchant Agreement           →
  🔒  Privacy Settings             →

[ 🚪 Logout ]

── Edit Store Details /shop/account/edit ────────────────────────

SECTION: Basic Info
  Store Name *           (change = admin re-approval required)
    ⚠️ Yellow banner if changed: "Changing name requires admin re-approval (24–48 hrs)"
  Description            (300 chars)
  Categories *           (same multi-select grid as registration, max 3)

SECTION: Contact
  Store Phone *
  WhatsApp Number
  Store Email

SECTION: Business
  GST Number             (change = admin re-approval)
  FSSAI Licence Number
  Years in Business

SECTION: Delivery Settings
  Minimum Order Value (₹)
  Accept COD:  [Toggle]

RE-APPROVAL INDICATOR:
  Fields that trigger re-approval have this badge next to their label:
  "🔄 Re-approval required"
  And a section banner at top:
  "Fields marked 🔄 require admin review before taking effect.
   Your store stays live with current details during review."

[ Save Changes ] | [ Cancel ]

── Store Timings /shop/account/timings ──────────────────────────

7-day weekly schedule:
  Each day row: [Day name] | [Open/Closed toggle] | [From ___] [To ___]
  
  Mon  ●  09:00 AM  →  10:00 PM
  Tue  ●  09:00 AM  →  10:00 PM
  Wed  ●  09:00 AM  →  10:00 PM
  Thu  ●  09:00 AM  →  10:00 PM
  Fri  ●  09:00 AM  →  11:00 PM
  Sat  ●  08:00 AM  →  11:00 PM
  Sun  ○  (Closed)
  
  "Apply Monday's timings to all days" shortcut link
  
BREAK TIME (per day, optional):
  "Add break" link on each open day
  
HOLIDAY DATES:
  Calendar picker (multi-select future dates)
  List: "Closed Apr 14  ✕" | "Closed May 1  ✕"

[ Save Timings ]

── Store Images /shop/account/images ────────────────────────────

COVER IMAGE:
  Current cover preview (16:9)
  [ Change Cover Photo ] → crop tool

GALLERY IMAGES (up to 4 additional):
  Grid of current images with ✕ on each
  Empty slots show "+" to add
  Drag handles appear on long-press to reorder
  "Gallery images appear when customers expand your store profile"

[ Save ]
```

---

## 🛒 CART & CHECKOUT — Complete Payment Flow

---

### Cart Screen `/cart`

```
EMPTY STATE:
  Illustration: empty bag with a small leaf blowing
  "Your cart is empty"
  "Discover fresh items from local kirana stores"
  [ 🏪 Explore Stores ] — orange button → /home

WITH ITEMS — FULL LAYOUT:

HEADER:
  "My Cart" (20px Bold) + "3 items" badge + [ 🗑 Clear All ] (right, red text)
  Clear All: confirmation alert "This will remove all items. Continue?" [ Cancel ] [ Clear ]

MULTI-STORE GROUPED ITEMS:

  Store Group 1:
  ┌────────────────────────────────────────────────────────────┐
  │  [Store img 36px circle]  Sharma Kirana                    │
  │  2 items  •  ₹575              [ + Add more items from here→]│
  │  ─────────────────────────────────────────────────────── │
  │                                                            │
  │  [Product img 56×56px] Amul Butter 500g                   │
  │  1 pack  •  Sharma Kirana      [ − ] [2] [ + ]   ₹530    │
  │                                                            │
  │  [Product img 56×56px] Britannia Multigrain Bread          │
  │  1 loaf                        [ − ] [1] [ + ]    ₹45    │
  │                                                            │
  │  Store subtotal:                               ₹575       │
  └────────────────────────────────────────────────────────────┘

  Store Group 2:
  ┌────────────────────────────────────────────────────────────┐
  │  [Store img] Green Basket Organics                         │
  │  1 item  •  ₹220             [ + Add more items from here→ ]│
  │  ─────────────────────────────────────────────────────── │
  │  [Product img] Alphonso Mangoes 1kg                        │
  │                               [ − ] [1] [ + ]   ₹220     │
  │  Store subtotal:                               ₹220       │
  └────────────────────────────────────────────────────────────┘

INTERACTION RULES:
  [+] tap: quantity +1, optimistic UI update (instant), syncs to API in background
  [−] tap: quantity −1; at 1 → shows "Remove item?" confirmation OR directly removes
  At 0: item slides out (translateX -100%, opacity 0, height collapses, 250ms)
  Stock limit: [+] grays out + "Max 5" tooltip when quantity = stock
  Price updates instantly as quantity changes (no lag, no loader)
  "Add more items from here →" tapping returns to that store's detail page (/home/store/:id)

COUPON SECTION:
  ┌────────────────────────────────────────────────────────────┐
  │  🏷️  Have a coupon?                                        │
  │  [  ENTER COUPON CODE           ]    [ Apply ]             │
  │  ─────────────────────────────                            │
  │  Available offers:                                         │
  │  [SAVE20] First order 20% off      → [ Apply ]            │
  │  [KIRANA50] ₹50 off on ₹500+      → [ Apply ]            │
  └────────────────────────────────────────────────────────────┘
  
  Apply: loading spinner on "Apply" button → success or error
  Applied: input turns green + "KIRANA50 applied — saving ₹50! ✓" + [ ✕ Remove ]
  Error: "Invalid or expired coupon code" in red below input

SAVINGS BANNER (conditional — shown if savings exist):
  "🎉 You're saving ₹85 on this order!"
  Green background, slides in from right with spring animation (250ms)
  Hides when coupon removed

BILL DETAILS (collapsible accordion):
  "Bill Details ▼" / "Bill Details ▲" toggle header
  Default: collapsed (users who care can expand)
  
  Expanded content:
  Item total:               ₹795
  Coupon discount (KIRANA50):  −₹50
  ─────────────────────────────────
  Sub-total:                ₹745
  Delivery fee:              ₹40   [ℹ️]
  Platform fee:               ₹5   [ℹ️]
  GST on platform fee:        ₹1
  ══════════════════════════════════
  Total payable:            ₹791
  
  ℹ️ tapping delivery fee: "Delivery fee is charged based on distance from store to your location"
  ℹ️ tapping platform fee: "A small fee to keep the platform running"
  
  "Total savings: ₹85 🎉" (green, below total)

DELIVERY ESTIMATE:
  📍 Delivering to: "Flat 5A, Prestige Shantiniketan" [ Change ]
  ⏱ Estimated: 40–55 minutes from store confirmation
  🛵 Items will be picked up from 2 stores sequentially by one rider

STICKY CHECKOUT BUTTON:
  Fixed at bottom, white bar above it (shadow-xl)
  Safe area bottom padding (iOS) / navigation bar padding (Android)
  
  [ Proceed to Checkout  ₹791 ] — full width, 56px, orange, ExtraBold
  
  Disabled state (if cart empty or validation errors):
    Grayed out + "Fix errors above to continue" tooltip
```

---

### Checkout Step 1 — Address `/cart/checkout`

```
HEADER:
  Back arrow → cart  |  "Checkout"  |  Step indicator: ①—②—③

PROGRESS STEPPER:
  [ ① Address ] ——— [ ② Payment ] ——— [ ③ Confirm ]
  Active step: orange filled circle with step number, bold label
  Completed: green checkmark
  Upcoming: gray outline circle, gray label

MAP PREVIEW (200px height):
  Shows delivery pin at saved/detected address
  Non-interactive (tap → opens /home/location-picker)
  Styled: light map, orange delivery pin in centre
  "Tap map to adjust pin" hint text (12px, gray, bottom-right of map)

DELIVERY ADDRESS:
  Currently selected:
  ┌────────────────────────────────────────────────────────────┐
  │  🏠  Home  (Default)                                       │
  │  Flat 5A, Prestige Shantiniketan, Koramangala              │
  │  Bengaluru — 560034                                        │
  │  Near Apollo Hospital                                      │
  └────────────────────────────────────────────────────────────┘
  
  [ ↓ Change Address ] — expands to list of saved addresses
  Expanded: saved address cards (same style as /profile/addresses)
  "Use current location" option at top of list
  [ + Add New Address ] at bottom of list

APARTMENT / INSTRUCTIONS (always visible, even with saved address):
  FLAT NO / FLOOR (often incomplete in saved addresses):
  "Floor / Flat No:"  [  Flat 5A, 3rd Floor  ]  (pre-filled if available, always editable)
  
  DELIVERY INSTRUCTIONS (optional):
  Quick chips (horizontal scroll, tap to select, can multi-select):
  [ 🚪 Leave at door ] [ 📞 Call on arrival ] [ 🔔 Ring doorbell ] [ 🐕 Dog at home ]
  Or free text: "Delivery instructions" (multiline, 100 char max)

ORDER SUMMARY (collapsible — collapsed by default):
  "Order Summary (3 items, 2 stores) ▼"
  Expanded: shows store groups + item counts + subtotals (no full detail — keep it light)

VALIDATION BEFORE PROCEEDING:
  Address must be within 20km of at least one store in cart
  If outside radius: "Some stores in your cart don't deliver to this address.
                     Change address or remove those items."

[ Continue to Payment → ] — primary orange button, 56px
  Disabled until address confirmed + within radius
```

---

### Checkout Step 2 — Payment `/cart/checkout/payment`

```
HEADER: Back → step 1  |  "Payment"  |  Stepper: ① ✓ — ② — ③

TOTAL REMINDER (sticky top):
  ┌────────────────────────────────────────────────────────────┐
  │  3 items from 2 stores           Total:  ₹791             │
  │  Savings applied: ₹85                     [ View details ] │
  └────────────────────────────────────────────────────────────┘

PAYMENT OPTIONS (radio group, one at a time):

── UPI (shown first — #1 in India) ──────────────────────────────

  ○ UPI — Pay via any UPI app
  [Expand if selected]:
  
    QUICK APP SHORTCUTS (auto-detected installed apps):
    [ G GPay ] [ PhonePe ] [ Paytm ] [ BHIM ] [ Amazon Pay ]
    Shown only if app is installed on device (intent detection)
    Tapping opens app directly via Razorpay intent → completes payment in app → returns
    
    ENTER UPI ID MANUALLY:
    [ yourname@________________ ]  [ Verify & Pay ]
    Verify: API checks UPI ID validity, shows name:
    "✓ Priya Sharma (Axis Bank)" — confirms right account before payment
    
    SAVED UPI IDs (if any):
    ○  priya@okaxis
    ○  priya@paytm
    [ + Pay with a different UPI ID ]

── Credit / Debit Card ───────────────────────────────────────────

  ○ Credit / Debit Card
  [Expand if selected]:
  
    SAVED CARDS:
    ○  •••• 4242  Visa     Exp 09/27    CVV: [_ _ _]
    ○  •••• 8888  MC       Exp 03/26    CVV: [_ _ _]
    
    ADD NEW CARD:
    Card Number: [____ ____ ____ ____]
      Auto-detects card type → shows Visa/MC/Amex/Rupay logo in real-time
    Name on Card: [____________________]
    Expiry: [MM] / [YY]
    CVV: [___]  [ ℹ What is CVV? ] → tooltip: "3 digits on back of card"
    [ ] Save this card for future orders (Razorpay tokenisation)

── Net Banking ────────────────────────────────────────────────────

  ○ Net Banking
  [Expand if selected]:
    Popular banks (logos, tap to select):
    [ SBI ] [ HDFC ] [ ICICI ] [ Axis ] [ Kotak ] [ PNB ] [ BOB ]
    [ See all 50+ banks ▼ ]
    Selected bank: highlighted orange border

── Wallet ─────────────────────────────────────────────────────────

  ○ Wallets
  [Expand if selected]:
    [ Paytm Wallet ] [ Amazon Pay ] [ Freecharge ] [ PhonePe Wallet ]

── Cash on Delivery ───────────────────────────────────────────────

  ○ Cash on Delivery
  [Expand if selected]:
    Info box (non-blocking, informational):
    ✓ Available for this order (₹791 ≤ ₹2,000 limit)
    ✓ Keep ₹791 cash ready (exact change preferred)
    ✓ Pay the rider after verifying all items
    ⚠️ Cancelling after rider dispatches affects your COD access
    
    [CONDITIONS FOR DISABLING COD]:
    If total > ₹2,000:
      Option grayed out. Reason: "COD unavailable for orders above ₹2,000"
    If user has 2+ active COD orders:
      "COD unavailable — 2 pending COD orders. Pay for those first."
    If first-time user + order > ₹500:
      "COD available from your 2nd order onwards for amounts above ₹500"

PAYMENT SECURITY STRIP:
  [🔒 Razorpay Secured]  [PCI DSS]  [256-bit SSL]
  Small, centered, muted — trust signals without visual noise

COUPON REMINDER (if no coupon applied yet):
  Small tappable banner: "🏷️ Have a coupon? You may be missing savings →"

PLACE ORDER BUTTON:
  Label changes per method:
  UPI:           [ Pay ₹791 via UPI → ]
  Card:          [ Pay ₹791 Securely → ]
  Net Banking:   [ Pay ₹791 via Net Banking → ]
  Wallet:        [ Pay ₹791 via Wallet → ]
  COD:           [ Confirm Order — Pay ₹791 Cash on Delivery ]

  All versions: full-width, 56px, orange
  
  PRE-FLIGHT VALIDATION when button tapped (before payment SDK):
    Re-check cart items still in stock
    Re-check all stores still open
    Re-check delivery address in range
    If any fail: show blocking error before opening Razorpay
    "One item went out of stock — please review your cart"
    [ Back to Cart ] button
```

---

### PAYMENT CONFIRMATION FLOWS — Complete Logic

---

#### Flow A — Online Payment (Razorpay)

```
STEP 1: User taps [ Pay ₹791 Securely ]

  Backend: POST /api/payments/create-order/
  Body: { amount: 79100, currency: "INR", cart_id, address_id, coupon_code }
  Response: { razorpay_order_id, amount, key_id, prefill }
  
  Button loading: spinner + "Opening secure payment..."
  Duration: 1–2s (API call)

STEP 2: Razorpay SDK opens (in-app overlay, no browser)
  Pre-filled:
    name: "Priya Sharma"
    email: "priya@gmail.com"
    contact: "+919876543210"
  Method: pre-selected based on what user chose in Step 2

  USER ACTIONS WITHIN RAZORPAY SDK:
  - Complete UPI payment in their UPI app
  - Enter card details + OTP/3DS
  - Complete net banking in embedded view
  
STEP 3A — PAYMENT SUCCESS:

  Razorpay callback returns:
    razorpay_payment_id: "pay_ABC123"
    razorpay_order_id: "order_XYZ789"
    razorpay_signature: "abc123def456..."
  
  Frontend immediately calls:
  POST /api/payments/verify/
  Body: { payment_id, order_id, signature }
  
  Backend verification:
    expected_sig = HMAC_SHA256(key_secret, "order_XYZ789|pay_ABC123")
    if expected_sig == razorpay_signature: VALID
    else: INVALID (log fraud attempt, return error)
  
  On VALID:
    Order.payment_status → "paid"
    Order.status → "confirmed"
    Order.razorpay_payment_id → "pay_ABC123"
    Order ID assigned: "KR-1049"
    Delivery OTP: random 6-digit generated + hashed (bcrypt) stored
    FCM sent to store owner(s): "🛒 New Order #KR-1049! ₹791"
    Rider assignment algorithm triggered asynchronously (Celery)
    
  Frontend receives: { success: true, order_id: "KR-1049" }
  Navigate: /cart/checkout/success

STEP 3B — PAYMENT FAILED:

  Razorpay SDK shows its own error messaging within the sheet
  User can retry within the sheet (Razorpay handles retry internally)
  
  If user explicitly CLOSES/DISMISSES the sheet:
    Navigate to: /cart/checkout/payment-failed
  
  PAYMENT FAILED SCREEN:
    ┌──────────────────────────────────────────────────────────┐
    │  ❌  (red circle with X — Lottie)                        │
    │  "Payment unsuccessful"                                  │
    │  "No money has been deducted from your account."         │
    │                                                          │
    │  Common reasons:                                         │
    │  • Insufficient balance                                  │
    │  • Transaction declined by your bank                     │
    │  • Payment timed out                                     │
    │  • OTP entered incorrectly                               │
    │                                                          │
    │  [ 🔄 Try Again with Same Method ]                       │
    │      Re-opens Razorpay SDK, same order_id (no new charge) │
    │                                                          │
    │  [ 💵 Switch to Cash on Delivery ]                       │
    │      COD confirmation modal → same order proceeds as COD  │
    │                                                          │
    │  [ ← Back to Cart ]                                      │
    │      Returns to cart (items preserved)                   │
    └──────────────────────────────────────────────────────────┘

STEP 4 — WEBHOOK (server-side, parallel to frontend flow):

  Razorpay → POST /api/payments/webhook/
  Backend validates webhook signature (separate RAZORPAY_WEBHOOK_SECRET)
  
  Events handled:
    payment.captured → mark order paid (source of truth)
    payment.failed → mark payment failed, send user notification
    refund.processed → update refund status, notify user
  
  Idempotency: check if order already marked paid before re-processing
  Webhook retries: Razorpay retries up to 5 times on failure — backend handles duplicates
```

---

#### Flow B — Cash on Delivery

```
STEP 1: User selects COD, taps [ Confirm Order — Pay ₹791 Cash on Delivery ]

STEP 2: PRE-VALIDATION (server-side, before showing confirmation):
  POST /api/payments/cod/confirm/ (dry-run validation)
  
  Checks:
  ✓ Order total ≤ ₹2,000
  ✓ Customer has < 2 active COD orders
  ✓ Customer has < 3 lifetime COD refusals
  ✓ If first order: total ≤ ₹500
  ✓ All items still in stock
  ✓ All stores open or will open before estimated delivery
  ✓ Delivery address within all store radii
  
  If any fail: show specific blocking error with resolution option
  "Amul Butter went out of stock — [Remove & Continue] or [Back to Cart]"

STEP 3: COD CONFIRMATION MODAL (non-dismissable by back button):

  Full-screen bottom sheet that slides up:
  ┌──────────────────────────────────────────────────────────┐
  │  ▬  (handle)                                             │
  │                                                          │
  │  💵  Confirm Cash on Delivery                            │
  │                                                          │
  │  You'll pay:  ₹791 cash  to your delivery rider          │
  │                                                          │
  │  Please note:                                            │
  │  • Keep ₹791 ready — exact change preferred              │
  │  • Pay the rider AFTER verifying all your items          │
  │  • Do not pay before checking your order                 │
  │  • Refusing delivery after dispatch may affect           │
  │    your COD access for future orders                     │
  │                                                          │
  │  Delivering to:                                          │
  │  📍 Flat 5A, Prestige Shantiniketan, Koramangala         │
  │                                                          │
  │  Estimated:  40–55 minutes                               │
  │                                                          │
  │  ────────────────────────────────                        │
  │                                                          │
  │  [     Cancel     ]    [ ✓ Yes, Place Order ]            │
  │  (secondary, left)     (primary orange, right)           │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
  
  Back gesture blocked while modal is open — must use Cancel or Confirm button

STEP 4: User taps [ Yes, Place Order ]

  Button: loading spinner + "Placing order..."
  
  Backend: POST /api/payments/cod/confirm/ (actual confirm this time)
    Order.status → "confirmed"
    Order.payment_method → "cod"
    Order.payment_status → "pending"
    Order ID: "KR-1050"
    Delivery OTP generated + stored (same as online flow)
    FCM to store owner(s): "🛒 New COD Order #KR-1050! ₹791 cash"
    Rider assignment triggered

  Navigate: /cart/checkout/success (COD variant)

STEP 5: ORDER SUCCESS — COD VARIANT:
  Same celebration screen but payment info shows:
  "💵 Pay ₹791 cash to your rider upon delivery"
  "Keep exact change ready"
  (Instead of "₹791 paid via UPI")

STEP 6: COD — DURING DELIVERY:
  Rider marks: "Collected ₹791 cash" (tap in rider app)
  Backend: Order.payment_status → "collected_cod"
  Customer order history: "💵 ₹791 paid cash on delivery"

STEP 7: COD — CUSTOMER REFUSES AT DOOR:
  Rider taps: "Customer Refused Delivery"
  Optional: Rider notes reason (dropdown: Not at home / Changed mind / Wrong address / Other)
  Backend:
    Order.status → "refused_delivery"
    Order.payment_status → "not_collected"
    Rider still gets delivery fee (they made the trip)
    Customer refusal count incremented
    If refusal_count == 2: warning email/SMS sent
    If refusal_count == 3: COD disabled for account + admin notified
    
STEP 8: STORE CANCELS AFTER COD ORDER PLACED:
  Store cannot fulfil → cancels order
  Backend: full automatic cancellation
  COD orders: nothing to refund (no money taken)
  Customer: push notification "❌ Sharma Kirana cancelled your order. 
            Reason: Item out of stock. Order #KR-1050 cancelled."
  New order suggestion: "Shop from other nearby stores →"
```

---

### Order Success Screen `/cart/checkout/success`

```
ANIMATION TIMELINE (total 1400ms):
  0ms:    Screen appears white
  0ms:    Confetti Lottie starts (full-screen, colourful, celebratory)
  150ms:  Green circle draws in (stroke animation, 400ms)
  450ms:  Checkmark draws inside circle (200ms)
  650ms:  "Order Placed! 🎉" slides up from y:20 (spring, 300ms)
  800ms:  "#KR-1050" fades in (200ms)
  950ms:  ETA block fades in (200ms)
  1100ms: Store status chips animate in (stagger 100ms each)
  1200ms: Action buttons slide up (spring, 200ms)
  1400ms: Confetti slows and gracefully fades (next 2000ms)

CONTENT:
  ✅ (72px animated checkmark)
  "Order Placed! 🎉"  — 28px Plus Jakarta Sans ExtraBold
  "#KR-1050"          — 14px JetBrains Mono, #6B7280
  
  ────────────────────────────────
  ESTIMATED DELIVERY:
  "40–55 min"  — 28px Bold, #FF5733
  "to Flat 5A, Koramangala"  — 14px gray
  ────────────────────────────────
  
  STORE STATUS CHIPS (horizontal):
  COD orders: ✓ Sharma Kirana — Confirmed | ⏳ Green Basket — Awaiting
  
  PAYMENT CONFIRMATION LINE:
  Online: "✓ ₹791 paid  •  UPI (priya@okaxis)  •  Ref: pay_ABC123"
  COD:    "💵 Pay ₹791 cash to your rider on delivery"
  
  ────────────────────────────────

ACTIONS:
  [ 🗺 Track My Order ] — primary orange, full-width
  [ Continue Shopping ] — gray text link, centered below
  
  AUTO-REDIRECT:
  Countdown: "Tracking your order in 6..." (12px, gray, below actions)
  After 8s: auto-navigate to /orders/KR-1050/tracking
  Tapping "Track" goes immediately
  
  SHARE (optional, bottom):
  "Share order status" → native share: "I just ordered from Sharma Kirana on KiranaRush 🛵 #KiranaRush"
```

---

### Order Detail `/orders/:orderId`

```
HEADER:
  Back → /orders
  "Order #KR-1050"
  [Status badge — large, current status with colour]

STATUS TIMELINE (vertical, icon-based):
  ✅  Order Placed             April 4, 3:45 PM
  ✅  Payment Confirmed        3:45 PM  •  Ref: pay_ABC123
  ✅  Store Confirmed          3:47 PM  •  Sharma Kirana accepted
  ✅  Rider Assigned           3:49 PM  •  Ravi Kumar assigned
  🔄  Preparing Your Order     (pulsing — current)
  ⬜  Ready for Pickup
  ⬜  Order Picked Up
  ⬜  Out for Delivery
  ⬜  Delivered

RIDER CARD (appears after rider assigned):
  ┌────────────────────────────────────────────────────────────┐
  │  [Rider photo 52px]  Ravi Kumar            ⭐ 4.8         │
  │  ⚡ Hero Electric Optima  •  KA01 AB 1234                  │
  │                    [ 📞 Call ] [ 💬 Message ]              │
  └────────────────────────────────────────────────────────────┘
  Tapping Call: shows number + "Call" → dials from device
  Tapping Message: opens in-app chat OR WhatsApp (based on rider's preference)

ITEMS (grouped by store):
  STORE: Sharma Kirana
  ──────────────────────────────────────────────────
  [img 56px] Amul Butter 500g  × 2       ₹530
  [img 56px] Britannia Bread   × 1        ₹45
                     Store subtotal:     ₹575
  
  STORE: Green Basket Organics
  ──────────────────────────────────────────────────
  [img 56px] Alphonso Mangoes 1kg × 1    ₹220
                     Store subtotal:     ₹220

BILL (expandable):
  "Bill Details ▼"
  Item total:                ₹795
  Coupon (KIRANA50):        −₹50
  Delivery fee:              ₹40
  Platform fee:               ₹5
  GST:                        ₹1
  ═══════════════════════════════
  Total paid:               ₹791
  Payment: ✓ UPI (priya@okaxis)  •  Ref: pay_ABC123

DELIVERY ADDRESS:
  📍 Flat 5A, Prestige Shantiniketan, Koramangala — 560034

ACTIONS (dynamic, based on order status):
  
  IF STATUS: placed / confirmed (not yet rider-assigned):
    [ 🗺 Live Tracking ] — disabled, gray — "Tracking starts when rider is assigned"
    [ ✕ Cancel Order ] — red text button with confirmation
    
  IF STATUS: rider_assigned / picking_up / in_transit:
    [ 🗺 Track Live ] — PRIMARY, navigates to /orders/:id/tracking
    [ Cancel ] — shown but requires support contact
    
  IF STATUS: delivered:
    [ ⭐ Rate This Order ] — orange, if not yet rated
    [ 🔄 Order Again ] — adds all items back to cart
    [ 📥 Download Invoice ] — generates PDF with GST details
    [ Report an Issue ] — text link (wrong item, missing item, etc.)
    
  IF STATUS: cancelled:
    [ 🔄 Order Again ] — only if items still available
    Refund status: "₹791 refunded to your UPI — arrives in 3–5 days"

CANCELLATION FLOW:
  Tap "Cancel Order" → confirmation bottom sheet:
  ┌──────────────────────────────────────────────────────────┐
  │  Cancel this order?                                      │
  │  #KR-1050  •  ₹791                                       │
  │                                                          │
  │  Reason (required):                                      │
  │  ○ Changed my mind                                       │
  │  ○ Ordered by mistake                                    │
  │  ○ Delivery time too long                                │
  │  ○ Found a better option                                 │
  │  ○ Other                                                 │
  │                                                          │
  │  Refund: ₹791 will be refunded to UPI in 3–5 days.      │
  │                                                          │
  │  [ Keep Order ]    [ Cancel Order ]                      │
  └──────────────────────────────────────────────────────────┘
```

---

## 🔔 IN-APP NOTIFICATION CENTRE `/notifications`

```
BELL ICON (in all top headers):
  Unread count: red pill badge with white number
  If count > 9: shows "9+" badge
  Pulsing animation if count > 0 (scale 1→1.05→1, 2s loop)
  Tapping: navigates to /notifications (or slides open notification drawer)

NOTIFICATION LIST:

  "Notifications" header + "Mark all read" (right, orange text link)
  
  GROUPED BY TIME:
  ── TODAY ─────────────────────────────
  ── YESTERDAY ─────────────────────────
  ── THIS WEEK ─────────────────────────
  ── OLDER ─────────────────────────────
  
  Each notification:
  ┌────────────────────────────────────────────────────────────┐
  │ [Icon 40px]  Title (15px SemiBold)                         │
  │              Subtitle (13px, gray, 2 lines max)            │
  │              "2 min ago"  (right-aligned, 11px gray)       │
  │              ● (unread dot, top-right, orange, 8px)        │
  └────────────────────────────────────────────────────────────┘
  
  Unread: light blue-tinted background #F0F9FF, bold title
  Read: white background, normal weight
  
  SWIPE LEFT: reveals [ Mark Read ] (gray) | [ Delete ] (red)
  TAP: navigates to relevant screen + marks as read

NOTIFICATION TYPES & ICONS:
  🛵 #FF5733  — Rider updates (assigned, picked up, nearby, delivered)
  🏪 #2563EB  — Store updates (confirmed, item unavailable, store closed)
  ✅ #16A34A  — Order placed, payment success
  💳 #16A34A  — Payment / refund updates
  🎉 #FF5733  — Promotions, new stores nearby, offers
  ⚠️ #D97706  — Account alerts, COD warnings, expiry notices
  🔔 #6B7280  — System / admin messages

EMPTY STATE:
  Illustration: quiet bell with Zzz
  "You're all caught up!"
  "No new notifications right now."
```

---

## 📦 COMPLETE STOCK VALIDATION RULES

```
AT ADD-TO-CART:
  Check: product.stock > 0 AND product.is_available = True
  If OOS: "+" button replaced with "Notify me" ghost button
  If unavailable: gray overlay + "Currently unavailable"

AT CART VIEW:
  Background re-validation every 60 seconds (Websocket or polling)
  If item becomes OOS while viewing cart:
    Item card gets orange warning banner: "⚠️ Only 2 left — update quantity"
    Or red: "❌ Out of stock — remove to proceed"

AT CHECKOUT START (cart → address):
  Synchronous API validation for every item
  Blocking errors shown before proceeding

AT PAYMENT TAP:
  Re-validate again (race condition safety)
  If changed: show error before opening Razorpay

AT ORDER PLACEMENT (backend):
  Final atomic check within database transaction
  If any item OOS between last check and order placement:
    Transaction rolled back
    Error returned: specific item name + "went out of stock"
    No charge made (payment held until order confirmed)
    User sent back to cart with item flagged
```

---

*Built for Bharat. Designed for the neighbourhood. Powered by Django.*