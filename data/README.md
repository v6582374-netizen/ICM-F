# 数据目录说明

本目录按 **data-engineer-role** 约定存放原始数据与处理结果：

- **`raw/`**：仅存放原始下载数据，不可被脚本改写。
- **`processed/`**：ETL 或建模脚本的输出，由数据手维护。

## 原始数据下载

表中所有**可直链下载**的数据集由脚本统一拉取到 `raw/`：

```bash
# 在项目根目录执行（需网络）
.venv/bin/python code/download_raw_datasets.py
# 或
uv run python code/download_raw_datasets.py
```

脚本会向 `data/raw/` 写入以下文件（若某次运行因网络失败，可多次重试）：

| 目标文件名 | 来源 |
|------------|------|
| `eurepoc_global_dataset_1_3.csv` | EuRepoC Zenodo – 全球事件主表 |
| `eurepoc_attribution_dataset_1_3.csv` | EuRepoC Zenodo – 归因展开表 |
| `eurepoc_receiver_dataset_1_3.csv` | EuRepoC Zenodo – 受害方展开表 |
| `eurepoc_dyadic_dataset_0_1.csv` | EuRepoC Zenodo – 国家对表 |
| `itu_rpm_afr_pub_2025_data.xlsx` | ITU – GCI 示例数据包（含 Global cybersecurity index 相关 sheet） |
| `cisa_known_exploited_vulnerabilities.csv` | CISA KEV – 已知被利用漏洞目录 |
| `nvdcve-2.0-2024.json.gz` | NIST NVD – CVE 2.0 年度 JSON |
| `nvdcve-2.0-recent.json.gz` | NIST NVD – CVE 2.0 近期 JSON |
| `oecd_stip_policy_initiatives.csv` | OECD STIP – 政策倡议 API 导出（示例参数） |
| `wdi_IT_NET_USER_ZS.csv` | World Bank WDI – 互联网使用率 |
| `wdi_NY_GDP_MKTP_CD.csv` | World Bank WDI – GDP |

**VCDB（VERIS Community Database）** 为 GitHub 仓库，每事件一 JSON，需在本地按需克隆：

```bash
git clone --depth 1 https://github.com/vz-risk/VCDB.git data/raw/vcdb
```

克隆后 `data/raw/vcdb` 下为按事件分组的 JSON 文件，可与 DBIR/VERIS 方法一致地解析。

## 数据字典

根目录的 **`data_dictionary.md`** 由数据手根据 `data/` 下的文件生成与更新，记录各文件的路径、列名、类型与缺失率等 Schema，供建模与编程手遵守。
