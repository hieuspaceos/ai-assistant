# Trạng thái tương tác đã đo
1. country-gallery-item (4 thumb/nước ×3): click → ảnh chính đổi theo data-country-preview-src,
   crossfade 2 lớp (.country-main-image opacity+scale .42s/.72s), thumb active có viền.
2. video-play-trigger (#incentive): click → <dialog> modal mở, video controls + nút "Fermer"
   (dialog-close góc phải), click nền đóng.
3. mobile-menu-toggle: hiện ≤980px, bật nav dạng panel absolute (is-menu-open trên header).
4. site-header: transparent gradient khi top; cuộn >~40px → .is-scrolled (nền paper, chữ ink).
5. destination-marquee + logo-marquee: CSS animation translate 46s linear infinite,
   pause khi prefers-reduced-motion.
6. data-reveal: mọi khối fade+rising khi vào viewport (IntersectionObserver → is-visible).
7. about-gallery: mobile = carousel scroll-snap ngang; ≥1180px = lưới 3 cột tĩnh.
