import assert from 'node:assert/strict';
import { parseSTL } from '../dashboard/arm3d.js';

const triangle = new ArrayBuffer(134);
const view = new DataView(triangle);
view.setUint32(80, 1, true);
const vertices = [0, 0, 0, 1, 0, 0, 0, 1, 0];
vertices.forEach((value, i) => view.setFloat32(96 + i * 4, value, true));
const geometry = parseSTL(triangle);
assert.deepEqual([...geometry.getAttribute('position').array], vertices);
assert.deepEqual([...geometry.getAttribute('normal').array], [0, 0, 1, 0, 0, 1, 0, 0, 1]);
assert(Number.isFinite(geometry.boundingSphere.radius));
geometry.dispose();
assert.throws(() => parseSTL(triangle.slice(0, 133)), /binary STL/);
assert.throws(() => parseSTL(new ArrayBuffer(83)), /binary STL/);
view.setUint32(80, 0xffffffff, true);
assert.throws(() => parseSTL(triangle), /binary STL/);
console.log('arm3d STL checks pass');
