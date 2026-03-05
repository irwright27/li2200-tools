from pathlib import Path
from typing import Any
from li2200tools.models import Header, Metadata, Results, Summary, Sensors, Record, Observations, LI2200File


def readfile(in_path: Path):

    in_path = Path(in_path)

    text_lines = in_path.read_text(errors="replace").splitlines(keepends=True)
    
    return text_lines


def head(line: str) -> Header:
    
    # Split first line into parts, to be used as key and value
    parts = line.strip().split("\t")

    # Create a variable as a Header dataclass
    header = Header(
        raw=line,
        key=parts[0],
        value=parts[1] if len(parts) > 1 else None
    )

    return header


def meta(lines: list[str]) -> Metadata:

    parsed = {}

    for line in lines:
        parts = line.rstrip("\n").split("\t")
        key = parts[0]
        value = parts[1] if len(parts) > 1 else None
        parsed[key] = value


    return Metadata(raw="".join(lines),
                    parsed=parsed
    )


def res(lines: list[str]) -> Results:

    parsed = {}

    for line in lines:
        parts = line.rstrip("\n").split("\t")
        key = parts[0]
        value = parts[1] if len(parts) > 1 else None
        parsed[key] = value


    return Results(raw="".join(lines),
                    parsed=parsed
    )


def _coerce_token(x: str) -> Any:
    """
    This function will make the reader try integer, then float, or keep as string
    """

    x = x.strip()
    if x == "":
        return ""
    
    try:
        if "." not in x and "e" not in x.lower():
            return int(x)   # First try int (bc MASK is an int and doesn't have a decimal)
    except ValueError:
        pass
    try:
        return float(x) # Then try float (bc the rest of your summaries have decimals)
    except ValueError:
        return x    # If neither work, x will be saved as a string


def summ(lines: list[str]) -> Summary:

    parsed: dict[str, tuple[Any, Any, Any, Any, Any]] = {}

    for line in lines:
        toks = line.rstrip("\n").split("\t")
        key = toks[0]
        vals = toks[1:]

        if len(vals) != 5:
            raise ValueError(f"Summary line {key!r} expected 5 ring values, got {len(vals)}: {line!r}")
        
        parsed[key] = tuple(_coerce_token(v) for v in vals) 

    return Summary(
        raw="".join(lines),
        parsed=parsed
    )


def sens(lines: list[str]) -> Sensors:
    """
    `lines` should include the marker line and subsequent SENSOR lines.
    """
    parsed: dict[str, tuple[str, tuple[Any, ...]]] = {}

    for line in lines:
        if line.strip() == "" or line.strip() == "### Contributing Sensors":
            continue

        toks = line.rstrip("\n").split("\t")

        # Expect: SENSOR <code> <model> <values...>
        if toks[0] != "SENSOR":
            continue

        code = toks[1].strip()          # W1, L2
        model = toks[2].strip()         # PCH5368, PAR1
        vals = tuple(_coerce_token(v) for v in toks[3:] if v.strip() != "")

        parsed[code] = (model, vals)

    return Sensors(
        raw="".join(lines),
        parsed={code: {"model": model, "values": vals} for code, (model, vals) in parsed.items()}
    )


def rec(line: str) -> Record:

    toks = line.rstrip("\n").split("\t")
    rtype = toks[0]

    # common fields
    seq = int(toks[1])
    dt = toks[2]
    sensor = toks[3]

    if rtype in {"A", "B"}:
        rings = [float(x) for x in toks[4:9]]
        parsed = {"seq": seq, "dt": dt, "sensor": sensor, "rings": rings}

    elif rtype == "G":
        parsed = {
            "seq": seq, "dt": dt, "gps_id": sensor,
            "lat": float(toks[4]), "lon": float(toks[5]), "alt": float(toks[6]),
            "gpsnum": int(toks[7]), "hdop": float(toks[8]), "fix_dt": toks[9],
        }

    elif rtype == "L":
        parsed = {"seq": seq, "dt": dt, "sensor": sensor, "value": float(toks[4])}

    else:
        parsed = {"seq": seq, "dt": dt, "sensor": sensor, "tokens": toks[4:]}

    return Record(
        raw=line,
        record_type=rtype,
        parsed=parsed)


def obs(lines: list[str]) -> Observations:

    records = tuple(
        rec(line)
        for line in lines[1:]
        if line.strip()
    )

    # Create a variable as a Observations dataclass

    return Observations(
        raw="".join(lines),
        records=records
    )


def read_li2200(in_path: Path):

    in_path = Path(in_path)
    text_lines = in_path.read_text(errors="replace").splitlines(keepends=True)

    raw = "".join(text_lines)

    targets = {
        "LAI",
        "MASK",
        "GAPS",
        "### Contributing Sensors",
        "### Observations"
    }

    brks = [
        i for i, ln in enumerate(text_lines)
        if ln.split("\t", 1)[0].strip() in targets
    ]

    # Unpacking brks for readability
    i_lai, i_mask, i_gaps, i_sensors, i_obs = brks

    # Parsing out dataclasses
    header = head(text_lines[0])
    metadata = meta(text_lines[1:i_lai])
    results = res(text_lines[i_lai:i_mask])
    summary = summ(text_lines[i_mask:i_gaps])
    sensors = sens(text_lines[i_gaps:i_sensors])
    observations = obs(text_lines[i_obs:])

    trailing = []
    for ln in reversed(text_lines):
        if not ln.strip():
            trailing.append(ln)
        else:
            break
    trailing.reverse()  

    return LI2200File(
        path=in_path,
        raw=raw,
        header=header,
        metadata=metadata,
        results=results,
        summary=summary,
        sensors=sensors,
        observations=observations,
        trailing=trailing,
    )


print(read_li2200('/Users/irwright/Desktop/li2200tools test/raw/C8-2.TXT').header)