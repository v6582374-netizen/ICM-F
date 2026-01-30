# 数据字典 (data_dictionary)

本文件由脚本自动生成，记录 data/raw 下的数据文件概况。

## 缺失下载备注（待重试）

- `/Users/shiwen/Downloads/ICM-F_副本/data/raw/census/absmcb_AB2200MCB01_us.csv`：ABS MCB API 返回 HTTP 500（2026-01-30）。
- `/Users/shiwen/Downloads/ICM-F_副本/data/raw/census/absmcb_AB2200MCB04_us.csv`：ABS MCB API 返回 HTTP 500（2026-01-30）。

| 文件路径 | 格式 | 大小 | 列（前若干） | 类型（示例） | 备注 |
|---|---|---:|---|---|---|
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252.csv | csv | 4.3KB | task_id, task_text, IM, FR, w, s, c, evidence_note | task_id: Categorical/Text; task_text: Categorical/Text; IM: Numerical (float); FR: Numerical (float); w: Numerical (float); s: Numerical (float); c: Numerical (float); evidence_note: Categorical/Text |  |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_authoritative_sc.csv | csv | 3.84KB | task_id, task_text, IM, FR, w, s, c, evidence_note | task_id: Categorical/Text; task_text: Categorical/Text; IM: Numerical (float); FR: Numerical (float); w: Numerical (float); s: Numerical (float); c: Numerical (float); evidence_note: Categorical/Text | 权威评测驱动的 s,c 重标注输出 |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/authoritative_sc_sources.md | md | 0.78KB | - | - | 权威评测来源链接清单 |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_authoritative_anomaly_report.md | md | 0.36KB | - | - | 权威 s,c 语义匹配异常报告 |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_authoritative_summary.json | json | 0.65KB | - | - | 权威 s,c 重标注摘要（JSON） |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_authoritative_summary.xml | xml | 0.40KB | - | - | 权威 s,c 重标注摘要（XML） |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_authoritative_agg.json | json | - | alpha, beta, mu, weighted_var_s, weighted_var_c, weighted_hist_s, weighted_hist_c, weight_mass_by_dim, top5_alpha_contrib, top5_beta_contrib, low_confidence_tasks | alpha: Numerical (float); beta: Numerical (float); mu: Numerical (float); weighted_var_s: Numerical (float); weighted_var_c: Numerical (float); weighted_hist_s: Categorical/JSON; weighted_hist_c: Categorical/JSON; weight_mass_by_dim: Categorical/JSON; top5_alpha_contrib: Categorical/JSON; top5_beta_contrib: Categorical/JSON; low_confidence_tasks: Categorical/JSON | 权威 s,c 聚合诊断摘要 |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_anomaly_report.md | md | 0.3KB | - | - | Task DNA 异常统计报告 |
| /Users/shiwen/Downloads/ICM-FORMAL/data/processed/task_dna_15-1252_summary.xml | xml | 1.7KB | - | - | Task DNA 结果摘要（XML） |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/CIP2020_SOC2018_Crosswalk.xlsx | xlsx | 418.8KB | - | - | 需要 openpyxl 才能解析表头 |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/IPEDS_2018-19_Final.zip | zip | 25.8MB | - | - | ZIP 内容未解析（需解压查看） |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/absmcb_AB2200MCB03_us.csv | csv | 57.2MB | - | - | API 返回 JSON 数组（非纯 CSV），需按 JSON 解析 |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/absmcb_AB2200MCB05_us.csv | csv | 32.1MB | - | - | API 返回 JSON 数组（非纯 CSV），需按 JSON 解析 |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/all/pseo_all_institutions.csv | csv | 42.0KB | ﻿institution, label, institution_state, statefips | ﻿institution: Numerical (int); label: Categorical/Text; institution_state: Categorical/Text; statefips: Numerical (int) |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/all/pseoe_all.csv.gz | csv.gz | 11.3MB | agg_level_pseo, inst_level, institution, degree_level, cip_level, cipcode, grad_cohort, grad_cohort_years, geo_level, geography, ind_level, industry ... | agg_level_pseo: Numerical (int); inst_level: Categorical/Text; institution: Numerical (int); degree_level: Numerical (int); cip_level: Categorical/Text; cipcode: Numerical (int); grad_cohort: Numerical (int); grad_cohort_years: Numerical (int) ... |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/all/pseof_all.csv.gz | csv.gz | 61.7MB | agg_level_pseo, inst_level, institution, degree_level, cip_level, cipcode, grad_cohort, grad_cohort_years, geo_level, geography, ind_level, industry ... | agg_level_pseo: Numerical (int); inst_level: Categorical/Text; institution: Numerical (int); degree_level: Numerical (int); cip_level: Categorical/Text; cipcode: Numerical (int); grad_cohort: Numerical (int); grad_cohort_years: Numerical (int) ... |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/all/version_pseo.txt | txt | 3.8KB | - | - | 二进制或未识别格式 |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/us/pseo_us_institutions.csv | csv | 93B | ﻿institution, label, institution_state, statefips | ﻿institution: Numerical (int); label: Categorical/Text; institution_state: Categorical/Text; statefips: Numerical (int) |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/us/pseoe_us.csv.gz | csv.gz | 6.7KB | agg_level_pseo, inst_level, institution, degree_level, cip_level, cipcode, grad_cohort, grad_cohort_years, geo_level, geography, ind_level, industry ... | agg_level_pseo: Numerical (int); inst_level: Categorical/Text; institution: Numerical (int); degree_level: Numerical (int); cip_level: Categorical/Text; cipcode: Numerical (float); grad_cohort: Numerical (int); grad_cohort_years: Numerical (int) ... |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/us/pseof_us.csv.gz | csv.gz | 77.3KB | agg_level_pseo, inst_level, institution, degree_level, cip_level, cipcode, grad_cohort, grad_cohort_years, geo_level, geography, ind_level, industry ... | agg_level_pseo: Numerical (int); inst_level: Categorical/Text; institution: Numerical (int); degree_level: Numerical (int); cip_level: Categorical/Text; cipcode: Numerical (int); grad_cohort: Numerical (int); grad_cohort_years: Numerical (int) ... |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/census/pseo/R2025Q2/us/version_pseo.txt | txt | 122B | - | - | 二进制或未识别格式 |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/cisa_known_exploited_vulnerabilities.csv | csv | 777.2KB | cveID, vendorProject, product, vulnerabilityName, dateAdded, shortDescription, requiredAction, dueDate, knownRansomwareCampaignUse, notes, cwes | cveID: Categorical/Text; vendorProject: Categorical/Text; product: Categorical/Text; vulnerabilityName: Categorical/Text; dateAdded: Timestamp; shortDescription: Categorical/Text; requiredAction: Categorical/Text; dueDate: Timestamp ... |  |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/gss/spss_qwl.zip | zip | 4.4MB | - | - | ZIP 内容示例: NIOSH-QWL.sav |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/gss/stata_qwl.zip | zip | 6.8MB | - | - | ZIP 内容示例: NIOSH-QWL.dta |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/itu_rpm_afr_pub_2025_data.xlsx | xlsx | 224.1KB | - | - | 需要 openpyxl 才能解析表头 |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/nvdcve-2.0-2024.json.gz | json.gz | 19.0MB | - | - | 压缩 JSON（未解析字段） |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/nvdcve-2.0-recent.json.gz | json.gz | 381.7KB | - | - | 压缩 JSON（未解析字段） |
| /Users/shiwen/Downloads/ICM-FORMAL/data/raw/onet/db_30_1_text.zip | zip | 12.8MB | - | - | ZIP 内容示例: db_30_1_text/, db_30_1_text/Skills to Work Context.txt, db_30_1_text/Education, Training, and Experience.txt, db_30_1_text/Sample of Reported Titles.txt, db_30_1_text/Task Categories.txt, db_30_1_text/Task Ratings.txt, db_30_1_text/Occupation Level Metadata.txt, db_30_1_text/UNSPSC Reference.txt, db_30_1_text/Work Context.txt, db_30_1_text/Occupation Data.txt, db_30_1_text/Work Styles.txt, db_30_1_text/Abilities.txt |
| /Users/shiwen/Downloads/ICM-F_副本/data/raw/oxford_martin_future_of_employment_2017.pdf | pdf | 1.3MB | - | - | PDF 文档/附录 |
