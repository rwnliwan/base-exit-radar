# Gate §7 — hasil test (Base prototype)

Policy: base-proto-policy v0.3.3 | Method: base-proto-method v0.3.3 | Schema: base-proto-schema v0.3.3

Hasil: **19/19 PASS**.

| Tes | Hasil | Expected | Actual |
|-----|-------|----------|--------|
| happy_path | PASS | identity correct, values/timestamps/sources saved, decision explainable | 10/10 checks pass; failed: none |
| controlled_trigger | PASS | decision=ABSTAIN reason=dex_deviation_extreme, one TEST/REPLAY alert emitted | decision=ABSTAIN reasons=['dex_deviation_extreme'] alert_duplicate=False mode=TEST/REPLAY |
| nav_weekend | PASS | NAV shown as last published reference + age/off-hours; not a live alarm | 8/8 checks pass; failed: none |
| multiplier | PASS | NAV not multiplied again; raw share conversion uses effective multiplier | 4/4 checks pass; failed: none |
| missing_stale | PASS | missing source -> ABSTAIN (no zero-risk); stale NAV flagged; gates separate | missing_pools: decision=ABSTAIN (expect ABSTAIN) ok=True; stale_nav: decision=WATCH codes=['exit_quote_missing', 'nav_stale_off_hours', 'no_exit_quote_adapter', 'oracle_registry_unknown', 'snapshot_transformed_replay'] ok=True; gates_separate ok=True |
| coverage | PASS | two aggregators one pool = one pool; one venue -> no false confidence | cross_check_same_pool ok=True; single_pool decision=ABSTAIN (expect ABSTAIN) median=None ok=True |
| proxy | PASS | extreme funding/OI alone does not trigger token-exit claim; label persists; OI change null | decision=WATCH (expect WATCH) ok=True; alert proxy_label ok=True; oi_change_24h=None ok=True |
| liquidity_vs_exit | PASS | large TVL without sell quote stays exit_quality_unverified; no sell claim | 5/5 checks pass; failed: none |
| idempotency | PASS | same snapshot/rule replay does not duplicate alert; bad input errors | first emit duplicate=False, second emit duplicate=True, same id=True; bad input: assess_snapshot({}) raised KeyError (structured error, not empty success) |
| quote_validation | PASS | null/empty/malformed/invalid/stale quotes -> cash-only WATCH; real USDC (native + USDC.e) verified; PAPER_PROPOSAL requires verified layer B + gate on | 31/31 cases cash-only; failed: none |
| freshness | PASS | DEX/quote/NAV freshness tested by time input; separate codes; replay vs live distinguished | 13/13 checks pass; failed: none |
| coverage_recomputed | PASS | chain/identity validated; counts recomputed from validated pools; venue aliases canonical; transformed payloads marked | 11/11 checks pass; failed: none |
| snapshot_identity_live_build | PASS | snapshot built by fixed build_snapshot is self-consistent on replay: identity matches, no transformed flag, stored == recomputed coverage | 8/8 checks pass; failed: none |
| dedup_persistence | PASS | persist failures are structured errors (not empty success); restart still duplicate; concurrent workers get exactly one new emit | 10/10 checks pass; failed: none |
| happy_path_both_tokens | PASS | NVDAc + AAPLc full chain (mock adapter from raw capture): build, assess, decide, explain, emit, paper record | 16/16 checks pass; failed: none |
| nav_multiplier_build | PASS | NAV stored as-is (not multiplied) across NAV/multiplier variations on the build path | 8/8 checks pass; failed: none |
| quoter_adapter | PASS | Aero Metaquoter V3 + OracleRegistry + factory venue (mock RPC, offline): parsing, fail-closed decoder, venue mapping (Aero Slipstream = aerodrome), full build layer B simulated_exit_quote_verified, paused oracle marks NAV stale | 26/26 checks pass; failed: none |
| quoter_g1_g6 | PASS | regression G1-G6 re-audit v5: venue terpisah, guard quote, partial-fill, decoder fail-closed, label jujur, registry blocking | 44/44 checks pass; failed: none |
| quoter_f1_f2_m1_m3 | PASS | follow-up F1+F2+F3 re-audit v6 + minor M1-M3 re-audit v7: MAX kontrak TickMath, double-quote probe, validator cap max_age, factory Aero V2, probe wajib sukses, factory di exit_quote | 22/22 checks pass; failed: none |

Detail per tes (termasuk fixture yang dimodifikasi) ada di `gate_results.json` dan `fixtures/`. Replay memakai mode TEST/REPLAY; alert sintetis bukan kejadian pasar live.
