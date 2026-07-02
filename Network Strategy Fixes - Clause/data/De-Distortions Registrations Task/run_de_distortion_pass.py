"""De-distortion pass for UK luxury/supercar registrations (2022-2025).

Agreed treatment policy (signed off in chat):

1. Factory / HQ / production / engineering (reference list, delete_from_fit, high
   confidence)  -> HELD to the local postcode-DISTRICT average (e.g. GU21 4 is held
   to the mean of the other observed GU21 sectors), with fallback to the postcode
   area mean then the national median sector. This replaces the distorted factory
   value with an estimate of genuine local demand instead of a hard zero. The
   removed excess is NOT redistributed (factory/press/demo plates are not buyers
   displaced from elsewhere).
2. Dealer sectors (competitor + McLaren + dealer changes) -> DEMO REMOVAL via a
   banded reduction measured against the local postcode-area norm:
       ratio <= 2x  -> 0%   (no distortion, leave alone)
       2-4x         -> 20%  (mild)
       4-8x         -> 50%  (medium)
       > 8x         -> 80%  (strong, per user)
   Reduction is floored at the local area baseline so we never push a dealer
   sector below genuine local demand. Removed demo volume is NOT redistributed.
3. Finance / leasing hotspots (reference list rows whose category contains
   finance_lease, incl. the importer/finance review rows) -> HELD to the local
   area baseline and the EXCESS is REDISTRIBUTED across the whole UK in proportion
   to that brand+sub-segment's clean registration distribution. Volume conserved.
4. review_before_delete, non-finance (Aston Martin Works, Newport Pagnell) -> KEEP
   and flag for human review only (mostly genuine dealership/heritage sales).
5. A statistical multi-brand finance/admin detector is produced as a REVIEW list
   only; it is never auto-applied.

Outputs: one canonical cleaned annual file (sector x sub-model x year), a matching
monthly file, and full audit trails. Raw source workbooks are never modified.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

TASK_DIR = Path(__file__).resolve().parent

RAW_REGS = TASK_DIR / "UK REGISTRATIONS NOT DE-DEDISTORTED BUT SUB SEGMENT - 2022 to 2025.xlsx"
SEGMENT_LOOKUP = TASK_DIR / "New Segment Verified - June 2026 - for analysis.xlsx"
MCLAREN_DEALERS = TASK_DIR / "McLaren UK Database.xlsx"
COMPETITOR_DEALERS = TASK_DIR / "Competitor_location_data_UPDATED_2026_v2 (1).xlsx"
DEALER_CHANGES = TASK_DIR / "Competitor_dealer_changes_2022_2026_Includes_McLaren_UPDATED (3).xlsx"
REFERENCE_SITES = TASK_DIR / "uk_supercar_non_buyer_and_finance_sites (2).xlsx"

PRIMARY_BRANDS = {
    "aston martin": "Aston Martin",
    "bentley": "Bentley",
    "ferrari": "Ferrari",
    "lamborghini": "Lamborghini",
    "mclaren": "McLaren",
    "rolls-royce": "Rolls-Royce",
    "rolls royce": "Rolls-Royce",
}
PRIMARY_BRAND_KEYS = {key.casefold() for key in PRIMARY_BRANDS.values()}

EXCLUDED_BRAND_PATTERNS = (
    "porsche",
    "maserati",
    "mercedes",
    "amg",
    "ford",
)

# Segments that are not part of the buyer-share fit (no comparable demand curve yet).
EXCLUDED_SEGMENTS = {"hypercar"}

# Offshore islands have no road drive-time to a GB dealer -> excluded from the GB fit.
ISLAND_AREAS = {"JE", "GY", "IM"}

# --- Manual overrides added after human review of the statistical candidates ---
# LE7 = Sytner Lamborghini + Bentley Leicester (Watermead Business Park, LE7 1PF),
# a real dealer missing from the competitor location file -> treat as dealer demo.
ADDITIONAL_DEALER_SECTORS = {
    ("lamborghini", "LE7"), ("lamborghini", "LE7 1"),
    ("bentley", "LE7"), ("bentley", "LE7 1"),
}
# BD1 = central Bradford supercar hire/trade cluster (ABM Exclusive Supercar Hire,
# CFA Prestige) -> not buyer geography; treat as finance/trade hotspot (redistribute).
ADDITIONAL_FINANCE_SECTORS = {
    ("bentley", "BD1"), ("bentley", "BD1 5"),
    ("lamborghini", "BD1"), ("lamborghini", "BD1 5"),
    ("rolls-royce", "BD1"), ("rolls-royce", "BD1 5"),
    # SW1P 2 (Westminster): 103 Lamborghinis, 96% single-brand, no dealer (HR Owen
    # Lamborghini London is SW7 3TD) -> administrative/finance/fleet cluster.
    ("lamborghini", "SW1P 2"),
}

EPS = 1e-9


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def norm_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def norm_key(value: object) -> str:
    return norm_text(value).casefold()


def canonical_brand(value: object) -> str:
    key = norm_key(value).replace("\u2013", "-")
    return PRIMARY_BRANDS.get(key, norm_text(value))


def clean_sector(value: object) -> str:
    """Normalise a postcode-sector string like 'AB10 1' / 'ab10  1'."""
    text = norm_text(value).upper()
    return re.sub(r"\s+", " ", text)


def postcode_sector_from_full_postcode(value: object) -> str:
    text = norm_text(value).upper()
    if not text:
        return ""
    match = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", text)
    if not match:
        return ""
    pc = re.sub(r"\s+", "", match.group(1))
    return f"{pc[:-3]} {pc[-3]}".strip()


def read_excel_safe(path: Path, **kwargs) -> pd.DataFrame:
    """Read an xlsx even if it is locked open in Excel (OneDrive), via a temp copy."""
    try:
        return pd.read_excel(path, engine="openpyxl", **kwargs)
    except PermissionError:
        tmp = Path(tempfile.gettempdir()) / f"_ddp_{path.stem}.xlsx"
        shutil.copy2(path, tmp)
        return pd.read_excel(tmp, engine="openpyxl", **kwargs)


def severity_band(ratio: float) -> tuple[str, float]:
    if not np.isfinite(ratio) or ratio <= 2.0:
        return "none", 0.0
    if ratio <= 4.0:
        return "mild", 0.20
    if ratio <= 8.0:
        return "medium", 0.50
    return "strong", 0.80


# --------------------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------------------
def load_long_registrations() -> pd.DataFrame:
    df = read_excel_safe(RAW_REGS, sheet_name="Sheet1")
    month_cols = [c for c in df.columns if re.match(r"^202[2-5]/\d{2}$", str(c))]
    keep_id = [
        "Postcode Sector-Number",
        "Make",
        "Model Group",
        "Model",
        "Sub Model",
        "Sub_Segment",
    ]
    long_df = df.melt(
        id_vars=keep_id,
        value_vars=month_cols,
        var_name="month",
        value_name="registrations",
    )
    long_df["registrations"] = pd.to_numeric(long_df["registrations"], errors="coerce").fillna(0.0)
    long_df = long_df[long_df["registrations"] > 0].copy()
    long_df["month"] = long_df["month"].str.replace("/", "-", regex=False)
    long_df["year"] = long_df["month"].str[:4].astype(int)
    long_df["sector"] = long_df["Postcode Sector-Number"].map(clean_sector)
    long_df["district"] = long_df["sector"].str.rsplit(" ", n=1).str[0]
    # Area = leading alphabetic part of the outward code (e.g. CW1 -> CW, AB10 1 -> AB).
    # Derived from the postcode itself so the run never depends on a separate Area column.
    long_df["area"] = long_df["district"].str.extract(r"^([A-Za-z]+)", expand=False).fillna("").str.upper()
    long_df["brand"] = long_df["Make"].map(canonical_brand)
    long_df["brand_key"] = long_df["brand"].map(norm_key)
    long_df["sub_model_key"] = long_df["Sub Model"].map(norm_key)
    long_df["sub_segment"] = long_df["Sub_Segment"].map(norm_text)
    long_df["sub_segment_key"] = long_df["sub_segment"].map(norm_key)
    return long_df


def load_segment_lookup() -> tuple[set[tuple[str, str]], pd.DataFrame]:
    lookup = read_excel_safe(SEGMENT_LOOKUP, sheet_name="Sheet1")
    lookup["brand"] = lookup["Brand"].map(canonical_brand)
    lookup["brand_key"] = lookup["brand"].map(norm_key)
    lookup["sub_model_key"] = lookup["Sub Model"].map(norm_key)
    lookup["segment_key"] = lookup["Segment"].map(norm_key)
    lookup["include_primary_fit"] = lookup["brand_key"].isin(PRIMARY_BRAND_KEYS) & ~lookup[
        "segment_key"
    ].isin(EXCLUDED_SEGMENTS)
    approved = set(
        lookup.loc[lookup["include_primary_fit"], ["brand_key", "sub_model_key"]].itertuples(
            index=False, name=None
        )
    )
    return approved, lookup


def load_reference_sites() -> tuple[dict[str, set[tuple[str, str]]], pd.DataFrame]:
    ref = read_excel_safe(REFERENCE_SITES, sheet_name="reference_sites")
    ref["brand"] = ref["brand"].map(canonical_brand)
    ref["brand_key"] = ref["brand"].map(norm_key)
    ref["sector"] = ref["postcode_sector"].map(clean_sector)
    ref["treatment_key"] = ref["recommended_treatment"].map(norm_key)
    ref["confidence_key"] = ref["confidence"].map(norm_key)
    ref["category_key"] = ref["category"].map(norm_key)

    is_finance = ref["category_key"].str.contains("finance", na=False)
    is_delete = (ref["treatment_key"] == "delete_from_fit") & (ref["confidence_key"] == "high")
    is_review_keep = (ref["treatment_key"] == "review_before_delete") & ~is_finance

    def pairs(mask: pd.Series) -> set[tuple[str, str]]:
        return set(ref.loc[mask, ["brand_key", "sector"]].itertuples(index=False, name=None))

    classes = {
        "delete": pairs(is_delete & ~is_finance),
        "finance": pairs(is_finance),
        "review_keep": pairs(is_review_keep),
    }
    ref["resolved_class"] = np.select(
        [is_delete & ~is_finance, is_finance, is_review_keep],
        ["delete", "finance", "review_keep"],
        default="keep_flag",
    )
    return classes, ref


def load_dealer_pairs() -> tuple[set[tuple[str, str]], dict[str, object]]:
    pairs: set[tuple[str, str]] = set()
    info: dict[str, object] = {}

    competitor = read_excel_safe(COMPETITOR_DEALERS, sheet_name="Dealers")
    competitor["brand_key"] = competitor["OEM/Brand"].map(canonical_brand).map(norm_key)
    competitor["sector"] = competitor["PostCode"].map(postcode_sector_from_full_postcode)
    comp_pairs = {
        (b, s) for b, s in zip(competitor["brand_key"], competitor["sector"]) if s
    }
    pairs |= comp_pairs
    info["competitor_dealer_pairs"] = len(comp_pairs)

    changes = read_excel_safe(DEALER_CHANGES, sheet_name="Deltas")
    changes["brand_key"] = changes["Brand"].map(canonical_brand).map(norm_key)
    change_pairs: set[tuple[str, str]] = set()
    for col in ("PostCode_Before", "PostCode_After"):
        sectors = changes[col].map(postcode_sector_from_full_postcode)
        change_pairs |= {(b, s) for b, s in zip(changes["brand_key"], sectors) if s}
    pairs |= change_pairs
    info["dealer_change_pairs"] = len(change_pairs)

    mclaren = read_excel_safe(MCLAREN_DEALERS, sheet_name="Sheet1")
    pc_col = next((c for c in mclaren.columns if norm_key(c) in {"postcode", "post code", "post_code"}), None)
    mc_pairs: set[tuple[str, str]] = set()
    if pc_col is not None:
        sectors = mclaren[pc_col].map(postcode_sector_from_full_postcode)
        mc_pairs = {("mclaren", s) for s in sectors if s}
    pairs |= mc_pairs
    info["mclaren_dealer_pairs"] = len(mc_pairs)
    info["mclaren_postcode_column"] = pc_col
    info["mclaren_dealer_sectors"] = sorted({s for _, s in mc_pairs})

    pairs |= ADDITIONAL_DEALER_SECTORS
    info["review_added_dealer_pairs"] = sorted(ADDITIONAL_DEALER_SECTORS)
    info["total_dealer_pairs"] = len(pairs)
    return pairs, info


# --------------------------------------------------------------------------------------
# Primary-fit split
# --------------------------------------------------------------------------------------
def build_primary_fit(long_df: pd.DataFrame, approved: set[tuple[str, str]]):
    long_df = long_df.copy()
    long_df["primary_brand"] = long_df["brand_key"].isin(PRIMARY_BRAND_KEYS)
    long_df["excluded_brand"] = long_df["brand_key"].apply(
        lambda x: any(p in x for p in EXCLUDED_BRAND_PATTERNS)
    )
    long_df["approved_product"] = list(
        (bk, sm) in approved for bk, sm in zip(long_df["brand_key"], long_df["sub_model_key"])
    )
    long_df["is_island"] = long_df["area"].isin(ISLAND_AREAS)
    long_df["exclusion_reason"] = np.where(
        long_df["is_island"], "offshore_island_no_gb_drive_time",
        np.where(~long_df["primary_brand"], "non_primary_brand",
                 np.where(~long_df["approved_product"], "non_fit_product_or_hypercar", "")),
    )
    keep_mask = long_df["primary_brand"] & long_df["approved_product"] & ~long_df["is_island"]
    primary = long_df[keep_mask].copy()
    excluded = long_df[~keep_mask].copy()

    unmatched = (
        long_df[long_df["primary_brand"] & ~long_df["approved_product"]]
        .groupby(["brand", "Sub Model", "sub_segment"], as_index=False)["registrations"]
        .sum()
        .sort_values("registrations", ascending=False)
    )
    return primary, excluded, unmatched


# --------------------------------------------------------------------------------------
# Core treatment engine (annual grain, mapped back to months)
# --------------------------------------------------------------------------------------
def apply_treatments(primary: pd.DataFrame, classes: dict, dealer_pairs: set):
    df = primary.copy()

    delete_set = classes["delete"]
    finance_set = classes["finance"] | ADDITIONAL_FINANCE_SECTORS
    review_keep_set = classes["review_keep"]

    # The registration data is mixed granularity: some rows are full sectors ("AB10 1")
    # and some are district-only ("CW1", "LE7"). Treatment sites are stored as full
    # sectors. We therefore match full-sector rows at sector level (precise, so genuine
    # neighbours are not swept in) and district-only rows at district level (so e.g. the
    # Bentley Crewe factory recorded as "CW1" still matches reference sector "CW1 3").
    def to_district(s: str) -> str:
        return s.rsplit(" ", 1)[0]

    delete_d = {(b, to_district(s)) for b, s in delete_set}
    finance_d = {(b, to_district(s)) for b, s in finance_set}
    dealer_d = {(b, to_district(s)) for b, s in dealer_pairs}
    review_d = {(b, to_district(s)) for b, s in review_keep_set}

    def classify(brand_key: str, sector: str) -> str:
        if " " in sector:  # full sector -> exact sector match
            pair = (brand_key, sector)
            if pair in delete_set:
                return "factory_hold"
            if pair in finance_set:
                return "finance"
            if pair in dealer_pairs:
                return "dealer"
            if pair in review_keep_set:
                return "review_keep"
            return "keep"
        d = (brand_key, sector)  # district-only -> district match
        if d in delete_d:
            return "factory_hold"
        if d in finance_d:
            return "finance"
        if d in dealer_d:
            return "dealer"
        if d in review_d:
            return "review_keep"
        return "keep"

    df["treatment_class"] = [classify(b, s) for b, s in zip(df["brand_key"], df["sector"])]

    # ---- annual aggregate at row identity: sector x brand x sub-model x year ----
    row_keys = ["sector", "district", "area", "brand", "brand_key", "Model Group", "Model",
                "Sub Model", "sub_model_key", "sub_segment", "sub_segment_key", "year",
                "treatment_class"]
    annual = df.groupby(row_keys, as_index=False)["registrations"].sum()
    annual = annual.rename(columns={"registrations": "original_annual"})

    # sector-level totals (sum over sub-models) for baseline / ratio decisions
    sector_lvl = (
        annual.groupby(["brand_key", "sub_segment_key", "district", "area", "sector", "year", "treatment_class"],
                       as_index=False)["original_annual"].sum()
        .rename(columns={"original_annual": "sector_annual"})
    )

    undistorted = sector_lvl[sector_lvl["treatment_class"].isin(["keep", "review_keep"])]

    # local district baseline = mean undistorted sector total in same district/brand/sub-seg/year
    district_baseline = (
        undistorted.groupby(["brand_key", "sub_segment_key", "district", "year"], as_index=False)["sector_annual"]
        .mean().rename(columns={"sector_annual": "district_baseline"})
    )
    # area baseline = mean undistorted sector total in same area/brand/sub-seg/year
    area_baseline = (
        undistorted.groupby(["brand_key", "sub_segment_key", "area", "year"], as_index=False)["sector_annual"]
        .mean().rename(columns={"sector_annual": "area_baseline"})
    )
    # national fallback = median undistorted sector total for brand/sub-seg/year
    nat_baseline = (
        undistorted.groupby(["brand_key", "sub_segment_key", "year"], as_index=False)["sector_annual"]
        .median().rename(columns={"sector_annual": "nat_baseline"})
    )

    sector_lvl = sector_lvl.merge(district_baseline, on=["brand_key", "sub_segment_key", "district", "year"], how="left")
    sector_lvl = sector_lvl.merge(area_baseline, on=["brand_key", "sub_segment_key", "area", "year"], how="left")
    sector_lvl = sector_lvl.merge(nat_baseline, on=["brand_key", "sub_segment_key", "year"], how="left")
    # dealer/finance baseline: area -> national, floored at 1 (protects genuine local demand)
    sector_lvl["baseline"] = sector_lvl["area_baseline"].fillna(sector_lvl["nat_baseline"]).fillna(1.0)
    sector_lvl["baseline"] = sector_lvl["baseline"].clip(lower=1.0)
    # factory hold baseline: district -> area -> national (NOT floored; genuine local demand can be ~0)
    sector_lvl["local_baseline"] = (
        sector_lvl["district_baseline"]
        .fillna(sector_lvl["area_baseline"])
        .fillna(sector_lvl["nat_baseline"])
        .fillna(0.0)
        .clip(lower=0.0)
    )

    # ---- decide sector-level scaling factor + excess for redistribution ----
    def decide(row):
        tc = row["treatment_class"]
        s = row["sector_annual"]
        base = row["baseline"]
        if tc == "factory_hold":
            lbase = row["local_baseline"]
            held = min(s, lbase)
            factor = held / s if s > EPS else 0.0
            ratio = s / max(lbase, EPS)
            return pd.Series({"factor": factor, "excess": 0.0, "ratio": ratio,
                              "band": "factory_hold_district_avg", "reduction": 1.0 - factor,
                              "baseline_used": lbase})
        if tc == "dealer":
            ratio = s / max(base, EPS)
            band, red = severity_band(ratio)
            target = max(s * (1.0 - red), base)
            target = min(s, target)  # never increase
            factor = target / s if s > EPS else 1.0
            return pd.Series({"factor": factor, "excess": 0.0, "ratio": ratio,
                              "band": band, "reduction": 1.0 - factor, "baseline_used": base})
        if tc == "finance":
            held = min(s, base)
            excess = max(s - held, 0.0)
            factor = held / s if s > EPS else 1.0
            ratio = s / max(base, EPS)
            return pd.Series({"factor": factor, "excess": excess, "ratio": ratio,
                              "band": "finance_redistribute", "reduction": 1.0 - factor,
                              "baseline_used": base})
        return pd.Series({"factor": 1.0, "excess": 0.0, "ratio": np.nan,
                          "band": "keep", "reduction": 0.0, "baseline_used": base})

    decided = sector_lvl.join(sector_lvl.apply(decide, axis=1))

    # map sector factor back onto annual sub-model rows
    factor_map = decided[["brand_key", "sub_segment_key", "sector", "year", "factor",
                          "ratio", "band", "reduction", "baseline_used", "sector_annual", "excess"]]
    annual = annual.merge(factor_map, on=["brand_key", "sub_segment_key", "sector", "year"], how="left")
    annual["factor"] = annual["factor"].fillna(1.0)
    annual["cleaned_annual"] = annual["original_annual"] * annual["factor"]

    # ---- redistribution of finance excess across clean UK distribution ----
    excess_pool = (
        decided[decided["excess"] > 0]
        .groupby(["brand_key", "sub_segment_key", "year"], as_index=False)["excess"].sum()
        .rename(columns={"excess": "excess_total"})
    )

    recip_mask = annual["treatment_class"].isin(["keep", "review_keep"]) & (annual["cleaned_annual"] > 0)
    annual["redistributed_in"] = 0.0
    if len(excess_pool):
        recip = annual[recip_mask].copy()
        recip = recip.merge(excess_pool, on=["brand_key", "sub_segment_key", "year"], how="inner")
        if len(recip):
            recip["wsum"] = recip.groupby(["brand_key", "sub_segment_key", "year"])["cleaned_annual"].transform("sum")
            recip["add"] = recip["excess_total"] * recip["cleaned_annual"] / recip["wsum"]
            add_map = recip.set_index(["sector", "brand_key", "sub_model_key", "year"])["add"]
            idx = pd.MultiIndex.from_arrays(
                [annual["sector"], annual["brand_key"], annual["sub_model_key"], annual["year"]]
            )
            annual["redistributed_in"] = idx.map(add_map).to_numpy()
            annual["redistributed_in"] = pd.to_numeric(annual["redistributed_in"], errors="coerce").fillna(0.0)

    annual["cleaned_registrations"] = annual["cleaned_annual"] + annual["redistributed_in"]

    # excess that could not be redistributed (no recipients) stays flagged
    redistributed_by_group = (
        annual.groupby(["brand_key", "sub_segment_key", "year"], as_index=False)["redistributed_in"].sum()
    )
    excess_pool = excess_pool.merge(redistributed_by_group, on=["brand_key", "sub_segment_key", "year"], how="left")
    excess_pool["redistributed_in"] = excess_pool["redistributed_in"].fillna(0.0)
    excess_pool["unredistributed"] = (excess_pool["excess_total"] - excess_pool["redistributed_in"]).clip(lower=0)

    # =================== monthly cleaned file ===================
    monthly = df.copy()
    monthly = monthly.merge(
        factor_map[["brand_key", "sub_segment_key", "sector", "year", "factor"]],
        on=["brand_key", "sub_segment_key", "sector", "year"], how="left",
    )
    monthly["factor"] = monthly["factor"].fillna(1.0)
    monthly["cleaned_registrations"] = monthly["registrations"] * monthly["factor"]

    # spread redistributed_in across each recipient row's months proportional to cleaned monthly
    add_per_row = annual.loc[annual["redistributed_in"] > 0,
                             ["sector", "brand_key", "sub_model_key", "year", "redistributed_in"]]
    if len(add_per_row):
        monthly = monthly.merge(add_per_row, on=["sector", "brand_key", "sub_model_key", "year"], how="left")
        monthly["redistributed_in"] = monthly["redistributed_in"].fillna(0.0)
        row_month_sum = monthly.groupby(["sector", "brand_key", "sub_model_key", "year"])[
            "cleaned_registrations"].transform("sum")
        share = np.where(row_month_sum > EPS, monthly["cleaned_registrations"] / row_month_sum, 0.0)
        monthly["cleaned_registrations"] = monthly["cleaned_registrations"] + monthly["redistributed_in"] * share
    else:
        monthly["redistributed_in"] = 0.0

    return annual, monthly, decided, excess_pool


# --------------------------------------------------------------------------------------
# Statistical multi-brand finance/admin detector (review only, never applied)
# --------------------------------------------------------------------------------------
def detect_statistical_finance(primary: pd.DataFrame, dealer_pairs: set, ref_sectors: set) -> pd.DataFrame:
    by_bs = (
        primary.groupby(["brand_key", "sector"], as_index=False)["registrations"].sum()
        .rename(columns={"registrations": "brand_sector_total"})
    )
    nat_med = (
        by_bs.groupby("brand_key", as_index=False)["brand_sector_total"].median()
        .rename(columns={"brand_sector_total": "brand_nat_median"})
    )
    by_bs = by_bs.merge(nat_med, on="brand_key", how="left")
    by_bs["ratio"] = by_bs["brand_sector_total"] / by_bs["brand_nat_median"].clip(lower=EPS)
    by_bs["has_dealer"] = [(b, s) in dealer_pairs for b, s in zip(by_bs["brand_key"], by_bs["sector"])]
    by_bs["in_reference"] = by_bs["sector"].isin(ref_sectors)

    spike = by_bs[(by_bs["brand_sector_total"] >= 6) & (by_bs["ratio"] >= 5) & ~by_bs["has_dealer"]]
    counts = spike.groupby("sector").agg(
        n_brands=("brand_key", "nunique"),
        total_regs=("brand_sector_total", "sum"),
        brands=("brand_key", lambda x: ", ".join(sorted(set(x)))),
        any_in_reference=("in_reference", "any"),
    ).reset_index()
    candidates = counts[counts["n_brands"] >= 3].sort_values("total_regs", ascending=False)
    return candidates


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def main() -> None:
    missing = [p.name for p in [RAW_REGS, SEGMENT_LOOKUP, MCLAREN_DEALERS, COMPETITOR_DEALERS,
                                DEALER_CHANGES, REFERENCE_SITES] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {missing}")

    out_dir = TASK_DIR / f"outputs_de_distortion_pass_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=False)

    long_df = load_long_registrations()
    approved, lookup = load_segment_lookup()
    classes, ref = load_reference_sites()
    dealer_pairs, dealer_info = load_dealer_pairs()
    ref_sectors = set(ref["sector"])

    primary, excluded, unmatched = build_primary_fit(long_df, approved)
    annual, monthly, decided, excess_pool = apply_treatments(primary, classes, dealer_pairs)
    stat_candidates = detect_statistical_finance(primary, dealer_pairs, ref_sectors)

    # ---------------- canonical outputs ----------------
    annual_cols = ["sector", "area", "brand", "Model Group", "Model", "Sub Model", "sub_segment",
                   "year", "treatment_class", "original_annual", "cleaned_registrations", "redistributed_in"]
    annual_out = annual[annual_cols].rename(columns={"original_annual": "original_registrations"})
    annual_out = annual_out.sort_values(["brand", "sub_segment", "sector", "year", "Sub Model"])
    annual_out.to_csv(out_dir / "registrations_cleaned_annual.csv", index=False)
    annual_out.to_parquet(out_dir / "registrations_cleaned_annual.parquet", index=False)

    monthly_cols = ["month", "year", "sector", "area", "brand", "Model Group", "Model", "Sub Model",
                    "sub_segment", "treatment_class", "registrations", "cleaned_registrations"]
    monthly_out = monthly[monthly_cols].rename(columns={"registrations": "original_registrations"})
    monthly_out = monthly_out[monthly_out["cleaned_registrations"] > 1e-6]
    monthly_out.to_csv(out_dir / "registrations_cleaned_monthly.csv", index=False)
    monthly_out.to_parquet(out_dir / "registrations_cleaned_monthly.parquet", index=False)

    # ---------------- audits ----------------
    factory_audit = (
        annual[annual["treatment_class"] == "factory_hold"]
        .groupby(["brand", "district", "sector", "sub_segment", "year"], as_index=False)
        .agg(original_registrations=("original_annual", "sum"),
             cleaned_registrations=("cleaned_registrations", "sum"))
    )
    factory_audit["removed"] = factory_audit["original_registrations"] - factory_audit["cleaned_registrations"]
    factory_audit["reason"] = "Factory/HQ/production sector held to local district average (reference list)"
    factory_audit = factory_audit.sort_values("removed", ascending=False)
    factory_audit.to_csv(out_dir / "factory_hold_audit.csv", index=False)

    dealer_audit = decided[decided["treatment_class"] == "dealer"].copy()
    dealer_audit = dealer_audit[dealer_audit["reduction"] > 1e-9]
    dealer_audit = dealer_audit[["brand_key", "sub_segment_key", "area", "sector", "year",
                                 "sector_annual", "baseline_used", "ratio", "band", "reduction", "factor"]]
    dealer_audit["cleaned_sector"] = dealer_audit["sector_annual"] * dealer_audit["factor"]
    dealer_audit["removed"] = dealer_audit["sector_annual"] - dealer_audit["cleaned_sector"]
    dealer_audit = dealer_audit.sort_values("removed", ascending=False)
    dealer_audit.to_csv(out_dir / "dealer_reduction_audit.csv", index=False)

    finance_audit = decided[decided["treatment_class"] == "finance"].copy()
    finance_audit["held"] = finance_audit["sector_annual"] * finance_audit["factor"]
    finance_audit = finance_audit[["brand_key", "sub_segment_key", "area", "sector", "year",
                                   "sector_annual", "baseline_used", "held", "excess"]]
    finance_audit = finance_audit.sort_values("excess", ascending=False)
    finance_audit.to_csv(out_dir / "finance_redistribution_audit.csv", index=False)
    excess_pool.to_csv(out_dir / "finance_excess_pool.csv", index=False)

    stat_candidates.to_csv(out_dir / "statistical_finance_candidates_REVIEW.csv", index=False)
    unmatched.to_csv(out_dir / "primary_brand_unmatched_submodels_audit.csv", index=False)
    excluded[["month", "year", "sector", "area", "brand", "Sub Model", "sub_segment",
              "exclusion_reason", "registrations"]].to_csv(
        out_dir / "registrations_excluded_from_primary_fit_audit.csv", index=False)
    island_rows = excluded[excluded["exclusion_reason"] == "offshore_island_no_gb_drive_time"]
    island_rows[["month", "year", "sector", "area", "brand", "Sub Model", "sub_segment",
                 "registrations"]].to_csv(out_dir / "offshore_islands_excluded.csv", index=False)
    ref.to_csv(out_dir / "reference_sites_used.csv", index=False)
    pd.DataFrame(sorted(dealer_pairs), columns=["brand_key", "sector"]).to_csv(
        out_dir / "dealer_sector_pairs_used.csv", index=False)

    # review flags = AM Works heritage + any unredistributed finance excess
    review_rows = ref[ref["resolved_class"] == "review_keep"][
        ["brand", "site_name", "sector", "recommended_treatment", "notes"]].copy()
    review_rows["flag"] = "kept_in_fit_human_review_only"
    review_rows.to_csv(out_dir / "review_flags.csv", index=False)

    # ---------------- summary ----------------
    raw_total = float(long_df["registrations"].sum())
    primary_before = float(primary["registrations"].sum())
    primary_after = float(annual["cleaned_registrations"].sum())
    factory_removed = float(factory_audit["removed"].sum()) if len(factory_audit) else 0.0
    factory_held = float(factory_audit["cleaned_registrations"].sum()) if len(factory_audit) else 0.0
    dealer_removed = float(dealer_audit["removed"].sum()) if len(dealer_audit) else 0.0
    finance_excess = float(finance_audit["excess"].sum()) if len(finance_audit) else 0.0
    redistributed = float(annual["redistributed_in"].sum())
    unredistributed = float(excess_pool["unredistributed"].sum()) if len(excess_pool) else 0.0
    island_excluded = float(island_rows["registrations"].sum()) if len(island_rows) else 0.0

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "policy": {
            "factory_hold": "factory/HQ/production reference rows held to local district average (district->area->national); excess removed, not redistributed",
            "dealer_demo_removal": "banded 0/20/50/80% vs local area baseline, floored at baseline, not redistributed",
            "finance_redistribution": "hold to local baseline, redistribute excess UK-wide by clean distribution",
            "review_keep": "review_before_delete non-finance kept and flagged only",
            "dealer_bands": {"<=2x": "0%", "2-4x": "20%", "4-8x": "50%", ">8x": "80%"},
        },
        "counts": {
            "raw_nonzero_rows": int(len(long_df)),
            "primary_fit_rows": int(len(primary)),
            "excluded_rows": int(len(excluded)),
            "annual_rows": int(len(annual)),
            "factory_hold_sector_years": int(len(factory_audit)),
            "dealer_reduced_sector_years": int(len(dealer_audit)),
            "finance_sector_years": int(len(finance_audit)),
            "statistical_finance_candidates": int(len(stat_candidates)),
            "offshore_island_rows_excluded": int(len(island_rows)),
        },
        "volumes": {
            "raw_total": round(raw_total, 2),
            "primary_before_cleaning": round(primary_before, 2),
            "primary_after_cleaning": round(primary_after, 2),
            "factory_excess_removed": round(factory_removed, 2),
            "factory_held_to_local_avg": round(factory_held, 2),
            "dealer_demo_removed": round(dealer_removed, 2),
            "finance_excess_identified": round(finance_excess, 2),
            "finance_excess_redistributed": round(redistributed, 2),
            "finance_excess_unredistributed": round(unredistributed, 2),
            "offshore_island_regs_excluded": round(island_excluded, 2),
            "net_change_vs_before": round(primary_after - primary_before, 2),
        },
        "review_overrides": {
            "le7_added_as_dealer": "Sytner Lamborghini + Bentley Leicester (LE7 1PF), missing from competitor file",
            "bd1_finance_trade_hotspot": "Bradford supercar hire/trade cluster (ABM Exclusive Supercar Hire, CFA Prestige)",
            "sw1p2_finance_admin_cluster": "Westminster Lamborghini admin/finance cluster (103 regs, no dealer)",
            "district_granularity_fix": "district-only rows (e.g. CW1) now match factory/dealer/finance sites recorded as full sectors (e.g. CW1 3)",
            "islands_excluded": sorted(ISLAND_AREAS),
            "am_works_mk16_9": "kept in fit (active dealership), flagged only",
            "le5_mk15_8": "left in fit, flagged - no confirmed dealer/finance cause",
        },
        "brand_totals_primary_before": primary.groupby("brand")["registrations"].sum().round(2).to_dict(),
        "brand_totals_primary_after": annual.groupby("brand")["cleaned_registrations"].sum().round(2).to_dict(),
        "treatment_sector_year_counts": decided["treatment_class"].value_counts().to_dict(),
        "dealer_info": dealer_info,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    v = summary["volumes"]
    c = summary["counts"]
    lines = [
        "# De-Distortion Pass Summary",
        "",
        f"Output folder: `{out_dir.name}`",
        "",
        "## Volumes (primary fit, registrations)",
        f"- Before cleaning: {v['primary_before_cleaning']:,.0f}",
        f"- After cleaning: {v['primary_after_cleaning']:,.0f}  (net {v['net_change_vs_before']:+,.1f})",
        f"- Factory/HQ excess removed: {v['factory_excess_removed']:,.0f} "
        f"(held to local avg: {v['factory_held_to_local_avg']:,.1f})",
        f"- Dealer demo removed: {v['dealer_demo_removed']:,.0f}",
        f"- Finance excess identified: {v['finance_excess_identified']:,.0f}",
        f"- Finance excess redistributed UK-wide: {v['finance_excess_redistributed']:,.0f}",
        f"- Finance excess NOT redistributable (no recipients): {v['finance_excess_unredistributed']:,.0f}",
        "",
        "## Counts",
        f"- Primary-fit rows: {c['primary_fit_rows']:,} (excluded {c['excluded_rows']:,})",
        f"- Factory/HQ sector-years held to local avg: {c['factory_hold_sector_years']}",
        f"- Dealer sector-years reduced: {c['dealer_reduced_sector_years']}",
        f"- Finance sector-years: {c['finance_sector_years']}",
        f"- Statistical finance candidates (review only): {c['statistical_finance_candidates']}",
        f"- Offshore island rows excluded ({', '.join(sorted(ISLAND_AREAS))}): "
        f"{c['offshore_island_rows_excluded']} ({v['offshore_island_regs_excluded']:,.0f} regs)",
        "",
        "## Review overrides applied",
        "- LE7 added as Sytner Lamborghini/Bentley Leicester dealer (was missing from competitor file)",
        "- BD1 treated as Bradford supercar hire/trade finance hotspot",
        "- Channel Islands + Isle of Man excluded from the GB drive-time fit",
        "- Aston Martin Works MK16 9 kept in fit (flagged only)",
        "",
        "## Dealer sourcing",
        f"- Competitor pairs: {dealer_info['competitor_dealer_pairs']}, "
        f"change pairs: {dealer_info['dealer_change_pairs']}, "
        f"McLaren pairs: {dealer_info['mclaren_dealer_pairs']} "
        f"(postcode column: {dealer_info['mclaren_postcode_column']})",
        f"- McLaren dealer sectors: {', '.join(dealer_info['mclaren_dealer_sectors'])}",
        "",
        "## Key outputs",
        "- `registrations_cleaned_annual.csv/.parquet` - canonical cleaned file (sector x sub-model x year)",
        "- `registrations_cleaned_monthly.csv/.parquet` - monthly version",
        "- `factory_hold_audit.csv`, `dealer_reduction_audit.csv`, `finance_redistribution_audit.csv`",
        "- `statistical_finance_candidates_REVIEW.csv`, `review_flags.csv`",
        "- `primary_brand_unmatched_submodels_audit.csv` (coverage check of segment lookup)",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
