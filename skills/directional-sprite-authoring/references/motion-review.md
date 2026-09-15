# I2V motion review

Define the intended motion before requesting image-to-video, then use the same
criteria to inspect the returned clip. The approved facing image and completed
video are still candidates: neither a detailed prompt nor a successful job proves
correct facing, consistent anatomy, usable contacts, or a clean loop.

| Action | Expected visible sequence | Review focus |
| --- | --- | --- |
| Animated idle | Neutral motion returning to the same root | Identity, stable facing, restrained root drift and clean seam |
| Walk | Contact A, pass A, contact B, pass B | Alternating anatomical limbs, fixed travel direction, foot sliding and seam |
| Jump | Takeoff, airborne phase, return | Coherent root; runtime elevation must not be duplicated in the pixels |
| Attack | Anticipation, strike, recovery | Same hand and equipment, readable reach, stable direction and explicit action end |
| Interact or cast | Preparation, effect motion, return | Target direction, silhouette clearance and explicit host action end |

Track anatomical limbs rather than temporary colors. Opposite walk contacts
exchange the leading and trailing legs while camera, scale, identity, equipment,
and travel direction remain fixed. An incorrect video frame never becomes a new
identity reference. A motion defect requires another I2V clip from the approved
facing; it is not repaired by generating or drawing a replacement frame.

Choose timestamps only after reviewing the decoded video. Runtime clips use one
FPS value, so use repeated accepted extracted frames for deliberate holds rather
than inventing per-frame-duration fields. Inspect the extracted cutouts and the
packed playback over at least two cycles. Background cleanup may change alpha and
edge pixels only; it must not redefine anatomy, scale, contacts, or motion.
