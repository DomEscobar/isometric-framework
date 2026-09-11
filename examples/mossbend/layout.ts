export const SIZE = 12;
export const projection = { tileWidth: 20, tileHeight: 10 };
export const origin = { x: 18, y: 130 };
export const trees = [
  { id: 'oak-west', c: 2, r: 1, height: 38 },
  { id: 'oak-mid', c: 1, r: 3, height: 36 },
  { id: 'oak-north', c: 10, r: 1, height: 42 },
  { id: 'oak-east', c: 10, r: 4, height: 34 },
  { id: 'oak-far', c: 10, r: 10, height: 39 },
  { id: 'oak-front', c: 2, r: 10, height: 36 },
];
export const center = (r: number) => r < 3 ? 5.5 : r < 8 ? 6.5 : 7.5;
export const wet = (c: number, r: number) => Math.abs(c - center(r)) <= .5;
export const deck = (c: number, r: number) => r === 6 && c >= 5 && c <= 8;
export const path = (c: number, r: number) => r === 6 || (c === 3 && r >= 3 && r <= 8) || (c === 9 && r >= 6 && r <= 9);
export const planted = (c: number, r: number) => trees.some(t => t.c === c && t.r === r);
export const spawn = { c: 2, r: 6 };
export const destination = { c: 9, r: 8 };
