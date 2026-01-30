"""
按数据手规范将表中可直链下载的数据集下载到项目 data/raw/ 目录。

数据来源与路径约定（与 data-engineer-role 一致）：
- 仅写入 ./data/raw/，不修改任何已有文件。
- 运行前请确保网络可达（Zenodo / ITU / World Bank / CISA / NIST / OECD）。

使用方法（在项目根目录执行）：
    uv run python code/download_raw_datasets.py
或：
    .venv/bin/python code/download_raw_datasets.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from http.client import IncompleteRead

# 项目根目录：脚本在 code/ 下时为父目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"

# 直链下载清单：(本地文件名, 下载 URL)
PSEO_RELEASE = "R2025Q2"
DOWNLOAD_LIST = [
    # EuRepoC – Global Dataset of Cyber Incidents (Zenodo)
    ("eurepoc_global_dataset_1_3.csv", "https://zenodo.org/records/14965395/files/eurepoc_global_dataset_1_3.csv?download=1"),
    ("eurepoc_attribution_dataset_1_3.csv", "https://zenodo.org/records/14965395/files/eurepoc_attribution_dataset_1.3.csv?download=1"),
    ("eurepoc_receiver_dataset_1_3.csv", "https://zenodo.org/records/14965395/files/eurepoc_receiver_dataset_1.3.csv?download=1"),
    ("eurepoc_dyadic_dataset_0_1.csv", "https://zenodo.org/records/14965395/files/eurepoc_dyadic_dataset_0_1.csv?download=1"),
    # ITU – Global Cybersecurity Index 示例数据包（含 GCI 相关 sheet）
    ("itu_rpm_afr_pub_2025_data.xlsx", "https://www.itu.int/en/ITU-D/Statistics/Documents/facts/rpm_afr_pub_2025_data.xlsx"),
    # CISA – Known Exploited Vulnerabilities
    ("cisa_known_exploited_vulnerabilities.csv", "https://www.cisa.gov/sites/default/files/csv/known_exploited_vulnerabilities.csv"),
    # NIST NVD – CVE 2.0 JSON Feeds
    ("nvdcve-2.0-2024.json.gz", "https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2024.json.gz"),
    ("nvdcve-2.0-recent.json.gz", "https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-recent.json.gz"),
    # OECD STIP – Policy Initiatives API 导出
    ("oecd_stip_policy_initiatives.csv", "https://stip.oecd.org/ws/STIP/API/getPolicyInitiatives.xqy?br=BR9%2CBR15&br-extra=none%2CBR16%2CBR1&format=csv&tg=TG35&th=TH5"),
    # O*NET Production Database 30.1（文本/CSV 版）
    ("onet/db_30_1_text.zip", "https://www.onetcenter.org/dl_files/database/db_30_1_text.zip"),
    # CIP2020-SOC2018 Crosswalk
    ("CIP2020_SOC2018_Crosswalk.xlsx", "https://nces.ed.gov/ipeds/cipcode/Files/CIP2020_SOC2018_Crosswalk.xlsx"),
    # IPEDS Access Database 2018-19 (Final)
    ("IPEDS_2018-19_Final.zip", "https://nces.ed.gov/ipeds/tablefiles/zipfiles/IPEDS_2018-19_Final.zip"),
    # GSS Quality of Worklife (SPSS / Stata)
    ("gss/spss_qwl.zip", "https://gss.norc.org/content/dam/gss/get-the-data/documents/spss/spss_qwl.zip"),
    ("gss/stata_qwl.zip", "https://gss.norc.org/content/dam/gss/get-the-data/documents/stata/stata_qwl.zip"),
    # Frey & Osborne (2017) report PDF with appendix tables
    ("oxford_martin_future_of_employment_2017.pdf", "https://www.oxfordmartin.ox.ac.uk/downloads/academic/future-of-employment.pdf"),
    # PSEO bulk downloads (LEHD)
    (f"census/pseo/{PSEO_RELEASE}/all/pseoe_all.csv.gz", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/all/pseoe_all.csv.gz"),
    (f"census/pseo/{PSEO_RELEASE}/all/pseof_all.csv.gz", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/all/pseof_all.csv.gz"),
    (f"census/pseo/{PSEO_RELEASE}/all/pseo_all_institutions.csv", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/all/pseo_all_institutions.csv"),
    (f"census/pseo/{PSEO_RELEASE}/all/version_pseo.txt", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/all/version_pseo.txt"),
    (f"census/pseo/{PSEO_RELEASE}/us/pseoe_us.csv.gz", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/us/pseoe_us.csv.gz"),
    (f"census/pseo/{PSEO_RELEASE}/us/pseof_us.csv.gz", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/us/pseof_us.csv.gz"),
    (f"census/pseo/{PSEO_RELEASE}/us/pseo_us_institutions.csv", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/us/pseo_us_institutions.csv"),
    (f"census/pseo/{PSEO_RELEASE}/us/version_pseo.txt", f"https://lehd.ces.census.gov/data/pseo/{PSEO_RELEASE}/us/version_pseo.txt"),
]

# World Bank WDI：返回 ZIP，解压后 CSV 的命名以 API 为准，此处约定落盘名
WB_INDICATORS = [
    ("wdi_IT_NET_USER_ZS.csv", "https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS?downloadformat=csv"),
    ("wdi_NY_GDP_MKTP_CD.csv", "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?downloadformat=csv"),
]

# ABS MCB groups for 2022 technology/financing/climate module
ABSMCB_GROUPS_2022 = [
    "AB2200MCB01",
    "AB2200MCB02",
    "AB2200MCB03",
    "AB2200MCB04",
    "AB2200MCB05",
]


def _download(url: str, dest: Path, desc: str = "") -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip: {dest.name} (exists)")
        return
    req = Request(url, headers={"User-Agent": "ICM-F-data/1.0"})
    tmp_path = dest.with_name(dest.name + ".part")
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
    try:
        with urlopen(req, timeout=120) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp_path.replace(dest)
        print(f"  ok: {dest.name}")
    except (URLError, HTTPError, OSError, IncompleteRead) as e:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        print(f"  fail: {dest.name} — {e}")


def _download_wb_zip(url: str, dest_csv: Path) -> None:
    """下载 World Bank ZIP，解压得到数据 CSV（排除 Metadata）并保存为 dest_csv。"""
    if dest_csv.exists() and dest_csv.stat().st_size > 0:
        print(f"  skip: {dest_csv.name} (exists)")
        return
    req = Request(url, headers={"User-Agent": "ICM-F-data/1.0"})
    zip_path = dest_csv.with_suffix(".zip")
    try:
        with urlopen(req, timeout=120) as resp:
            zip_path.write_bytes(resp.read())
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_csv = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            data_csv = [n for n in all_csv if "Metadata" not in n] or all_csv
            preferred = [n for n in data_csv if "API" in n or "Indicator" in n]
            chosen = (preferred[0] if preferred else data_csv[0]) if data_csv else None
            if chosen:
                dest_csv.write_bytes(zf.read(chosen))
                print(f"  ok: {dest_csv.name} (from zip)")
            else:
                print(f"  fail: no CSV in zip for {dest_csv.name}")
        zip_path.unlink(missing_ok=True)
    except (URLError, HTTPError, OSError, zipfile.BadZipFile) as e:
        print(f"  fail: {dest_csv.name} — {e}")
        if zip_path.exists():
            zip_path.unlink(missing_ok=True)

def _download_census_group_csv(
    base_url: str,
    group: str,
    dest: Path,
    geo_for: str = "us:1",
    extra_params: str = "",
) -> None:
    """下载 Census API group 数据并保存为 CSV。"""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip: {dest.name} (exists)")
        return
    query = f"get=group({group})&for={geo_for}"
    if extra_params:
        query = f"{query}&{extra_params}"
    url = f"{base_url}?{query}"
    req = Request(url, headers={"User-Agent": "ICM-F-data/1.0"})
    try:
        with urlopen(req, timeout=120) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        if content.lstrip().startswith("{") and '"error"' in content[:200]:
            print(f"  fail: {dest.name} — API error")
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"  ok: {dest.name}")
    except (URLError, HTTPError, OSError) as e:
        print(f"  fail: {dest.name} — {e}")


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print(f"Target directory: {DATA_RAW}")

    print("\n[1] Direct file downloads")
    for name, url in DOWNLOAD_LIST:
        _download(url, DATA_RAW / name)

    print("\n[2] World Bank WDI (ZIP → CSV)")
    for name, url in WB_INDICATORS:
        _download_wb_zip(url, DATA_RAW / name)

    print("\n[3] Census API group downloads (CSV)")
    # ABS Technology-related module (absmcb, US-level, multiple groups)
    for group in ABSMCB_GROUPS_2022:
        _download_census_group_csv(
            "https://api.census.gov/data/2022/absmcb",
            group,
            DATA_RAW / f"census/absmcb_{group}_us.csv",
            geo_for="us:1",
            extra_params="NAICS2022=00",
        )

    print("\nDone. VCDB（GitHub 每事件一 JSON）需在仓库中按需克隆，例如：")
    print("  git clone --depth 1 https://github.com/vz-risk/VCDB.git data/raw/vcdb")


if __name__ == "__main__":
    main()
