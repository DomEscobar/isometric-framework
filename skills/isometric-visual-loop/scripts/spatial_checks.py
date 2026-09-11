"""Grid-cell authoring checks. Hosts own/export this semantic data, not pixel classifiers."""
from collections import deque


def require(ok, message):
    if not ok:
        raise ValueError(message)


def cell(value):
    require(isinstance(value, list) and len(value) == 3
            and all(type(n) is int for n in value[:2])
            and isinstance(value[2], str) and value[2], "Cell must be [column,row,floor]")
    return tuple(value)


def cells(values):
    require(isinstance(values, list) and values, "Nonempty cell list required")
    result = {cell(v) for v in values}
    require(len(result) == len(values), "Duplicate cells")
    return result


def optional_cells(values, message):
    require(isinstance(values, list), message)
    result = {cell(v) for v in values}
    require(len(result) == len(values), "Duplicate cells")
    return result


def indexed(values):
    require(isinstance(values, list), "Expected object list")
    result = {}
    for value in values:
        require(isinstance(value, dict), "Expected object list")
        ident = value.get("id")
        require(isinstance(ident, str) and ident and ident not in result, "Unique nonempty IDs required")
        result[ident] = value
    return result


def neighbors(p):
    c, r, floor = p
    return [(c+1, r, floor), (c-1, r, floor), (c, r+1, floor), (c, r-1, floor)]


def reachable(start, allowed):
    seen = {start} if start in allowed else set()
    queue = deque(seen)
    while queue:
        for p in neighbors(queue.popleft()):
            if p in allowed and p not in seen:
                seen.add(p)
                queue.append(p)
    return seen


def inspect(layout):
    require(isinstance(layout, dict), "Spatial layout must be an object")
    require(layout.get("version") == 1, "Spatial layout version must be 1")
    regions = indexed(layout["regions"])
    require(regions, "Semantic regions required")
    instances = indexed(layout["instances"])
    routes = indexed(layout["routes"])
    bridges = indexed(layout["bridges"])
    surfaces, by_region, findings = {}, {}, []

    def fail(code, ident, message):
        findings.append({"id": code+":"+ident, "instance": ident, "difference": message})

    water_under_bridges = {}
    for ident, region in regions.items():
        require(region.get("kind") in ("planting", "paving", "grass", "soil", "water", "deck"), "Unknown surface kind")
        by_region[ident] = cells(region["cells"])
        if region["kind"] == "water":
            water_under_bridges[ident] = optional_cells(region.get("underBridgeCells", []),
                                                        "underBridgeCells must be a list")
        else:
            require("underBridgeCells" not in region, "underBridgeCells only applies to water regions")
        require(not set(surfaces) & by_region[ident], "Base regions must not overlap; deck is a bridge overlay")
        surfaces.update({p: region["kind"] for p in by_region[ident]})
    walkable = {p for p, kind in surfaces.items() if kind != "water"}
    bridge_decks = set()
    for ident, bridge in bridges.items():
        deck = cells(bridge["deck"])
        bridge_decks |= deck
        landings = [cell(p) for p in bridge["landings"]]
        require(len(landings) == 2 and landings[0] != landings[1], "Bridge needs two distinct landings")
        if not set(landings) <= walkable:
            fail("landing-support", ident, "Both landings must touch supported non-water terrain")
        if not set(landings) <= deck or not deck <= reachable(landings[0], deck):
            fail("deck-continuity", ident, "Deck and both landings must form one axis-connected surface")
        overlay = {cell(p) for p in bridge["waterOverlayCells"]}
        if overlay & deck:
            fail("water-over-deck", ident, "Rendered water occupancy intersects the bridge deck")
        if not deck <= set(surfaces):
            fail("deck-outside-map", ident, "Deck extends outside declared terrain")
        walkable |= deck
    for ident, under_bridge in water_under_bridges.items():
        require(under_bridge <= bridge_decks,
                "Water underBridgeCells must be declared bridge deck cells")
        water = by_region[ident] | under_bridge
        if water != reachable(next(iter(water)), water):
            fail("water-connectivity", ident,
                 "Water region has disconnected or point-only bends; use separate region IDs for distinct ponds")
    solid, roots = set(), {}
    for ident, instance in instances.items():
        footprint = cells(instance["footprint"])
        roots[ident] = footprint
        require(instance.get("kind") in ("tree", "prop", "building"), "Unknown instance kind")
        require(type(instance.get("solid")) is bool, "Declare whether instance is solid")
        support = instance["support"]
        require(support in regions, "Unknown support region")
        if not footprint <= by_region[support] or not footprint <= walkable:
            fail("support", ident, "Footprint leaves its declared supported region")
        if instance["kind"] == "tree" and regions[support]["kind"] != "planting":
            fail("root-support", ident, "Tree roots require an intentional planting region")
        if instance["solid"]:
            if solid & footprint:
                fail("solid-overlap", ident, "Solid footprints overlap")
            solid |= footprint
    spawn = cell(layout["spawn"])
    connected_world = reachable(spawn, walkable-solid)
    if not connected_world:
        fail("spawn-support", "spawn", "Spawn must be supported and clear")
    route_union, reached = set(), set()
    for ident, route in routes.items():
        corridor = cells(route["cells"])
        radius = route["clearanceCells"]
        require(type(radius) is int and 0 <= radius <= 8, "clearanceCells must be an integer 0..8")
        expanded = {(c+dc, r+dr, f) for c, r, f in corridor
                    for dc in range(-radius, radius+1) for dr in range(-radius, radius+1)}
        if expanded & solid or not expanded <= walkable:
            fail("route-clearance", ident, "Reserved route including actor clearance intersects solids or unsupported terrain")
        start, goals = cell(route["start"]), cells(route["goals"])
        connected = reachable(start, corridor & (walkable-solid))
        if start not in connected_world or not goals <= connected or not corridor <= connected:
            fail("route-connectivity", ident, "Reserved route and every goal must connect to its start")
        reached |= connected
        route_union |= expanded
    for ident, instance in instances.items():
        approaches = {cell(p) for p in instance["approaches"]}
        if instance["kind"] == "building" and not approaches:
            fail("entrance-missing", ident, "Building needs a declared entrance approach")
        if approaches and (not approaches <= reached or approaches & solid
                           or any(not set(neighbors(p)) & roots[ident] for p in approaches)):
            fail("entrance-access", ident, "Every entrance approach must adjoin its building and a clear connected route")
        if instance["kind"] == "tree" and roots[ident] & route_union:
            fail("root-route", ident, "Tree root intersects reserved circulation")
    return {"passed": not findings, "findings": findings,
            "scope": {"regions": sorted(regions), "instances": sorted(instances), "routes": sorted(routes), "bridges": sorted(bridges)}}
