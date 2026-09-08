/** Authored vector artwork, no downloaded assets. Run with Node to regenerate woodland.svg. */
import { writeFileSync } from 'node:fs';

const parts = [];
const group = (x, y, content) => `<g transform="translate(${x} ${y})">${content}</g>`;
const path = (d, fill, extra = '') => `<path d="${d}" fill="${fill}" ${extra}/>`;
const ellipse = (cx, cy, rx, ry, fill) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="${fill}"/>`;
const mossColors = ['#8fae79', '#97b77e', '#89aa73'];
for (let i = 0; i < 7; i++) {
  const isPath = i >= 3 && i <= 5;
  const water = i === 6;
  let art = path('M64 0 128 32 64 64 0 32Z', water ? '#82aaa0' : isPath ? '#ddcca5' : mossColors[i]);
  if (water) {
    art += path('M20 31 41 21 47 24 26 34ZM73 42 91 33 96 36 78 45ZM55 16 67 10 72 13 60 19Z', '#a9c7b1');
    art += path('M35 47 46 42 50 44 39 49ZM92 24 102 19 106 21 96 26Z', '#73978e');
  } else {
    for (let j = 0; j < 15; j++) {
      const x = 14 + ((j * 23 + i * 13) % 98);
      const y = 9 + ((j * 13 + i * 7) % 45);
      if (Math.abs(x - 64) / 64 + Math.abs(y - 32) / 32 > .83) continue;
      art += isPath
        ? path(`M${x} ${y} l7 -3 5 2 -7 3Z`, j % 3 ? '#cab891' : '#efe1bc')
        : path(`M${x} ${y} l-3 -3 4 1 1 -5 2 5 4 -1 -3 4Z`, j % 3 ? '#789963' : '#bed094');
    }
    if (!isPath) art += path('M47 14 58 11 64 14 54 17ZM77 47 85 43 92 45 84 49Z', '#a9c487');
  }
  parts.push(group(i * 128, 0, art));
}

// A broad oak: warm bark, five sculpted canopy masses, sunlit upper-left facets.
let tree = ellipse(67, 149, 34, 9, '#29483835');
tree += path('M53 145 58 113 48 93 54 88 65 109 73 80 80 83 73 115 76 144 85 151 66 155 47 151Z', '#79553c');
tree += path('M58 143 63 112 59 95 65 108 68 140 62 150 53 150Z', '#ac7a4a');
tree += path('M42 111 19 102 9 81 17 63 15 49 36 28 59 27 72 15 97 25 110 45 108 60 119 77 110 99 88 106 65 118Z', '#315e47');
tree += path('M17 79 22 58 44 40 63 47 72 76 59 96 33 97Z', '#56865a');
tree += path('M35 38 45 22 68 15 87 22 99 39 91 56 68 66 43 57Z', '#6e985f');
tree += path('M70 64 90 51 108 62 116 80 105 98 86 99 71 86Z', '#48774e');
tree += path('M37 90 58 76 82 82 90 102 66 115 46 107Z', '#44774d');
tree += path('M23 55 37 40 47 43 36 51 34 63 21 70ZM47 29 67 20 80 25 61 28 54 40 42 43ZM78 67 89 59 101 65 88 67 82 78Z', '#92b573');
tree += path('M26 81 37 78 42 81 32 85ZM55 96 66 88 74 91 63 97ZM79 40 90 37 93 42 83 46Z', '#81a768');
tree += path('M72 122 79 117 78 129 71 135Z', '#476b44');
parts.push(group(0, 80, tree));

let mushrooms = ellipse(66, 151, 31, 7, '#2948382a');
mushrooms += path('M45 146 46 122 54 123 57 147 51 152Z', '#f2deaf');
mushrooms += path('M47 135 55 136 56 143 48 143Z', '#c7b388');
mushrooms += path('M27 124 34 111 48 103 61 108 74 125 66 132 39 133Z', '#b7553d');
mushrooms += path('M29 122 37 110 48 105 60 111 65 120 52 117 38 123Z', '#e18452');
mushrooms += ellipse(44, 113, 4, 2, '#f5d69b') + ellipse(58, 122, 5, 2, '#f5d69b') + ellipse(37, 125, 3, 2, '#f5d69b');
mushrooms += path('M78 150 79 134 85 132 90 152Z', '#e9d7ab');
mushrooms += path('M67 136 75 123 87 121 99 132 96 139 77 141Z', '#c96d44');
mushrooms += path('M70 133 77 125 87 123 91 128 78 130Z', '#eba96a');
mushrooms += ellipse(83, 130, 3, 2, '#fae1ac');
parts.push(group(128, 80, mushrooms));

let rock = ellipse(67, 150, 33, 8, '#2948382c');
rock += path('M29 140 38 114 63 104 88 113 102 138 85 153 50 155Z', '#7e9186');
rock += path('M29 140 38 114 63 104 74 120 58 139Z', '#bdc6a7');
rock += path('M58 139 74 120 88 113 102 138 85 153Z', '#94a18e');
rock += path('M33 140 52 136 60 141 76 140 84 149 58 154 43 150Z', '#5d8651');
rock += path('M40 140 50 136 57 140 48 143ZM68 145 76 143 78 146 69 148Z', '#9dba74');
parts.push(group(256, 80, rock));

let lantern = ellipse(64, 151, 19, 5, '#29483824');
lantern += ellipse(64, 125, 26, 25, '#ffdc7318') + ellipse(64, 125, 18, 18, '#ffdc7325');
lantern += path('M58 102 59 96 67 94 73 99 72 105 69 105 70 100 66 97 62 98 61 104Z', '#825d37');
lantern += path('M50 112 64 104 78 111 78 136 65 145 51 137Z', '#9b6538');
lantern += path('M50 112 64 104 78 111 64 118Z', '#e6ae58');
lantern += path('M54 117 63 121 63 139 55 134Z', '#ffe1a0');
lantern += path('M67 121 74 116 74 133 67 138Z', '#f7c864');
lantern += path('M58 120 60 121 60 130 58 129Z', '#fff5cc');
parts.push(group(384, 80, lantern));

// Four actual facings: a visible face in the south, hood and backpack in the north.
function ranger(direction, frame) {
  const back = direction === 'ne' || direction === 'nw';
  const right = direction === 'ne' || direction === 'se';
  const walking = frame >= 2 && frame <= 5;
  const phase = frame - 2;
  const bob = frame === 1 || (walking && phase % 2 === 1) ? -1 : 0;
  const stride = walking ? [3, 0, -3, 0][phase] : 0;
  let art = path(`M23 ${65 + stride} l8 -1 1 7 -11 0Z M35 ${65 - stride} l8 0 3 7 -11 0Z`, '#574838');
  let body = path('M22 42 40 41 47 61 38 68 22 65 17 59Z', '#355f49');
  body += path('M23 44 31 45 31 64 22 62 20 57Z', '#5e8860');
  body += path(`M${right ? 42 : 17} 46 l4 0 ${walking ? stride : 1} 11 -5 2Z`, '#eac38d');
  if (back) {
    body += path('M23 43 34 42 38 48 36 60 24 61 20 55Z', '#b07b48');
    body += path('M24 43 34 43 35 48 23 49Z', '#d5a268');
    body += path('M27 49 31 49 31 55 27 55Z', '#725839');
  } else {
    body += path('M23 40 40 39 41 45 32 48 23 44Z', '#e1b569');
    body += path('M36 44 40 45 45 56 40 58Z', '#d99752');
    body += path('M20 48 25 46 39 62 35 64Z', '#c08e55');
    body += path('M33 59 44 58 46 66 36 68Z', '#a46e41');
    body += path('M35 60 43 60 43 63 35 64Z', '#d6a066');
  }
  body += path('M23 25 40 23 45 31 43 41 33 45 23 39Z', back ? '#677747' : '#f0c792');
  if (back) body += path(right ? 'M40 31 46 32 45 38 41 39Z' : 'M21 31 26 32 25 39 21 37Z', '#e3bb82');
  if (!back) {
    const eye = right ? 39 : 27;
    body += path(`M${eye} 32 h3 v4 h-3Z`, '#354c3d');
    body += path(`M${right ? 42 : 22} 35 h4 v4 h-4Z`, '#dcac78');
    body += path(`M${right ? 34 : 28} 39 h5 v2 h-5Z`, '#d58b67');
  }
  body += path('M12 29 19 23 26 10 32 6 45 22 53 27 49 32 33 37 17 33Z', '#b58a42');
  body += path('M19 24 26 10 32 6 38 20 31 26Z', '#e8bf6e');
  body += path('M12 29 29 29 45 23 53 27 34 34 19 32Z', '#d8ad5c');
  body += path('M21 24 30 27 44 23 46 27 32 31 19 28Z', '#4c7150');
  body += path('M34 19 38 8 44 5 43 13 37 23Z', '#8ba971');
  body += path('M36 20 42 8 39 19Z', '#bdcc87');
  return art + group(0, bob + (frame === 6 ? -2 : 0), body);
}
for (const [row, direction] of ['ne', 'se', 'sw', 'nw'].entries()) {
  for (let frame = 0; frame < 7; frame++) parts.push(group(frame * 64, 256 + row * 80, ranger(direction, frame)));
}

writeFileSync(new URL('./woodland.svg', import.meta.url), `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="640" viewBox="0 0 1024 640">${parts.join('\n')}</svg>\n`);
