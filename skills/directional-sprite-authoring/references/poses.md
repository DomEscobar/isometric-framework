# Action phases and pose consistency

Define the motion before requesting image-to-video. The approved facing image and
the returned video are candidates: neither a detailed prompt nor a completed job
establishes correct facing, consistent anatomy or smooth playback.

## Phase plans

| Action | Small starting plan | What to inspect |
| --- | --- | --- |
| Idle | One neutral frame per required direction | Identity, root, visibly distinct required views |
| Walk | Contact A, passing A, contact B, passing B | Alternating limbs, consistent travel, loop seam and foot sliding |
| Jump | One airborne pose per direction initially | Raised feet without doubled flight offset, landing returns to idle/walk |
| Attack | Anticipation, strike, recovery | Same hand/weapon, readable aim and reach, host-driven effect timing |
| Interact/cast | Reach/preparation, effect pose, return | Target direction, silhouette clearance, explicit host action end |

For opposite walk contacts, track anatomical limbs rather than changing colors:
the leading and trailing legs exchange roles while camera and travel direction
stay fixed. Preserve character identity, equipment hands and body scale through
the passing poses. Use the approved facing image as the authority for an I2V
replacement; do not let an incorrect generated video frame redefine the motion.

Reuse or repeat an approved frame for timing holds instead of regenerating an
identical pose. Runtime clips use one FPS value; repeated frame IDs can lengthen
a hold. Do not add per-frame-duration fields to the current manifest.

Use a consistent character/world scale, not mandatory real-world anatomy. Inspect
body landmarks separately from moving limbs and equipment; never auto-fit each
silhouette. Apply the skill's visual review and repair gate to the assembled clip,
including after normalization or background cleanup. Preserve both frame
comparisons and playback evidence; unresolved defects remain unaccepted.
