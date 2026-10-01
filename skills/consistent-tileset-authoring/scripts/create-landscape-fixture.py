"""Create a tiny diagnostic compositor fixture; it is not production art."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image

def dump(path, value): path.write_text(json.dumps(value, sort_keys=True), "utf8")
def hash(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def png(path, pixels): Image.fromarray(pixels).save(path)
def mask(path, selected):
    value = np.zeros((96, 192), np.uint8); value[selected] = 255; png(path, value); return {"path": path.name, "sha256": hash(path)}
def run(out):
    out = Path(out).resolve()
    if out.exists(): raise ValueError("fixture output already exists")
    out.mkdir(parents=True); base = np.zeros((96, 192, 4), np.uint8); base[:] = [28, 105, 42, 255]; png(out / "ground.png", base)
    earth = np.zeros_like(base); earth[:] = [124, 76, 28, 255]; png(out / "earth.png", earth)
    road = np.zeros((96,192), bool); road[42:54, 20:172] = True; road[12:84, 84:108] = True
    water = np.zeros_like(road); water[4:18, 148:180] = True
    edge = np.zeros_like(road); edge[42:54, 18:20] = True; edge[42:54, 20:22] = True
    root_a = np.zeros_like(road); root_a[64:80, 64:80] = True; root_b = np.zeros_like(road); root_b[16:48, 128:160] = True
    masks = {"route": mask(out/"route.png", road), "water": mask(out/"water.png", water), "routeWest": mask(out/"route-west.png", edge), "oakA": mask(out/"oak-a.png", root_a), "oakB": mask(out/"oak-b.png", root_b)}; masks["route"]["semantic"]="road"; masks["water"]["semantic"]="water"
    dump(out/"layout.json", {"kind":"synthetic-landscape-fixture"})
    geometry={"version":1,"coordinateSpace":"projected-pixels","projection":"isometric-2to1","origin":[-32,-48],"canvas":[192,96],"masks":masks,"layout":{"path":"layout.json","sha256":hash(out/"layout.json")},"instances":[{"id":"oak-a","anchor":[64,64],"transform":{"scale":[1,1]},"contactId":"oak-a-roots"},{"id":"oak-b","anchor":[128,32],"transform":{"scale":[2,2]},"contactId":"oak-b-roots"}]}; dump(out/"geometry.json", geometry)
    contact=np.zeros((2,2,4),np.uint8); contact[:]=[210,160,60,255]; png(out/"route-contact.png",contact)
    roots=np.zeros((8,8,4),np.uint8); roots[:]=[65,40,15,255]; png(out/"roots.png",roots)
    packed={"version":1,"groups":[{"id":"fixture","kind":"surface","composition":{"reference":"ground.png","origin":[-32,-48],"sourceScale":1}}]}; dump(out/"packed-art.json",packed)
    recipe={"version":1,"geometrySource":"geometry.json","surface":{"packedArt":"packed-art.json","groundPng":"ground.png"},"regionalMaterials":{"earth":"earth.png"},"regionalPaths":[{"id":"route","mask":"route","material":"earth"}],"contacts":[{"id":"route-west","kind":"pathExterior","insideMask":"route","outsideMask":"routeWest","allowedMask":"routeWest","orientation":"west","edgeWidth":2,"asset":"route-contact.png","anchor":[20,46],"assetAnchor":[1,1]}],"protectedMasks":["route","water"],"underlays":[{"id":"oak-a-roots","instanceId":"oak-a","family":"oak-roots","asset":"roots.png","assetAnchor":[0,0],"exportScale":[1,1],"allowedMask":"oakA"},{"id":"oak-b-roots","instanceId":"oak-b","family":"oak-roots","asset":"roots.png","assetAnchor":[0,0],"exportScale":[1,1],"allowedMask":"oakB"}]}; dump(out/"recipe.json",recipe)
    scene={"version":1,"name":"Landscape fixture","tileWidth":64,"tileHeight":32,"diagonal":False,"maxStepHeight":0,"map":[["grass"]*3,["grass"]*3,["grass"]*3],"tiles":{"grass":{"color":16777215,"walkable":True}},"entityTypes":{"oakSmall":{"visual":{"kind":"box","color":6697728,"height":32},"bodyHeight":32,"blocking":True},"oakLarge":{"visual":{"kind":"box","color":4460832,"height":64},"bodyHeight":64,"blocking":True}},"entities":[{"id":"oak-a","type":"oakSmall","c":0,"r":1},{"id":"oak-b","type":"oakLarge","c":2,"r":1}]}; dump(out/"scene.json",scene)
    return out
if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--out",required=True); a=p.parse_args()
    try: print(run(a.out))
    except ValueError as e: p.error(str(e))
