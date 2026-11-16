# Running eqasim on Windows through WSL

## 1. Check what the PC has (PowerShell)

```powershell
wsl --status
wsl -l -v
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)
```

If WSL is missing: `wsl --install -d Ubuntu` in an administrator PowerShell,
then reboot. Aim for 16 GB of RAM; with less, lower `sampling_rate` and
`processes` in the configs.

## 2. Inside Ubuntu (WSL)

```bash
cd /path/to/territorial-chains            # for instance /mnt/c/Users/<you>/Downloads/territorial-chains
bash scripts/setup_wsl.sh
```

This clones eqasim-france v1.5.0 into `~/eqasim-france`, installs its
dependencies with `uv`, and writes six configs. Data and outputs stay in
the project folder so they are visible from Windows; the cache stays on
the Linux side because it is much faster there.

## 3. Data, smoke test, then the variants

```bash
cd /path/to/territorial-chains            # for instance /mnt/c/Users/<you>/Downloads/territorial-chains
bash scripts/download_data.sh                       # several GB, resumable
(cd ~/eqasim-france && uv run python "$OLDPWD/configs/make_configs.py" "$OLDPWD" 0.1)
bash scripts/run_variants.sh                        # smoke test, 0.1% sample
bash scripts/run_variants.sh A_entd_local B_entd_national C_entd_urban D_emp_national E_emp_urban
```

All variants share one cache (`~/eqasim-cache`), so the census, SIRENE and
building stages are computed once. Logs go to `output/<variant>/run.log`.
