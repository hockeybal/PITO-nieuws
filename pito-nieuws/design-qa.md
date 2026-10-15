# Campaign design QA

Reference: supplied RTL/KPN screenshot of 13 October, 11:15:16. Compared together with reports/pito-campaign-desktop.png. Mobile verification: reports/campaign-features-mobile.png.

Scope: PITO adaptation of top-banner and paired side-display positions, preserving existing PITO site navigation and municipal hero. Not a full RTL replica.

Fixed: inherited beige article-banner background; oversized feature panels; duplicated video inside article when both outside displays are present; banner max width; alignment of side displays with the top campaign banner.

Verified: 970 × 250 desktop banner, no horizontal overflow at 1920 and 390 widths, muted video playback, functioning pause button, mobile hiding of side displays, loaded bird/logo/store assets. Existing location/source tests: 3 passed.

P3: native 4K master is not present; existing 1145px bird is adequate for its rendered size. Side creatives are shorter than the reference's full-height background skin.

final result: passed for responsive PITO campaign adaptation; pixel-exact RTL reproduction and a native 4K export are not claimed.
