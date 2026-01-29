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

# 项目根目录：脚本在 code/ 下时为父目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"

# 直链下载清单：(本地文件名, 下载 URL)
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
]

# World Bank WDI：返回 ZIP，解压后 CSV 的命名以 API 为准，此处约定落盘名
WB_INDICATORS = [
    ("wdi_IT_NET_USER_ZS.csv", "https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS?downloadformat=csv"),
    ("wdi_NY_GDP_MKTP_CD.csv", "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?downloadformat=csv"),
]


def _download(url: str, dest: Path, desc: str = "") -> None:
    req = Request(url, headers={"User-Agent": "ICM-F-data/1.0"})
    try:
        with urlopen(req, timeout=120) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.read())
        print(f"  ok: {dest.name}")
    except (URLError, HTTPError, OSError) as e:
        print(f"  fail: {dest.name} — {e}")


def _download_wb_zip(url: str, dest_csv: Path) -> None:
    """下载 World Bank ZIP，解压得到数据 CSV（排除 Metadata）并保存为 dest_csv。"""
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


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print(f"Target directory: {DATA_RAW}")

    print("\n[1] Direct file downloads")
    for name, url in DOWNLOAD_LIST:
        _download(url, DATA_RAW / name)

    print("\n[2] World Bank WDI (ZIP → CSV)")
    for name, url in WB_INDICATORS:
        _download_wb_zip(url, DATA_RAW / name)

    print("\nDone. VCDB（GitHub 每事件一 JSON）需在仓库中按需克隆，例如：")
    print("  git clone --depth 1 https://github.com/vz-risk/VCDB.git data/raw/vcdb")


if __name__ == "__main__":
    main()
