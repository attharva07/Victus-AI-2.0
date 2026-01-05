# Victus Quality Report

Generated: 2026-01-05T21:00:53.544893+00:00
Commit: bd086e0 (dirty)
Python: 3.12.12

## Summary
| Check | Status | Notes |
| --- | --- | --- |
| Tests (quiet) | ✅ Pass | ............................................................................                                             [100%] |
| Coverage | ✅ Pass | 56% |
| Ruff lint | ✅ Pass | All checks passed! |

## Coverage
Reported coverage: 56%
Top uncovered lines:
- victus/__init__.py                           1     1     0%   1
- victus/app.py                              195    89    54%   5-9,31,44,49,54,61,66,69,73,75-80,83,95-96,106,112,115,120,124,126-129,131-163,167-174,178-182,185-186,188-194,196,216,221
- victus/audit.py                              1     1     0%   1
- victus/config/__init__.py                    0     0   100%
- victus/config/runtime.py                    36    20    44%   13,15-16,20,22,26,28-30,32,34,38,45,52,54-55,59,61,65,67
- victus/core/__init__.py                      0     0   100%
- victus/core/approval.py                      6     1    83%   8
- victus/core/audit.py                        37     2    95%   25,42
- victus/core/cli/__init__.py                  0     0   100%
- victus/core/cli/constants.py                 6     0   100%
- victus/core/cli/failures_cmd.py             64    34    47%   10-24,28-39,43-49
- victus/core/cli/main.py                     31    31     0%   1-3,5-11,14-16,18-21,24-35,38-39
- victus/core/cli/memory_cmd.py               84    40    52%   12-21,28-29,35-42,46-52,56-62,66-71
- victus/core/cli/report_cmd.py               19     7    63%   9-15
- victus/core/executor.py                     93    50    46%   27,34,40,47,50,54,56-58,60-63,65-73,75-101,105
- victus/core/failures/__init__.py             4     4     0%   1-3,5
- victus/core/failures/logger.py              47     6    87%   23,42,54,56-58
- victus/core/failures/models.py              15     0   100%
- victus/core/failures/redaction.py           33     8    76%   16,20,22-23,27,36,40,44
- victus/core/failures/schema.py              65    10    85%   48-49,57-58,62,67,69,71,74,80
