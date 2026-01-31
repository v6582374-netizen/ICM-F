# Domain Mapping Used (SOC 2018 Major Groups)

This file documents the SOC major-group mapping used for S/T/A classification.

## Scope
- SOC 2018 major groups (two-digit prefixes from O*NET-SOC codes).
- Local O*NET source: `/Users/shiwen/Downloads/ICM-FORMAL/data/raw/onet/db_30_1_text/Occupation Data.txt`.
- Authoritative SOC major-group list: https://www.bls.gov/soc/2018/major_groups.htm

## strict (default in code)
```
STEM  = ["15", "17", "19"]
TRADE = ["47", "49", "51"]
ARTS  = ["27"]
```

## extended (optional)
```
STEM  = ["11", "13", "15", "17", "19", "25", "29"]
TRADE = ["45", "47", "49", "51", "53"]
ARTS  = ["27"]
```

## Notes
- The code currently uses the strict mapping above.
- Any changes must keep SOC major groups aligned to the BLS SOC 2018 list.
