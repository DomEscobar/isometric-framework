"""Binds placed grid footprints to measured art geometry; neither side can shrink alone."""


def extent(cells):
    columns = [c for c, _, _ in cells]
    rows = [r for _, r, _ in cells]
    return max(columns)-min(columns)+1, max(rows)-min(rows)+1


def inspect(layout, contract):
    """Every placed instance must reserve the cells its calibrated artwork occupies.

    The art checker already forces a contract footprint wide enough for the decoded
    silhouette, so a placement that reserves fewer cells is art covering ground it
    never claimed. Checking every exported instance keeps the scope out of the
    author's hands.
    """
    assets = {a["id"]: a for a in contract["assets"]}
    findings = []

    def fail(code, ident, message):
        findings.append({"id": code+":"+ident, "instance": ident, "difference": message})

    for instance in layout["instances"]:
        ident = instance["id"]
        name = instance.get("asset")
        if not isinstance(name, str) or not name:
            fail("asset-unnamed", ident, "Placed instance must name the calibrated art asset it renders")
            continue
        if name not in assets:
            fail("asset-unknown", ident, "Named art asset is absent from the measured contract: "+name)
            continue
        columns, rows = extent(instance["footprint"])
        declared = assets[name]["footprint"]
        if (columns, rows) != (declared["columns"], declared["rows"]):
            fail("footprint-disagreement", ident,
                 f"Placement reserves {columns}x{rows} cells but calibrated art {name} measures "
                 f"{declared['columns']}x{declared['rows']}; reserve the cells the artwork occupies "
                 f"instead of letting it cover neighbouring ground")
    return {"passed": not findings, "findings": findings}
