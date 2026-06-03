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
    summary = summ(text_lines[i_mask:i_gaps + 1])
    sensors = sens(text_lines[i_sensors:i_obs])
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


def unparse_header(header: Header) -> str:
    """
    Convert a Header dataclass back into one LI-2200 header line.
    Output string includes all changes made to dataclass after initial reading
    """
    if header.value is None:
        return f"{header.key}\n"
    return f"{header.key}\t{header.value}\n"


def unparse_meta(meta: Metadata) -> str:
    """
    Convert a Metadata dataclass back into LI-2200 file string format
    Output string includes all changes made to dataclass after initial reading
    """
    if meta.parsed is None:
        raise ValueError("Metadata.parsed is empty; cannot unparse metadata")
    
    unp = ""
    for k in meta.parsed:
        unp += f"{k}\t{meta.parsed[k]}\n"

    return unp


def unparse_res(res: Results) -> str:
    """
    Convert a Results dataclass back into LI-2200 file string format
    Output string includes all changes made to dataclass after initial reading
    """
    if res.parsed is None:
        raise ValueError("Results.parsed is empty; cannot unparse Results")
    
    unp = ""
    for k in res.parsed:
        unp += f"{k}\t{res.parsed[k]}\n"

    return unp


def unparse_summ(summ: Summary) -> str:
    """
    Convert a Summary dataclass back into LI-2200 file string format
    Output string includes all changes made to dataclass after initial reading
    """
    if summ.parsed is None:
        raise ValueError("Summary.parsed is empty; cannot unparse file summary")
    
    unp = ""
    for k in summ.parsed:
        unp += f"{k}\t{summ.parsed[k][0]}\t{summ.parsed[k][1]}\t{summ.parsed[k][2]}\t{summ.parsed[k][3]}\t{summ.parsed[k][4]}\n"

    return unp


def unparse_sens(sens: Sensors) -> str:
    """
    Convert a Sensors dataclass back into LI-2200 file string format.
    """
    if sens.parsed is None:
        raise ValueError("Sensors.parsed is empty; cannot unparse sensors")

    lines = ["### Contributing Sensors\n"]
    for code, sensor in sens.parsed.items():
        model = sensor.get("model")
        values = sensor.get("values", ())
        parts = ["SENSOR", code, model, *values]
        lines.append("\t".join(str(part) for part in parts) + "\n")

    return "".join(lines)


def unparse_record(record: Record) -> str:
    """
    Convert one Record dataclass back into one LI-2200 observation line.

    If the original raw line is available, preserve it exactly. This keeps
    filtered files from changing numeric formatting such as trailing zeroes.
    """
    if record.raw:
        return record.raw if record.raw.endswith("\n") else f"{record.raw}\n"

    if record.parsed is None:
        raise ValueError("Record.parsed is empty; cannot unparse record")

    parsed = record.parsed
    rtype = record.record_type

    if rtype in {"A", "B"}:
        parts = [rtype, parsed["seq"], parsed["dt"], parsed["sensor"], *parsed["rings"]]
    elif rtype == "G":
        parts = [
            rtype,
            parsed["seq"],
            parsed["dt"],
            parsed["gps_id"],
            parsed["lat"],
            parsed["lon"],
            parsed["alt"],
            parsed["gpsnum"],
            parsed["hdop"],
            parsed["fix_dt"],
        ]
    elif rtype == "L":
        parts = [rtype, parsed["seq"], parsed["dt"], parsed["sensor"], parsed["value"]]
    else:
        parts = [
            rtype,
            parsed["seq"],
            parsed["dt"],
            parsed["sensor"],
            *parsed.get("tokens", ()),
        ]

    return "\t".join(str(part) for part in parts) + "\n"


def unparse_obs(obs: Observations) -> str:
    """
    Convert an Observations dataclass back into LI-2200 file string format.
    """
    lines = ["### Observations\n"]
    lines.extend(unparse_record(record) for record in obs.records)
    return "".join(lines)


def unparse_li2200(file: LI2200File) -> str:
    """
    Convert a whole LI2200File object back into LI-2200 text format.
    """
    return "".join(
        [
            unparse_header(file.header),
            unparse_meta(file.metadata),
            unparse_res(file.results),
            unparse_summ(file.summary),
            "\n",
            unparse_sens(file.sensors),
            "\n\n",
            unparse_obs(file.observations),
            "".join(file.trailing),
        ]
    )


def write_li2200(
    file: LI2200File,
    out_path: Path,
    header_match_filename: bool = False,
    overwrite: bool = False,
) -> Path:
    """
    Write a LI2200File object to a text file and return the output path.

    Args:
        file: The input file in LI2200File object format.
        out_path: Path where the LI2200 file should be written.
        header_match_filename: If True, update the LAI_FILE header value to
            match out_path's filename without the file extension.
        overwrite: If True, replace an existing output file. Defaults to False.
    """
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {out_path}")

    if header_match_filename:
        from li2200tools.engine import rename_file

        file = rename_file(file, out_path.stem)

    out_path.write_text(unparse_li2200(file))
    return out_path
