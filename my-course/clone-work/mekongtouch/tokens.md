# MekongTouch — design tokens (đo từ CSS sống)
Font: Montserrat (400/700/750/800), fallback system-ui
Màu: ink #171814 · forest #1f3228 · forest-soft #33483b · paper #f4efe6
     white #fffdf8 · sand #ded1bf · clay #ba683c · orange #d96f32 · gold #c49b4d
     muted #71695e · line #17181429 · light-line #fffdf83d
Type: h1 clamp(2.6rem,6.2vw,4.8rem) 800 · h2 4.35rem@1280 / 3.5rem@980 / 2.25rem base 750
      eyebrow .78rem 800 uppercase · body 16px lh1.65 · button .9rem 800 min-h48 radius 8
Layout: section-inner min(100%-32px,1180px) · section-pad 72→104px · header 76px
Radius: 8px · Motion: fast .18s / base .42s / ease cubic-bezier(.22,1,.36,1)
Breakpoints: 420 · 719 · 720 · 980 (nav→burger, service split) · 1180 · 1280
Header: transparent gradient trên hero → .is-scrolled: paper 96% + border + logo dark
